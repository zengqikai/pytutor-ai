"""
忠实度核验器 (Faithfulness Verifier)
=====================================

研究方向 R2 的核心方法实现：给定 (学生代码, LLM 误区解释)，
自动把解释拆成原子断言 (claim)，逐条对 AST 事实集核验，产出忠实度指标。

指标定义
--------
    Faithfulness = #{被 AST 事实支持的可核验断言} / #{全部可核验断言}

    每个断言被分为三类：
      SUPPORTED     —— AST 事实集里能找到对应客观事实（忠实）
      UNSUPPORTED   —— 可核验但 AST 里没有 → 幻觉 (hallucination)
      UNVERIFIABLE  —— 关于"学生意图/教学建议"等，AST 无法证实也无法证伪
                       （如实划出，不计入忠实度分母，论文里单独报告）

设计取舍（诚实边界）
------------------
断言拆分本身可以用 LLM，会引入误差，因此本模块提供两种拆分器：
  1. RuleBasedClaimExtractor —— 纯离线、确定性，用于自动化基准与 CI；
     覆盖误区解释里最常见的可核验断言模式（行号+结构谓词）。
  2. llm_extract_claims()（可选钩子）—— 真实实验用，需外部注入一个
     callable(prompt)->str；生成模型与被测模型必须分离以防同源偏置。

核验器只依赖 ast_facts.extract_facts()，完全离线可复现。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional

from ast_facts import Fact, extract_facts, INPLACE_METHODS


class Verdict(str, Enum):
    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"        # 幻觉
    UNVERIFIABLE = "unverifiable"      # 意图/建议类，不计入分母


@dataclass
class Claim:
    text: str
    predicate: str                     # 归一化后的谓词类型
    args: dict = field(default_factory=dict)
    line: Optional[int] = None


@dataclass
class ClaimVerdict:
    claim: Claim
    verdict: Verdict
    matched_fact: Optional[str] = None
    reason: str = ""


@dataclass
class FaithfulnessReport:
    total_claims: int
    verifiable: int
    supported: int
    unsupported: int
    unverifiable: int
    # 零可核验断言时两者为 None——不能把"没说话"当成"说对了"
    faithfulness: Optional[float]      # supported / verifiable
    hallucination_rate: Optional[float]  # unsupported / verifiable
    details: list[ClaimVerdict] = field(default_factory=list)

    @property
    def has_verifiable(self) -> bool:
        return self.verifiable > 0

    def summary(self) -> str:
        if not self.has_verifiable:
            return (f"忠实度=N/A  幻觉率=N/A  (无可核验断言；"
                    f"不可核验 {self.unverifiable})")
        return (
            f"忠实度={self.faithfulness:.2f}  幻觉率={self.hallucination_rate:.2f}  "
            f"(可核验 {self.verifiable} = 支持 {self.supported} + 幻觉 {self.unsupported}; "
            f"不可核验 {self.unverifiable})"
        )


# =============================================================================
# 1. 规则式断言抽取器（离线基准 / CI）
# =============================================================================

class RuleBasedClaimExtractor:
    """把一段中文误区解释切成原子断言。

    覆盖的可核验断言模式（正则驱动，确定性）：
      - 行号引用：       "第 N 行"
      - in-place 返回：  "append/sort/... 返回 None / 返回值"
      - print≠return：   "只 print / 没有 return / 缺少 return"
      - value-as-index： "循环变量当索引 / 当下标"
      - range 半开：     "range 左闭右开 / 不包含 / 不含"
      - 类型错误：       "input 返回字符串 / str 和 int / 类型不匹配"
      - while 无限：     "无限循环 / 条件变量未更新"
    不可核验断言（意图/建议）用启发式识别，标 UNVERIFIABLE。
    """

    # 意图/建议类关键词 → 不可核验
    _INTENT_MARKERS = [
        "建议", "应该", "推荐", "可以尝试", "下一步", "学生可能想",
        "学生以为", "学生期望", "为了", "帮助你", "记住", "注意",
    ]

    _LINE_RE = re.compile(r"第\s*(\d+)\s*行")
    _FENCE_RE = re.compile(r"```[^\n]*\n.*?```", re.S)
    _HEADING_RE = re.compile(r"^#{1,6}\s+.*$")
    _HR_RE = re.compile(r"^([-*_])\s*(\1\s*){2,}$")
    _LIST_RE = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
    _BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
    _TAG_RE = re.compile(r"<[^>]+>")

    def extract(self, explanation: str) -> list[Claim]:
        claims: list[Claim] = []
        text = self._clean_markdown(explanation)
        # 按句切分：中文句读 + 换行 + 英文句末（后接空白）
        sentences = re.split(r"[。；\n！？]|(?<=[.!?])\s+", text)
        for s in sentences:
            s = s.strip().strip("-*>#` ")
            if not self._is_claim_like(s):
                continue
            # "看这段代码：" 之类的引导句不是断言
            if len(s) < 12 and s.endswith(("：", ":")):
                continue
            claims.extend(self._classify_sentence(s))
        return claims

    @classmethod
    def _clean_markdown(cls, explanation: str) -> str:
        """去掉纯排版内容，避免把标题/代码块/表格当成断言。

        代码块整体丢弃；行内代码只去反引号，保留代码词（``append`` 仍是可核验线索）。
        """
        text = cls._FENCE_RE.sub("\n", explanation)
        text = text.replace("`", "")
        kept: list[str] = []
        for raw in text.splitlines():
            line = raw.strip()
            if not line:
                continue
            # 表格（有无前导竖线都跳过）与分隔行
            if line.startswith("|") or line.count("|") >= 2:
                continue
            if cls._HEADING_RE.match(line) or cls._HR_RE.match(line):
                continue
            line = re.sub(r"^>\s?", "", line)
            line = cls._LIST_RE.sub("", line)
            line = cls._BOLD_RE.sub(r"\1", line)
            line = cls._TAG_RE.sub("", line)
            line = line.strip()
            if line:
                kept.append(line)
        return "\n".join(kept)

    @staticmethod
    def _is_claim_like(s: str) -> bool:
        """过滤空句、纯符号和过短片段（如 ``e.g``、单个列表符号）。"""
        if len(s) < 4:
            return False
        return bool(re.search(r"[\w一-鿿]", s))

    def _classify_sentence(self, s: str) -> list[Claim]:
        out: list[Claim] = []
        line_m = self._LINE_RE.search(s)
        line = int(line_m.group(1)) if line_m else None

        # 意图/建议类 → 不可核验（优先判定，避免和结构断言混淆）
        if any(k in s for k in self._INTENT_MARKERS) and not self._has_structural_signal(s):
            out.append(Claim(text=s, predicate="intent_or_advice", line=line))
            return out

        # in-place 方法返回 None
        m = re.search(r"(append|extend|insert|remove|sort|reverse|clear|update|add|discard)\b", s)
        if m and ("返回" in s and ("None" in s or "空" in s or "值" in s)):
            out.append(Claim(text=s, predicate="inplace_returns_none",
                             args={"method": m.group(1)}, line=line))
            return out

        # 把方法返回值赋给变量
        if m and ("赋" in s or "赋给" in s or "赋值" in s):
            out.append(Claim(text=s, predicate="assign_call_result",
                             args={"method": m.group(1)}, line=line))
            return out

        # print / return 混淆
        if ("print" in s and "return" in s) or ("没有 return" in s) or ("缺少 return" in s) \
                or ("只" in s and "print" in s):
            out.append(Claim(text=s, predicate="print_not_return", line=line))
            return out

        # value 当 index
        if ("循环变量" in s or "遍历" in s) and ("索引" in s or "下标" in s):
            out.append(Claim(text=s, predicate="value_as_index", line=line))
            return out

        # range 半开区间
        if "range" in s and ("左闭右开" in s or "不包含" in s or "不含" in s or "不包括" in s):
            out.append(Claim(text=s, predicate="range_half_open", line=line))
            return out

        # 类型转换 / str+int
        if ("input" in s and ("字符串" in s or "str" in s)) \
                or ("类型" in s and ("转换" in s or "不匹配" in s or "错误" in s)) \
                or ("字符串" in s and ("数值" in s or "整数" in s or "int" in s)):
            out.append(Claim(text=s, predicate="type_mismatch", line=line))
            return out

        # while 无限循环
        if "无限循环" in s or ("条件变量" in s and ("未更新" in s or "没更新" in s)):
            out.append(Claim(text=s, predicate="infinite_loop", line=line))
            return out

        # 其余：若含行号或结构词，当作"泛结构断言"（可核验但需要行号对上）；
        # 否则视为不可核验的自然语言修饰。
        if line is not None or self._has_structural_signal(s):
            out.append(Claim(text=s, predicate="generic_structural", line=line))
        else:
            out.append(Claim(text=s, predicate="intent_or_advice", line=line))
        return out

    @staticmethod
    def _has_structural_signal(s: str) -> bool:
        return any(k in s for k in
                   ["print", "return", "append", "range", "for", "while",
                    "input", "索引", "下标", "赋值", "循环", "函数"])


# =============================================================================
# 2. 核验器：断言 × 事实集 → 裁决
# =============================================================================

class FaithfulnessVerifier:
    def __init__(self, code: str):
        self.code = code
        self.facts: list[Fact] = extract_facts(code)
        self._by_kind: dict[str, list[Fact]] = {}
        for f in self.facts:
            self._by_kind.setdefault(f.kind, []).append(f)

    def _facts(self, kind: str) -> list[Fact]:
        return self._by_kind.get(kind, [])

    def verify_claim(self, claim: Claim) -> ClaimVerdict:
        p = claim.predicate

        if p == "intent_or_advice":
            return ClaimVerdict(claim, Verdict.UNVERIFIABLE,
                                reason="关于学生意图/教学建议，AST 无法证实或证伪")

        if p in ("inplace_returns_none", "assign_call_result"):
            method = claim.args.get("method")
            # 事实集里是否有对该 in-place 方法返回值的赋值 / 调用
            for f in self._facts("assign_call_result"):
                if f.get("method") == method and f.get("is_inplace"):
                    if claim.line is None or claim.line == f.line:
                        return ClaimVerdict(claim, Verdict.SUPPORTED, f.describe())
            # 至少存在该方法调用（返回 None 是语言事实）
            for f in self._facts("method_call"):
                if f.get("method") == method and method in INPLACE_METHODS:
                    if claim.line is None or claim.line == f.line:
                        return ClaimVerdict(claim, Verdict.SUPPORTED, f.describe(),
                                            reason="代码确有该 in-place 方法调用")
            return ClaimVerdict(claim, Verdict.UNSUPPORTED,
                                reason=f"代码中找不到对 {method}() 的相应用法（幻觉）")

        if p == "print_not_return":
            for f in self._facts("func_def"):
                if f.get("has_return") is False:
                    # 该函数体里确有 print？
                    has_print = any(pf.line >= f.line for pf in self._facts("print_call"))
                    if has_print:
                        return ClaimVerdict(claim, Verdict.SUPPORTED, f.describe())
            return ClaimVerdict(claim, Verdict.UNSUPPORTED,
                                reason="没有'有 print 且无 return'的函数（幻觉）")

        if p == "value_as_index":
            # 存在 for x in it 且体内 it[x]
            fors = self._facts("for_loop")
            subs = self._facts("subscript")
            for fo in fors:
                tgt = fo.get("target")
                it = fo.get("iterable")
                for su in subs:
                    if su.get("container") == it and su.get("index") == tgt:
                        return ClaimVerdict(claim, Verdict.SUPPORTED, su.describe())
            return ClaimVerdict(claim, Verdict.UNSUPPORTED,
                                reason="代码中不存在'循环变量当下标'的结构（幻觉）")

        if p == "range_half_open":
            if self._facts("range_call"):
                return ClaimVerdict(claim, Verdict.SUPPORTED,
                                    self._facts("range_call")[0].describe())
            return ClaimVerdict(claim, Verdict.UNSUPPORTED,
                                reason="代码里没有 range() 调用（幻觉）")

        if p == "type_mismatch":
            # "存在二元运算" 不等于 "类型不匹配"。只有推断出 str 与 num
            # 相混时才算支持；两侧类型一致算反驳；推断不出则不可核验。
            binops = self._facts("binop")
            if not binops:
                return ClaimVerdict(claim, Verdict.UNSUPPORTED,
                                    reason="代码里没有二元运算（幻觉）")
            for f in binops:
                if f.get("definite_type_error"):
                    return ClaimVerdict(claim, Verdict.SUPPORTED, f.describe(),
                                        reason=f"{f.get('left_kind')} 与 {f.get('right_kind')} 相加")
            kinds = {(f.get("left_kind"), f.get("right_kind")) for f in binops}
            if all(l == r and l in ("str", "num") for l, r in kinds):
                return ClaimVerdict(claim, Verdict.UNSUPPORTED,
                                    reason="运算两侧类型一致，不构成类型错误（幻觉）")
            return ClaimVerdict(claim, Verdict.UNVERIFIABLE,
                                reason="无法从代码结构确定操作数类型")

        if p == "infinite_loop":
            # "有 while" 不等于 "无限循环"：条件变量在体内更新、或存在
            # break/return/raise 出口时，不能把该断言判为支持。
            whiles = self._facts("while_loop")
            if not whiles:
                return ClaimVerdict(claim, Verdict.UNSUPPORTED,
                                    reason="代码里没有 while 循环（幻觉）")
            for f in whiles:
                if f.get("may_never_terminate"):
                    return ClaimVerdict(claim, Verdict.SUPPORTED, f.describe(),
                                        reason="条件变量在循环体内从不更新且无出口")
            return ClaimVerdict(claim, Verdict.UNSUPPORTED,
                                reason="while 条件变量在体内有更新或存在出口（幻觉）")

        if p == "generic_structural":
            # 有行号 → 该行是否存在任何事实
            if claim.line is not None:
                if any(f.line == claim.line for f in self.facts):
                    return ClaimVerdict(claim, Verdict.SUPPORTED,
                                        reason=f"第 {claim.line} 行确有代码结构")
                return ClaimVerdict(claim, Verdict.UNSUPPORTED,
                                    reason=f"第 {claim.line} 行在代码中不存在对应结构（行号幻觉）")
            return ClaimVerdict(claim, Verdict.UNVERIFIABLE,
                                reason="泛结构断言但无行号，无法精确核验")

        return ClaimVerdict(claim, Verdict.UNVERIFIABLE, reason="未知谓词")

    def verify(self, explanation: str,
               extractor: Optional[RuleBasedClaimExtractor] = None) -> FaithfulnessReport:
        extractor = extractor or RuleBasedClaimExtractor()
        claims = extractor.extract(explanation)
        verdicts = [self.verify_claim(c) for c in claims]

        supported = sum(1 for v in verdicts if v.verdict == Verdict.SUPPORTED)
        unsupported = sum(1 for v in verdicts if v.verdict == Verdict.UNSUPPORTED)
        unverifiable = sum(1 for v in verdicts if v.verdict == Verdict.UNVERIFIABLE)
        verifiable = supported + unsupported
        # 没有可核验断言 ≠ 100% 忠实。返回 None，由聚合层单独报告覆盖率。
        faith = round(supported / verifiable, 3) if verifiable else None
        halluc = round(unsupported / verifiable, 3) if verifiable else None

        return FaithfulnessReport(
            total_claims=len(claims), verifiable=verifiable,
            supported=supported, unsupported=unsupported, unverifiable=unverifiable,
            faithfulness=faith, hallucination_rate=halluc,
            details=verdicts,
        )


# =============================================================================
# 3. LLM 抽取钩子（真实实验用，可选）
# =============================================================================

def llm_extract_claims(explanation: str,
                       llm_call: Callable[[str], str]) -> list[Claim]:
    """用外部 LLM 把解释拆成原子断言（真实实验路径）。

    llm_call: 注入的可调用对象，输入 prompt，返回文本。生成模型必须与
    被评测的解释模型分离，以避免同源偏置（见 R2 风险对策）。
    """
    prompt = (
        "把下面这段对学生代码的误区解释，拆成一条一条的原子事实断言，"
        "每行一条，只保留关于代码结构的可核验陈述，去掉建议和鼓励语：\n\n"
        + explanation
    )
    raw = llm_call(prompt)
    ext = RuleBasedClaimExtractor()
    claims: list[Claim] = []
    for line in raw.splitlines():
        line = line.strip("-• \t")
        if line:
            claims.extend(ext._classify_sentence(line))
    return claims


if __name__ == "__main__":
    code = "items = []\nnew = items.append(5)\nfor i in items:\n    print(items[i])"

    # 一条"忠实"解释
    good = ("第 2 行把 append() 的返回值赋给了 new，而 append 返回 None。"
            "第 4 行循环变量 i 被当作下标使用。建议改用直接遍历元素。")
    # 一条"含幻觉"解释（编造了不存在的 range 和第 9 行）
    bad = ("第 2 行 append 返回 None。第 9 行使用了 range 左闭右开区间导致越界。"
           "代码里的 while 循环是无限循环。")

    v = FaithfulnessVerifier(code)
    for label, exp in [("忠实解释", good), ("含幻觉解释", bad)]:
        rep = v.verify(exp)
        print(f"\n=== {label} ===")
        print(rep.summary())
        for d in rep.details:
            print(f"  [{d.verdict.value:12}] {d.claim.text[:40]}  — {d.reason or d.matched_fact}")
