"""
忠实度核验器回归测试（task 10）
==============================

这些用例守护"量尺本身"：核验器不能再把
- 合法的字符串重复运算当成类型错误，
- 会收敛的 while 循环当成无限循环，
- 零可核验断言当成满分。

研究代码在 research/faithfulness/，只依赖标准库，因此可以直接在
后端测试环境里跑。
"""

import sys
from pathlib import Path

import pytest

RESEARCH_DIR = Path(__file__).resolve().parents[2] / "research" / "faithfulness"
sys.path.insert(0, str(RESEARCH_DIR))

from ast_facts import extract_facts  # noqa: E402
from faithfulness_verifier import FaithfulnessVerifier, RuleBasedClaimExtractor  # noqa: E402

TYPE_CLAIM = "这段代码有类型不匹配的错误。"
LOOP_CLAIM = "这里的 while 循环会无限循环。"


def verdict_for(code: str, claim: str) -> str:
    report = FaithfulnessVerifier(code).verify(claim)
    assert report.details, "断言应被抽取出来"
    return report.details[0].verdict.value


class TestTypeMismatchRule:
    def test_legal_string_repetition_is_not_supported(self):
        """'hello ' + name * 3 是合法的，不能判成类型错误（v0.1 的假阳性）。"""
        code = "name = input()\nprint('hello ' + name * 3)"
        assert verdict_for(code, TYPE_CLAIM) != "supported"

    def test_pure_numeric_arithmetic_rejected(self):
        code = "a = 1\nb = 2\nprint(a + b)"
        assert verdict_for(code, TYPE_CLAIM) == "unsupported"

    def test_real_str_int_addition_supported(self):
        code = "x = input()\nprint(x + 3)"
        assert verdict_for(code, TYPE_CLAIM) == "supported"

    def test_unknown_operand_types_are_unverifiable(self):
        """推断不出类型时既不能证实也不能证伪。"""
        code = "def f(a, b):\n    return a + b"
        assert verdict_for(code, TYPE_CLAIM) == "unverifiable"

    def test_same_name_in_other_scope_does_not_leak(self):
        """模块级的字符串 x 不能污染函数里同名的数值 x。"""
        code = "x = 'text'\ndef f():\n    x = 1\n    return x + 2"
        assert verdict_for(code, TYPE_CLAIM) == "unsupported"


class TestInfiniteLoopRule:
    def test_converging_while_is_not_supported(self):
        code = "i = 0\nwhile i < 5:\n    print(i)\n    i += 1"
        assert verdict_for(code, LOOP_CLAIM) == "unsupported"

    def test_while_true_with_break_is_not_supported(self):
        code = "while True:\n    break"
        assert verdict_for(code, LOOP_CLAIM) == "unsupported"

    def test_never_updated_condition_supported(self):
        code = "i = 0\nwhile i < 5:\n    print(i)"
        assert verdict_for(code, LOOP_CLAIM) == "supported"

    def test_no_while_rejected(self):
        assert verdict_for("print(1)", LOOP_CLAIM) == "unsupported"


class TestZeroVerifiableIsNotPerfect:
    def test_no_claims_yields_none_not_one(self):
        report = FaithfulnessVerifier("print(1)").verify("建议多练习。")
        assert report.verifiable == 0
        assert report.faithfulness is None
        assert report.hallucination_rate is None
        assert "N/A" in report.summary()

    def test_coverage_reported_in_experiment(self):
        """run_experiment 的 summary 必须给出 claim_coverage 和配对差值。"""
        import run_experiment

        result = run_experiment.run(
            str(RESEARCH_DIR / "dataset_seed.json"),
            run_experiment._stub_llm,
        )
        for cond in ("C1", "C2"):
            assert "claim_coverage" in result["summary"][cond]
            assert 0.0 <= result["summary"][cond]["claim_coverage"] <= 1.0
        assert result["meta"]["dataset_sha256_16"]
        assert result["meta"]["model"] == "stub" or result["meta"]["model"]


class TestMarkdownIsNotAClaim:
    """extractor v2：标题、代码块、表格不该进入断言流。"""

    def extract(self, text):
        return RuleBasedClaimExtractor().extract(text)

    def test_headings_and_table_rows_are_dropped(self):
        text = (
            "## 问题分析\n"
            "| 指标 | 值 |\n"
            "|---|---|\n"
            "| 行号 | 2 |\n"
            "第 2 行的 append 返回 None。"
        )
        claims = self.extract(text)
        assert [c.text for c in claims] == ["第 2 行的 append 返回 None"]
        assert claims[0].predicate == "inplace_returns_none"

    def test_fenced_code_block_is_dropped(self):
        text = "看这段代码：\n```python\nprint('hello')\n```\n它只 print 没有 return。"
        claims = self.extract(text)
        assert len(claims) == 1
        assert "print('hello')" not in claims[0].text
        assert claims[0].predicate == "print_not_return"

    def test_inline_code_is_kept_as_text(self):
        claims = self.extract("`append` 没有返回值。")
        assert claims
        assert "append" in claims[0].text
        assert "`" not in claims[0].text

    def test_bullets_and_bold_markers_are_stripped(self):
        claims = self.extract("- **第 3 行** 的循环变量被当成索引。")
        assert claims
        assert "**" not in claims[0].text
        assert claims[0].predicate == "value_as_index"

    def test_english_sentence_boundary_splits_claims(self):
        claims = self.extract("Line 2 is wrong. The loop variable is used as an index.")
        texts = [c.text for c in claims]
        assert len(texts) == 2
        assert texts[0].startswith("Line 2") and "wrong" in texts[0]
        assert texts[1].startswith("The loop")
