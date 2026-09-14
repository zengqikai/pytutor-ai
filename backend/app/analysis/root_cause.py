"""
E-FR-04 · 薄根因层（默认关闭 · 数据受阻）
=========================================

在 M（症状）之上建一小组根因假设，一根多症。

本模块最重要的代码不是映射表，是**阻止映射表被当成事实使用的那道闸门**。
SRS 3.2 §4.2.4 写得很清楚：根因→症状映射是**假设，严禁写死**。可"严禁"
是一句话，代码里不落实就等于没有。因此这里的设计是：

    未经共现数据验证的假设 → activate() 拒绝激活 → 权重恒为空

想跳过验证只有一条路：显式传 `force=True` 并承担后果，而且它会打日志。
这比在注释里写"上线前须验证"有效得多——注释不会在 CI 里失败。

借鉴强度
--------
CoderAgent 是 L3（无公开仓库、评测依赖真实学习轨迹）。我们只借 ACT-R / PToT
的 why-how-where-what 认知分层作骨架。补充 II 建议：论文引用应指向 ACT-R 本身
而非 CoderAgent，因为"根因分层"是认知科学通识，记在二手论文名下引用链不准。

为什么"数据受阻"而非"没时间做"
------------------------------
判断 M3 与 M6 是否真的同根（"值不会自动留存"），需要看它们在真实学生提交里
是否显著共现。没有真实数据，这个映射就只是一个听起来合理的故事。而一个错误的
"根因"会误导教学——它会让系统对一个根本没犯 M6 的学生大谈 return 语义。
"""

from __future__ import annotations

import logging
import math
import os
from dataclasses import dataclass
from typing import Iterable

logger = logging.getLogger(__name__)


FLAG_ENV = "ENABLE_ROOT_CAUSE_LAYER"

# 假设映射（NOT hardcoded truth）—— 上线前须经共现数据确认
ROOT_CAUSE_HYPOTHESES: dict[str, list[str]] = {
    "value_not_auto_retained": ["M3", "M6"],   # "值不会自动留存"
    "off_by_boundary": ["M4", "M5"],           # 计数边界偏差
    "state_over_loop": ["M8"],                 # 循环状态演化
}

# 验证阈值。lift > 1 表示共现高于独立假设下的期望；support 保证不是小样本巧合。
MIN_LIFT = 1.5
MIN_SUPPORT = 20      # 至少 20 次共现才谈得上统计意义
MIN_SAMPLES = 200     # 总样本量下限


@dataclass(frozen=True)
class ValidationVerdict:
    root_cause: str
    validated: bool
    lift: float | None
    support: int
    reason: str


def _lift(co: int, a: int, b: int, n: int) -> float | None:
    """lift = P(A∧B) / (P(A)·P(B))。单症状根因无需 lift（无共现可言）。"""
    if n == 0 or a == 0 or b == 0:
        return None
    p_ab = co / n
    return p_ab / ((a / n) * (b / n))


def validate_hypotheses(
    cooccurrence: dict[tuple[str, str], int],
    marginal: dict[str, int],
    n_samples: int,
) -> list[ValidationVerdict]:
    """用真实共现数据检验每条根因假设。

    参数：
        cooccurrence  {(M_i, M_j): 同一次提交中共同出现的次数}，键无序需归一
        marginal      {M_i: 出现总次数}
        n_samples     总提交数

    单症状假设（如 state_over_loop → [M8]）无共现可验，视为**结构性成立**
    ——它不主张任何两个症状同根，因此没有可被证伪的内容。这不是放水，
    是它本来就没做出统计断言。
    """
    verdicts: list[ValidationVerdict] = []

    if n_samples < MIN_SAMPLES:
        for rc in ROOT_CAUSE_HYPOTHESES:
            verdicts.append(ValidationVerdict(
                rc, False, None, 0,
                f"总样本 {n_samples} < {MIN_SAMPLES}，不足以验证任何假设"))
        return verdicts

    for rc, symptoms in ROOT_CAUSE_HYPOTHESES.items():
        if len(symptoms) == 1:
            verdicts.append(ValidationVerdict(
                rc, True, None, marginal.get(symptoms[0], 0),
                "单症状假设，未主张共现，结构性成立"))
            continue

        # 多症状：要求**每一对**都通过，而非平均通过。
        # 三个症状里两个同根、一个不同根，整条假设就是错的。
        pair_results = []
        for i in range(len(symptoms)):
            for j in range(i + 1, len(symptoms)):
                a, b = sorted((symptoms[i], symptoms[j]))
                co = cooccurrence.get((a, b), 0)
                lf = _lift(co, marginal.get(a, 0), marginal.get(b, 0), n_samples)
                pair_results.append((a, b, co, lf))

        failed = [
            f"{a}∧{b}: support={co}, lift={lf if lf is None else round(lf, 2)}"
            for a, b, co, lf in pair_results
            if co < MIN_SUPPORT or lf is None or lf < MIN_LIFT
        ]
        min_support = min(co for _, _, co, _ in pair_results)
        lifts = [lf for *_, lf in pair_results if lf is not None]
        min_lift = min(lifts) if lifts else None

        if failed:
            verdicts.append(ValidationVerdict(
                rc, False, min_lift, min_support,
                "未通过的症状对：" + "；".join(failed)))
        else:
            verdicts.append(ValidationVerdict(
                rc, True, min_lift, min_support, "全部症状对通过 lift/support 阈值"))

    return verdicts


# =============================================================================
# 激活闸门
# =============================================================================

_ACTIVE: dict[str, list[str]] = {}


def is_enabled() -> bool:
    return os.environ.get(FLAG_ENV, "").lower() in ("1", "true", "yes")


def activate(verdicts: Iterable[ValidationVerdict], force: bool = False) -> dict[str, list[str]]:
    """只把**通过验证**的假设装进活跃映射。

    force=True 会装入全部假设，但记 WARNING。它存在的意义是让"跳过验证"这件事
    在日志里留下痕迹，而不是让它变得不可能——评测环境有时需要跑未验证的映射。
    """
    global _ACTIVE
    if not is_enabled():
        _ACTIVE = {}
        return _ACTIVE

    if force:
        logger.warning(
            "root_cause: force=True，装入未经验证的根因映射。"
            "错误的根因会误导教学，请勿在生产开启。")
        _ACTIVE = dict(ROOT_CAUSE_HYPOTHESES)
        return _ACTIVE

    _ACTIVE = {
        v.root_cause: ROOT_CAUSE_HYPOTHESES[v.root_cause]
        for v in verdicts if v.validated
    }
    rejected = [v.root_cause for v in verdicts if not v.validated]
    if rejected:
        logger.info("root_cause: 未通过验证，已排除 %s", rejected)
    return _ACTIVE


def compute_weights(active_misconceptions: list[str]) -> dict[str, float]:
    """把命中的症状折成根因权重。Flag 关闭或无验证通过的映射时返回空 dict
    ——对现有诊断零影响（E-FR-04 验收判定）。

    权重 = 该根因下被命中的症状数 / 该根因的症状总数。
    这是一个刻意朴素的定义：在映射本身尚未被数据验证之前，
    给权重设计一个精巧的公式是在错误的地基上盖楼。
    """
    if not is_enabled() or not _ACTIVE:
        return {}
    hit = set(active_misconceptions)
    out: dict[str, float] = {}
    for rc, symptoms in _ACTIVE.items():
        k = len(hit & set(symptoms))
        if k:
            out[rc] = round(k / len(symptoms), 3)
    return out


def reset() -> None:
    """测试用。"""
    global _ACTIVE
    _ACTIVE = {}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    print("== Flag 关闭时（默认）==")
    print("  weights =", compute_weights(["M3", "M6"]), "← 对现有诊断零影响")

    os.environ[FLAG_ENV] = "true"

    print("\n== 样本不足，全部拒绝激活 ==")
    vs = validate_hypotheses({}, {}, n_samples=50)
    activate(vs)
    print("  weights =", compute_weights(["M3", "M6"]))

    print("\n== 有数据：M3∧M6 显著共现，M4∧M5 不共现 ==")
    n = 1000
    marginal = {"M3": 200, "M6": 180, "M4": 150, "M5": 140}
    co = {("M3", "M6"): 90, ("M4", "M5"): 5}
    vs = validate_hypotheses(co, marginal, n)
    for v in vs:
        mark = "✓" if v.validated else "✗"
        print(f"  {mark} {v.root_cause:26} {v.reason}")
    activate(vs)
    print("  weights(M3,M6) =", compute_weights(["M3", "M6"]))
    print("  weights(M4,M5) =", compute_weights(["M4", "M5"]), "← 假设被数据否决")
