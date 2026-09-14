"""
E-FR-01 · 教学转向状态机（架桥）
================================

把 pedagogy 的 if-else 选策略，替换为「学生状态 → 教学意图转移图 → 按意图生成」。
这样误区/根因诊断才能**反过来驱动教学路径**——这就是 SRS 3.2 说的"架桥"。

借鉴强度（见补充 II 的分级）
---------------------------
StratL 是 L1（有开源）。本项目只借它的三段式**结构**：状态追踪 → 意图选择 →
按意图生成。转移图用规则/配置而非 LLM 驱动——StratL 自己的实证就表明手工意图
选择比 LLM 驱动更贴合策略，这一点不必再验一遍。

硬前提
------
本模块依赖 SRS 3.1 的 B-FR-13（真实历史计数）。**没有真实的 attempt_count，
状态机退化为无记忆**——所有转移都会走 first_time 分支，concept_explanation
永远不可达。这不是本模块的缺陷，是它的前提；`select_strategy` 在 attempt_count
明显不合法时会拒绝而非静默降级。

不重构承诺
----------
本模块是新增文件。既有调用方通过 `select_strategy_legacy()` 适配层接入，
签名与 SRS 3.1 一致，零改动。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable

import yaml


# =============================================================================
# 1. 契约（与 SRS 3.2 §4.2.1 一致）
# =============================================================================

class TeachingIntent(str, Enum):
    ELICIT_PREDICTION = "elicit_prediction"      # E-FR-05：先预测
    PRODUCTIVE_FAILURE = "productive_failure"    # 让其有成效地卡住
    PROGRESSIVE_HINT = "progressive_hint"        # L1..L5 渐进提示
    CONCEPT_EXPLANATION = "concept_explanation"  # 重复误区 → 概念重讲
    COUNTEREXAMPLE = "counterexample"            # AST 定向反例
    CONSOLIDATE = "consolidate"                  # 巩固小结
    ADVANCE = "advance"                          # 进入下一知识点


MASTERY_THRESHOLD = 0.6
REPEAT_THRESHOLD = 3        # 第 ≥3 次同一误区 → 概念重讲（E-FR-01 验收）
MAX_HINT_LEVEL = 5


@dataclass
class StudentState:
    """状态追踪的产物。字段全部可由现有诊断链路填充。"""

    concept_mastery: dict[str, float] = field(default_factory=dict)
    active_misconceptions: list[str] = field(default_factory=list)
    root_cause_weights: dict[str, float] = field(default_factory=dict)  # E-FR-04，可空
    attempt_count: int = 1              # 来自 misconception_events（B-FR-13）
    error_class: str | None = None      # E-FR-02 第 1 层
    last_intent: TeachingIntent | None = None

    # --- 以下为 SRS §4.2.1 之外的扩展，服务 E-FR-05 ---
    prediction_submitted: bool = False
    prediction_matches_actual: bool | None = None


@dataclass
class StrategyDecision:
    intent: TeachingIntent
    hint_level: int
    prompt_template: str

    # 便于日志与 A/B：记录是哪条规则做的决定
    matched_rule: str = ""


# =============================================================================
# 2. 谓词注册表 —— 转移图里的 `when:` 只能引用这里注册过的名字
# =============================================================================

Predicate = Callable[[StudentState], bool]
_PREDICATES: dict[str, Predicate] = {}


def predicate(name: str) -> Callable[[Predicate], Predicate]:
    def deco(fn: Predicate) -> Predicate:
        _PREDICATES[name] = fn
        return fn
    return deco


@predicate("always")
def _always(s: StudentState) -> bool:
    return True


@predicate("prediction_submitted")
def _prediction_submitted(s: StudentState) -> bool:
    return s.prediction_submitted


@predicate("repeated_same_misconception")
def _repeated(s: StudentState) -> bool:
    """同一误区第 ≥3 次。注意 attempt_count 必须是**本次之前**的次数 +1，
    即 B-FR-18 修复后的"先读后写"语义；否则这里会提前一次触发。"""
    return bool(s.active_misconceptions) and s.attempt_count >= REPEAT_THRESHOLD


@predicate("first_time_misconception")
def _first_time(s: StudentState) -> bool:
    """命名沿用 SRS，语义是"尚未达到重复阈值"（attempt 1 或 2）。
    attempt=2 仍走渐进提示，只是 hint_level 更高。"""
    return bool(s.active_misconceptions) and s.attempt_count < REPEAT_THRESHOLD


@predicate("still_failing")
def _still_failing(s: StudentState) -> bool:
    return bool(s.active_misconceptions) and not _mastery_recovered(s)


@predicate("mastery_recovered")
def _mastery_recovered(s: StudentState) -> bool:
    if not s.concept_mastery:
        return False
    return min(s.concept_mastery.values()) >= MASTERY_THRESHOLD


# =============================================================================
# 3. 转移图
# =============================================================================

@dataclass(frozen=True)
class Rule:
    from_intent: str      # 意图名或 "*"
    when: str             # 谓词名
    to: TeachingIntent

    def describe(self) -> str:
        return f"{self.from_intent} --[{self.when}]--> {self.to.value}"


class TransitionGraph:
    """从 YAML 载入并**在载入时校验**。

    校验必须发生在载入时而非匹配时：配置里写错一个意图名，应当在服务启动时
    炸掉，而不是等某个学生恰好走到那条分支才 500。
    """

    def __init__(self, start: TeachingIntent, default: TeachingIntent,
                 entry_on_misconception: TeachingIntent, rules: list[Rule]):
        self.start = start
        self.default = default
        self.entry_on_misconception = entry_on_misconception
        self.rules = rules

    @classmethod
    def from_yaml(cls, path: str | Path) -> "TransitionGraph":
        with open(path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        def as_intent(v: str, key: str) -> TeachingIntent:
            try:
                return TeachingIntent(v)
            except ValueError:
                raise ValueError(
                    f"转移图 {key}={v!r} 不是合法的 TeachingIntent。"
                    f"合法值：{[i.value for i in TeachingIntent]}"
                ) from None

        rules: list[Rule] = []
        for i, r in enumerate(cfg.get("transitions", [])):
            missing = {"from", "when", "to"} - set(r)
            if missing:
                raise ValueError(f"转移图第 {i} 条规则缺少字段 {sorted(missing)}")
            if r["when"] not in _PREDICATES:
                raise ValueError(
                    f"转移图第 {i} 条规则引用了未注册的谓词 {r['when']!r}。"
                    f"已注册：{sorted(_PREDICATES)}"
                )
            if r["from"] != "*":
                as_intent(r["from"], f"transitions[{i}].from")
            rules.append(Rule(r["from"], r["when"], as_intent(r["to"], f"transitions[{i}].to")))

        return cls(
            start=as_intent(cfg["start"], "start"),
            default=as_intent(cfg.get("default", "progressive_hint"), "default"),
            entry_on_misconception=as_intent(
                cfg.get("entry_on_misconception", "productive_failure"),
                "entry_on_misconception"),
            rules=rules,
        )


_GRAPH: TransitionGraph | None = None


def get_graph(path: str | Path | None = None) -> TransitionGraph:
    global _GRAPH
    if _GRAPH is None or path is not None:
        p = Path(path) if path else Path(__file__).with_name("transition_graph.yaml")
        _GRAPH = TransitionGraph.from_yaml(p)
    return _GRAPH


# =============================================================================
# 4. 意图选择
# =============================================================================

def _resolve_current(s: StudentState, graph: TransitionGraph) -> str:
    """确定"从哪个意图出发"求值。

    三种情形：
      - 已有 last_intent           → 就从它出发
      - 无 last_intent 但已命中误区 → 从 entry_on_misconception 出发（见 YAML 注释）
      - 都没有                     → 从 start 出发
    """
    if s.last_intent is not None:
        return s.last_intent.value
    if s.active_misconceptions:
        return graph.entry_on_misconception.value
    return graph.start.value


def select_next_intent(
    s: StudentState, graph: TransitionGraph | None = None
) -> tuple[TeachingIntent, str]:
    """返回 (下一意图, 命中的规则描述)。规则按列表顺序匹配，首条命中即返回。"""
    graph = graph or get_graph()
    current = _resolve_current(s, graph)

    for rule in graph.rules:
        if rule.from_intent not in ("*", current):
            continue
        if _PREDICATES[rule.when](s):
            return rule.to, rule.describe()

    return graph.default, f"<default> -> {graph.default.value}"


# =============================================================================
# 5. 意图 → 提示等级 / 模板
# =============================================================================

_TEMPLATES: dict[TeachingIntent, str] = {
    TeachingIntent.ELICIT_PREDICTION: "elicit_prediction.j2",
    TeachingIntent.PRODUCTIVE_FAILURE: "productive_failure.j2",
    TeachingIntent.PROGRESSIVE_HINT: "progressive_hint.j2",
    TeachingIntent.CONCEPT_EXPLANATION: "concept_explanation.j2",
    TeachingIntent.COUNTEREXAMPLE: "counterexample.j2",
    TeachingIntent.CONSOLIDATE: "consolidate.j2",
    TeachingIntent.ADVANCE: "advance.j2",
}


def _intent_to_hint_level(intent: TeachingIntent, s: StudentState) -> int:
    """只有渐进提示有等级，且随尝试次数上升（封顶 5）。
    其余意图 hint_level=0——概念重讲不是"更强的提示"，它是另一种教学动作。"""
    if intent is TeachingIntent.PROGRESSIVE_HINT:
        return max(1, min(s.attempt_count, MAX_HINT_LEVEL))
    return 0


def _intent_to_template(intent: TeachingIntent) -> str:
    return _TEMPLATES[intent]


def select_strategy(s: StudentState) -> StrategyDecision:
    """主入口。SRS 3.2 §4.2.1 的签名。"""
    if s.attempt_count < 1:
        raise ValueError(
            f"attempt_count={s.attempt_count} 非法。它应当来自 misconception_events "
            f"的真实计数（B-FR-13）；传 0 说明历史查询失败，此时静默降级会让 "
            f"concept_explanation 永久不可达。"
        )
    intent, rule = select_next_intent(s)
    return StrategyDecision(
        intent=intent,
        hint_level=_intent_to_hint_level(intent, s),
        prompt_template=_intent_to_template(intent),
        matched_rule=rule,
    )


# =============================================================================
# 6. 适配层：保留 SRS 3.1 的旧签名，调用方零改动
# =============================================================================

def select_strategy_legacy(
    misconception_id: str,
    attempt_count: int,
    has_history: bool,
) -> dict:
    """旧签名 → 新状态机。返回旧的 dict 契约 {"strategy", "hint_level"}。

    `has_history` 在新模型里是冗余的（attempt_count >= 2 即蕴含有历史），
    保留它只为签名兼容；若二者矛盾，以 attempt_count 为准并不静默——矛盾本身
    往往意味着调用方仍在用 B-FR-18 修复前的"先写后读"顺序。
    """
    if has_history and attempt_count <= 1:
        raise ValueError(
            "has_history=True 但 attempt_count<=1，二者矛盾。"
            "通常是误区事件在查询历史之前就入库了（B-FR-18 时序缺陷）。"
        )
    s = StudentState(
        active_misconceptions=[misconception_id],
        attempt_count=attempt_count,
    )
    d = select_strategy(s)
    return {"strategy": d.intent.value, "hint_level": d.hint_level}


if __name__ == "__main__":
    print("== E-FR-01 验收判定 ==")
    for n in (1, 2, 3, 4):
        s = StudentState(active_misconceptions=["M3"], attempt_count=n)
        d = select_strategy(s)
        print(f"  第 {n} 次: {d.intent.value:20} hint={d.hint_level}  ←  {d.matched_rule}")

    print("\n== 掌握后收尾 ==")
    s = StudentState(concept_mastery={"list": 0.8}, attempt_count=1,
                     last_intent=TeachingIntent.PROGRESSIVE_HINT)
    d = select_strategy(s)
    print(f"  {d.intent.value}  ←  {d.matched_rule}")

    print("\n== E-FR-05 预测环节 ==")
    s = StudentState(attempt_count=1, prediction_submitted=True,
                     last_intent=TeachingIntent.ELICIT_PREDICTION)
    print(f"  {select_strategy(s).intent.value}")
