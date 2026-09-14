"""
近似置信度 (Approximate Confidence) —— SRS 3.2 补充 §5 的落地实现

要解决什么
----------
现状：visitor 里散落着硬编码置信度（M4 的 0.90、M6 的 0.88、M8 的 0.65…）。
这些数字既非概率、也不可比较、更不随证据强弱变化——`while True: pass` 和
一个靠弱命名启发式勉强命中的 M6，报出来的置信度是同一个常数。

为什么不做"真置信度"
--------------------
真正的概率化置信度要对每个知识点维护掌握概率、随作答证据贝叶斯更新，
即知识追踪（KT）。KT 的瓶颈**不是模型代码**（pyKT/pyBKT 都开源），
而是真实学生答题序列——这正是本项目拿不到的数据。所以本期只做**基于证据的
近似**：不训练、不需要数据、但让置信度随证据强弱单调变化，且可解释。

方法：log-odds 累加
------------------
    logit = logit(prior) + Σ wᵢ · [证据 i 成立]
    confidence = sigmoid(logit)，再截断到 [FLOOR, CEIL]

选 log-odds 而非直接加权平均，有三个理由：
  1. 天然有界，不会加着加着超过 1；
  2. 证据的"边际贡献递减"是自动的（接近 1 时再加证据涨得慢），符合直觉；
  3. 每条证据的权重就是它的对数似然比，语义清楚，将来有标注数据时
     可以直接用逻辑回归重新拟合，而不必换掉整个框架。

**权重是先验设定的，不是拟合出来的。** 这是本模块最重要的诚实边界：
这些数字表达的是"我们相信 stderr 佐证比单通道 LLM 更有说服力"这个定性判断，
它们的**序**（ordering）是有意义的，**绝对值**没有校准过。因此：

  - 可以用它排序（哪个诊断更可信）、做阈值门控（低于 τ 不展示）；
  - 不可以宣称"置信度 0.82 意味着 82% 的概率正确"；
  - 论文里报告时必须写明未校准，或先用人工标注跑一次 calibration。

CALIBRATION TODO：拿到 ≥200 条人工标注（诊断是否正确）后，用
`fit_weights()`（见文末）以逻辑回归重估各 wᵢ，并画 reliability diagram。
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


FLOOR = 0.15   # 再弱的证据也不宣称"几乎不可能"——留出人类判断空间
CEIL = 0.95    # 永不宣称确定：AST 判据本身就有启发式成分


class Channel(str, Enum):
    """诊断通道。三个通道相互独立，一致性本身是强证据。"""
    RULE = "rule"      # 正则/报错文本匹配
    AST = "ast"        # 结构分析（B 方向 visitor）
    LLM = "llm"        # 自然语言诊断


# -----------------------------------------------------------------------------
# 权重表（先验设定，未校准；改动须记入 debug 日志）
# -----------------------------------------------------------------------------

PRIOR = 0.30  # 基线：一个孤零零的命中，先验上倾向不可信

W = {
    # 结构证据：命中的 AST 特征条数。第二条的边际贡献小于第一条。
    "ast_feature_1": 0.60,
    "ast_feature_2plus": 0.55,      # 与上一条叠加，共 1.15

    # 运行期佐证：代码真的报了与该误区一致的错。这是最硬的证据。
    "stderr_corroboration": 1.00,

    # 通道一致性：两个/三个独立通道指向同一误区
    "agree_2_channels": 0.80,
    "agree_3_channels": 1.40,       # 与上一条互斥，不叠加

    # 负证据
    "llm_only": -0.70,              # 仅 LLM 单通道：最容易幻觉
    "heuristic_only": -0.50,        # 仅靠弱启发式命中（如 M6 的函数名单）
    "exemption_near_miss": -0.35,   # 差一点就被豁免规则放过
}


@dataclass
class Evidence:
    """一次诊断所收集到的证据。字段全部可由现有 visitor 输出直接填充。"""

    misconception_id: str
    channels: set[str] = field(default_factory=set)
    ast_feature_count: int = 0
    has_stderr_corroboration: bool = False
    heuristic_only: bool = False        # 命中依赖弱信号（命名启发式等）
    exemption_near_miss: bool = False   # 豁免规则差一点点就生效

    def __post_init__(self) -> None:
        if isinstance(self.channels, (list, tuple)):
            self.channels = set(self.channels)


@dataclass
class ConfidenceResult:
    misconception_id: str
    confidence: float
    logit: float
    terms: list[tuple[str, float]]   # 每条生效证据及其贡献，供 UI/日志解释

    def explain(self) -> str:
        parts = [f"先验 {PRIOR:.2f}"]
        for name, w in self.terms:
            sign = "+" if w >= 0 else "−"
            parts.append(f"{sign}{abs(w):.2f} {name}")
        return f"{self.confidence:.2f}  ←  " + "  ".join(parts)


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def _sigmoid(x: float) -> float:
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def compute_confidence(ev: Evidence) -> ConfidenceResult:
    """把证据折成一个 [FLOOR, CEIL] 内的置信度，并保留每项贡献。"""
    terms: list[tuple[str, float]] = []
    x = _logit(PRIOR)

    # --- 结构证据 ---
    if ev.ast_feature_count >= 1:
        terms.append(("AST 结构特征≥1", W["ast_feature_1"]))
        x += W["ast_feature_1"]
    if ev.ast_feature_count >= 2:
        terms.append(("AST 结构特征≥2", W["ast_feature_2plus"]))
        x += W["ast_feature_2plus"]

    # --- 运行期佐证 ---
    if ev.has_stderr_corroboration:
        terms.append(("stderr 佐证", W["stderr_corroboration"]))
        x += W["stderr_corroboration"]

    # --- 通道一致性（互斥分支）---
    n = len(ev.channels)
    if n >= 3:
        terms.append(("三通道一致", W["agree_3_channels"]))
        x += W["agree_3_channels"]
    elif n == 2:
        terms.append(("双通道一致", W["agree_2_channels"]))
        x += W["agree_2_channels"]
    elif ev.channels == {Channel.LLM.value}:
        terms.append(("仅 LLM 单通道", W["llm_only"]))
        x += W["llm_only"]

    # --- 负证据 ---
    if ev.heuristic_only:
        terms.append(("仅弱启发式命中", W["heuristic_only"]))
        x += W["heuristic_only"]
    if ev.exemption_near_miss:
        terms.append(("接近豁免边界", W["exemption_near_miss"]))
        x += W["exemption_near_miss"]

    conf = min(CEIL, max(FLOOR, _sigmoid(x)))
    return ConfidenceResult(ev.misconception_id, round(conf, 3), round(x, 3), terms)


# -----------------------------------------------------------------------------
# 与现有 visitor 的接缝
# -----------------------------------------------------------------------------

def from_visitor_finding(finding: dict[str, Any], stderr: str = "") -> ConfidenceResult:
    """把 visitor 产出的 finding 折成置信度。

    约定 finding 里可选带这些键（visitor 侧需补充产出，见下方 TODO）：
        ast_features: list[str]   命中的结构特征描述
        heuristic_only: bool      是否仅靠弱启发式（如 M6 命名名单）命中
        exemption_near_miss: bool 是否接近豁免边界

    向后兼容：这些键不存在时按保守值处理，置信度会偏低而非偏高——
    宁可低估也不高估，与"假阳性代价更高"的取舍一致。

    TODO(B方向)：让 M1–M8 各 visitor 在 finding 里输出 ast_features 与
    heuristic_only。目前 M6 的命名启发式、M4 的形参名启发式都应置
    heuristic_only=True。
    """
    mc_id = finding.get("misconception_id", "?")
    features = finding.get("ast_features") or []
    channels = set(finding.get("channels") or [Channel.AST.value])

    corroborated = _stderr_supports(mc_id, stderr)

    ev = Evidence(
        misconception_id=mc_id,
        channels=channels,
        ast_feature_count=len(features),
        has_stderr_corroboration=corroborated,
        heuristic_only=bool(finding.get("heuristic_only", False)),
        exemption_near_miss=bool(finding.get("exemption_near_miss", False)),
    )
    return compute_confidence(ev)


# 误区 → 与之一致的运行期错误特征。只在两者**指向同一根因**时才算佐证，
# 不是"有报错就加分"——那会让任何 crash 都抬高所有诊断的置信度。
_STDERR_SIGNATURES: dict[str, tuple[str, ...]] = {
    "M1": ("SyntaxError",),
    "M3": ("'NoneType' object", "NoneType"),
    "M4": ("list indices must be integers", "TypeError: list indices"),
    "M5": ("IndexError", "list index out of range"),
    "M7": ("unsupported operand type", "can only concatenate", "invalid literal for int"),
}


def _stderr_supports(mc_id: str, stderr: str) -> bool:
    if not stderr:
        return False
    sigs = _STDERR_SIGNATURES.get(mc_id)
    if not sigs:
        return False
    return any(s in stderr for s in sigs)


# -----------------------------------------------------------------------------
# 校准入口（数据到位后启用；现在是显式的空壳，不是遗忘）
# -----------------------------------------------------------------------------

def fit_weights(labeled: list[tuple[Evidence, bool]]) -> dict[str, float]:
    """用人工标注（证据, 诊断是否正确）以逻辑回归重估权重。

    未实现：需要 ≥200 条标注且样本要覆盖各证据组合，否则拟合出的权重
    不比先验更可信。数据到位前调用它是自欺。

    实现提示：把 Evidence 转成 one-hot 特征向量（键与 W 一致），
    sklearn.linear_model.LogisticRegression(fit_intercept=True)，
    截距即 logit(PRIOR)，系数即各 wᵢ；随后用 reliability diagram 检查校准度。
    """
    raise NotImplementedError(
        "需要 ≥200 条人工标注；未标注前请继续使用先验权重，并在任何对外材料中"
        "声明置信度未经校准（见模块 docstring 的诚实边界）。"
    )
