"""
EvalSample —— 忠实度/诊断评测集的统一样本结构（SRS 3.2 §5.2 的落地实现）

为什么需要它
------------
评测集会从三个来源汇合：
  - handwritten  手工构造（尤其是 hard negatives，外部基准通常不提供）
  - mcminer      McMining 官方基准导入（正例种子，加速阶段一）
  - synthetic    LLM 生成后人工筛（可选，须防同源偏置）

不同来源的许可证、可再分发性、标签体系都不同。把 source 与 license 随样本
**逐条留存**，是为了让 license_gate() 能在发布前机械地筛掉不可再分发的样本，
而不是靠人记得住。

标签体系
--------
mc_labels 用本项目的 M1–M8；映射不上的外部类目统一落 BEYOND_M。
BEYOND_M 不是"脏数据"——它恰恰是"M1–M8 覆盖了多少、漏了多少"的量化对照，
是论文动机的一部分（见 SRS 3.2 补充 §2.2）。

category 区分正例与硬负例：
  - positive       代码确有该误区，诊断**应当**命中
  - hard_negative  代码结构像误区但完全正确，诊断**不得**命中（测 precision）
  - clean          普通正确代码

诚实边界
--------
ast_evidence 由 B 方向 visitor 自动生成，它是"我们的实现认为存在的结构证据"，
**不是**独立的 ground truth。用它核验 LLM 解释是合法的（AST 不会撒谎地描述
语法结构），但用它反过来验证 visitor 自身的正确性是循环论证——后者必须靠
独立构造的 hard negatives（B-EVAL-09）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Iterable


BEYOND_M = "beyond-M"

VALID_M_LABELS = frozenset({f"M{i}" for i in range(1, 9)} | {BEYOND_M})


class Category(str, Enum):
    POSITIVE = "positive"
    HARD_NEGATIVE = "hard_negative"
    CLEAN = "clean"


class Source(str, Enum):
    HANDWRITTEN = "handwritten"
    MCMINER = "mcminer"
    SYNTHETIC = "synthetic"


# 可再分发的许可证白名单。不在名单内的样本 → 仅本地评测，不进公开发布集。
# 注意：这是一个保守白名单，不是法律意见。新增条目前须人工确认。
REDISTRIBUTABLE_LICENSES = frozenset({
    "mit", "apache-2.0", "bsd-3-clause", "bsd-2-clause",
    "cc-by-4.0", "cc0-1.0", "unlicense",
})

# 明确不可再分发（但可本地评测）的常见类型
NON_REDISTRIBUTABLE_MARKERS = frozenset({
    "unknown", "", "proprietary", "research-only", "noncommercial", "cc-by-nc-4.0",
})


@dataclass
class EvalSample:
    """一条评测样本。"""

    code: str
    language: str = "python"
    mc_labels: list[str] = field(default_factory=list)
    category: str = Category.POSITIVE.value
    ast_evidence: list[str] = field(default_factory=list)
    source: str = Source.HANDWRITTEN.value
    license: str = "unknown"
    sample_id: str = ""
    gold_explanation_zh: str = ""
    origin_label: str = ""          # 外部基准的原始类目名，供审计映射决策
    notes: str = ""

    # -- 校验 ---------------------------------------------------------------

    def validate(self) -> list[str]:
        """返回问题列表；空列表 = 通过。不抛异常，便于批量导入时汇总报告。"""
        problems: list[str] = []
        if not self.code.strip():
            problems.append("code 为空")
        if self.language != "python":
            problems.append(f"language={self.language!r} 非 python")
        is_negative = self.category in (Category.HARD_NEGATIVE.value, Category.CLEAN.value)
        # 负例（正确代码）本来就没有误区标签，要求非空会把最有价值的
        # hard negative 全部丢掉。只对正例要求标签。
        if not self.mc_labels and not is_negative:
            problems.append("mc_labels 为空")
        for lb in self.mc_labels:
            if lb not in VALID_M_LABELS:
                problems.append(f"未知标签 {lb!r}")
        if self.category not in {c.value for c in Category}:
            problems.append(f"未知 category {self.category!r}")
        # 注：positive 且标签为 [beyond-M] 是允许的，但这类样本只能用于覆盖面
        # 统计，不能计入 M1–M8 的 recall（分母里没有它对应的类）。
        if is_negative and any(
            lb in VALID_M_LABELS and lb != BEYOND_M for lb in self.mc_labels
        ):
            problems.append("负例样本不应带 M 标签")
        return problems

    # -- 许可证 -------------------------------------------------------------

    def is_redistributable(self) -> bool:
        lic = (self.license or "").strip().lower()
        if lic in NON_REDISTRIBUTABLE_MARKERS:
            return False
        return lic in REDISTRIBUTABLE_LICENSES

    # -- 序列化 -------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EvalSample":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


# =============================================================================
# 集合级操作
# =============================================================================

def license_gate(samples: Iterable[EvalSample]) -> tuple[list[EvalSample], list[EvalSample]]:
    """按许可证切分：(可公开发布, 仅本地评测)。

    这个函数是一道**机械闸门**，不做判断只做过滤。判断（某许可证到底算不算
    可再分发）在 REDISTRIBUTABLE_LICENSES 白名单里，改白名单需人工评审。
    """
    public, local_only = [], []
    for s in samples:
        (public if s.is_redistributable() else local_only).append(s)
    return public, local_only


def coverage_report(samples: Iterable[EvalSample]) -> dict[str, Any]:
    """M1–M8 覆盖面对照：外部基准里有多少落进了我们的 M，多少落在 M 之外。

    这是 SRS 3.2 补充 §2.2 所说的"覆盖面对照"，可直接写进论文动机。
    """
    samples = list(samples)
    by_label: dict[str, int] = {}
    by_source: dict[str, int] = {}
    by_category: dict[str, int] = {}
    origin_of_beyond: dict[str, int] = {}

    for s in samples:
        by_source[s.source] = by_source.get(s.source, 0) + 1
        by_category[s.category] = by_category.get(s.category, 0) + 1
        for lb in s.mc_labels:
            by_label[lb] = by_label.get(lb, 0) + 1
        if BEYOND_M in s.mc_labels and s.origin_label:
            origin_of_beyond[s.origin_label] = origin_of_beyond.get(s.origin_label, 0) + 1

    total = len(samples)
    beyond = by_label.get(BEYOND_M, 0)
    within = sum(v for k, v in by_label.items() if k != BEYOND_M)
    denom = within + beyond

    return {
        "total_samples": total,
        "labels_within_M": within,
        "labels_beyond_M": beyond,
        "coverage_ratio": round(within / denom, 4) if denom else None,
        "by_label": dict(sorted(by_label.items())),
        "by_source": by_source,
        "by_category": by_category,
        # 落在 M 之外的原始类目 top 列表 —— 直接回答"我们漏了哪些误区"
        "beyond_M_origin_labels": dict(
            sorted(origin_of_beyond.items(), key=lambda kv: -kv[1])
        ),
    }


def dedup(samples: Iterable[EvalSample]) -> list[EvalSample]:
    """按规范化代码去重（跨来源可能撞样本）。保留先出现的那条。"""
    seen: set[str] = set()
    out: list[EvalSample] = []
    for s in samples:
        key = "\n".join(line.rstrip() for line in s.code.strip().splitlines())
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def save_jsonl(samples: Iterable[EvalSample], path: str | Path) -> int:
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")
            n += 1
    return n


def load_jsonl(path: str | Path) -> list[EvalSample]:
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(EvalSample.from_dict(json.loads(line)))
    return out
