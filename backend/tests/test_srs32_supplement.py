"""
SRS 3.2 补充件实现的单元测试
============================

覆盖四块可离线自证的逻辑：
  1. confidence.py  —— 置信度的**序性**与边界（绝对值未校准，只测序）
  2. eval_sample.py —— schema 校验、许可证闸门、覆盖面统计
  3. mcmining_import.py —— 类目映射、正确代码 → hard_negative
  4. misconception_anchored.py —— 答案泄露检测、低置信度改变语气

不覆盖的（因为无法离线自证，见各文件的"本地对齐点"）：
  - TRAVER 脚本的真实调用签名
  - McMining 数据的真实字段名
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# faithfulness 数据基建已并入仓库根的 research/faithfulness（2026-07-26 合并）
sys.path.insert(0, str(ROOT.parent))

from app.analysis.confidence import (  # noqa: E402
    CEIL, FLOOR, Channel, Evidence, compute_confidence, from_visitor_finding,
)
from app.services.prompts.misconception_anchored import (  # noqa: E402
    build_system_prompt, leaks_answer,
)
from research.faithfulness.eval_sample import (  # noqa: E402
    BEYOND_M, Category, EvalSample, Source, coverage_report, dedup, license_gate,
)
from research.faithfulness.mcmining_import import map_or_beyond  # noqa: E402


# =============================================================================
# 1. 置信度
# =============================================================================

class TestConfidence:
    def test_bounds_never_exceeded(self):
        strong = Evidence("M3", channels={"rule", "ast", "llm"},
                          ast_feature_count=5, has_stderr_corroboration=True)
        weak = Evidence("M6", channels={"llm"}, ast_feature_count=0,
                        heuristic_only=True, exemption_near_miss=True)
        assert compute_confidence(strong).confidence <= CEIL
        assert compute_confidence(weak).confidence >= FLOOR

    def test_stderr_beats_llm_only(self):
        """有运行期佐证的诊断，必须比仅 LLM 单通道更可信。"""
        with_err = Evidence("M3", channels={"ast"}, ast_feature_count=1,
                            has_stderr_corroboration=True)
        llm_only = Evidence("M3", channels={"llm"})
        assert compute_confidence(with_err).confidence > compute_confidence(llm_only).confidence

    def test_more_features_monotonic(self):
        a = Evidence("M4", channels={"ast"}, ast_feature_count=1)
        b = Evidence("M4", channels={"ast"}, ast_feature_count=2)
        assert compute_confidence(b).confidence > compute_confidence(a).confidence

    def test_three_channels_beat_two(self):
        two = Evidence("M1", channels={"ast", "rule"})
        three = Evidence("M1", channels={"ast", "rule", "llm"})
        assert compute_confidence(three).confidence > compute_confidence(two).confidence

    def test_heuristic_only_penalized(self):
        """M6 靠函数名单勉强命中时，置信度必须低于结构证据命中。"""
        structural = Evidence("M6", channels={"ast"}, ast_feature_count=2)
        naming = Evidence("M6", channels={"ast"}, ast_feature_count=1, heuristic_only=True)
        assert compute_confidence(naming).confidence < compute_confidence(structural).confidence

    def test_explain_lists_terms(self):
        r = compute_confidence(Evidence("M3", channels={"ast"}, ast_feature_count=1,
                                        has_stderr_corroboration=True))
        assert "stderr 佐证" in r.explain()
        assert len(r.terms) >= 2

    def test_stderr_signature_must_match_misconception(self):
        """任意报错不该抬高任意诊断的置信度——只有指向同一根因的才算佐证。"""
        finding = {"misconception_id": "M3", "ast_features": ["f1"], "channels": ["ast"]}
        matched = from_visitor_finding(finding, stderr="AttributeError: 'NoneType' object ...")
        mismatched = from_visitor_finding(finding, stderr="ZeroDivisionError: division by zero")
        assert matched.confidence > mismatched.confidence

    def test_missing_keys_degrade_conservatively(self):
        """finding 缺字段时应偏低而非偏高（假阳性代价更高）。"""
        bare = from_visitor_finding({"misconception_id": "M4"})
        rich = from_visitor_finding(
            {"misconception_id": "M4", "ast_features": ["a", "b"], "channels": ["ast", "rule"]})
        assert bare.confidence < rich.confidence


# =============================================================================
# 2. EvalSample
# =============================================================================

class TestEvalSample:
    def test_validate_rejects_bad_label(self):
        s = EvalSample(code="x=1", mc_labels=["M99"])
        assert any("未知标签" in p for p in s.validate())

    def test_validate_rejects_non_python(self):
        s = EvalSample(code="int x=1;", language="java", mc_labels=["M1"])
        assert any("非 python" in p for p in s.validate())

    def test_negative_sample_must_not_carry_m_label(self):
        s = EvalSample(code="d={}\nfor k in d: print(d[k])",
                       mc_labels=["M4"], category=Category.HARD_NEGATIVE.value)
        assert any("负例样本" in p for p in s.validate())

    def test_hard_negative_with_empty_labels_is_valid(self):
        """回归：负例不带 mc_labels 是正常的，早期实现把它当校验失败丢弃了，
        而 hard negative 恰恰是外部基准最稀缺、本项目最需要的样本类型。"""
        s = EvalSample(code="d={'a':1}\nfor k in d: print(d[k])",
                       mc_labels=[], category=Category.HARD_NEGATIVE.value)
        assert s.validate() == []

    def test_license_gate_splits(self):
        ok = EvalSample(code="a=1", mc_labels=["M1"], license="MIT")
        bad = EvalSample(code="b=2", mc_labels=["M1"], license="unknown")
        nc = EvalSample(code="c=3", mc_labels=["M1"], license="CC-BY-NC-4.0")
        public, local = license_gate([ok, bad, nc])
        assert len(public) == 1 and len(local) == 2

    def test_coverage_report_counts_beyond_m(self):
        samples = [
            EvalSample(code="a=1", mc_labels=["M3"], source=Source.MCMINER.value),
            EvalSample(code="b=2", mc_labels=[BEYOND_M],
                       source=Source.MCMINER.value, origin_label="closure_late_binding"),
            EvalSample(code="c=3", mc_labels=[BEYOND_M],
                       source=Source.MCMINER.value, origin_label="closure_late_binding"),
        ]
        rep = coverage_report(samples)
        assert rep["labels_beyond_M"] == 2
        assert rep["labels_within_M"] == 1
        # coverage_ratio 报告到 4 位小数，容差随之
        assert abs(rep["coverage_ratio"] - 1 / 3) < 1e-3
        assert rep["beyond_M_origin_labels"]["closure_late_binding"] == 2

    def test_dedup_normalizes_trailing_space(self):
        a = EvalSample(code="x = 1  \ny = 2", mc_labels=["M1"])
        b = EvalSample(code="x = 1\ny = 2", mc_labels=["M1"])
        assert len(dedup([a, b])) == 1


# =============================================================================
# 3. McMining 映射
# =============================================================================

class TestMcMiningMapping:
    def test_known_category_maps(self):
        assert map_or_beyond("append_returns_none") == "M3"
        assert map_or_beyond("print_vs_return") == "M6"

    def test_case_and_separator_insensitive(self):
        assert map_or_beyond("Append-Returns-None") == "M3"
        assert map_or_beyond("print vs return") == "M6"

    def test_unknown_goes_beyond_m(self):
        assert map_or_beyond("closure_late_binding") == BEYOND_M
        assert map_or_beyond("") == BEYOND_M


# =============================================================================
# 4. 误区锚定 prompt
# =============================================================================

class TestMisconceptionAnchoredPrompt:
    def test_low_confidence_changes_stance(self):
        high = build_system_prompt("M3", 0.9)
        low = build_system_prompt("M3", 0.3)
        assert "提问而非断言" in low
        assert "提问而非断言" not in high

    def test_prompt_carries_no_leak_constraints(self):
        p = build_system_prompt("M6", 0.8)
        assert "不要给出修正后的代码" in p

    def test_leak_detection_code_block(self):
        leaked, _ = leaks_answer("```python\nitems.append(5)\n```")
        assert leaked

    def test_leak_detection_fix_phrasing(self):
        leaked, why = leaks_answer("你应该把 new = items.append(5) 改成 items.append(5)。")
        assert leaked and "修正句式" in why

    def test_socratic_reply_passes(self):
        leaked, _ = leaks_answer("想一想：append 执行完之后，它把什么交还给了你？")
        assert not leaked

    def test_single_assignment_explanation_not_flagged(self):
        """讲解单行赋值是合法教学，不该误判为泄露。"""
        leaked, _ = leaks_answer("在 Python 里，x = 5 表示把 5 绑定到名字 x 上。")
        assert not leaked


if __name__ == "__main__":
    passed = failed = 0
    fails = []
    for name, obj in list(globals().items()):
        if isinstance(obj, type) and name.startswith("Test"):
            inst = obj()
            for m in dir(inst):
                if m.startswith("test_"):
                    try:
                        getattr(inst, m)()
                        passed += 1
                    except Exception as e:  # noqa: BLE001
                        failed += 1
                        fails.append(f"{name}.{m}: {type(e).__name__}: {e}")
    print(f"通过 {passed} / 失败 {failed}")
    for f in fails:
        print("  ✗", f)
    raise SystemExit(1 if failed else 0)
