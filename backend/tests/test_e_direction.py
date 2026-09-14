"""
E 方向（E-FR-01 / 02 / 04 / 05）单元测试
=======================================

测试逐条对应 SRS 3.2 §4.3 的验收判定，而不是"覆盖代码行"。
每个测试类的 docstring 引用它所验收的需求编号。

未覆盖：E-FR-03（生成-检索-重排）——它复用 rag_service，本包内无该模块。
"""

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.analysis import root_cause as rc  # noqa: E402
from app.analysis.error_class import (  # noqa: E402
    LOGIC_ERROR, OTHER_ERROR, classify_error, enrich_diagnose_result,
    is_beyond_misconceptions, is_syntax_level,
)
from app.services.pedagogy.steering import (  # noqa: E402
    StrategyDecision, StudentState, TeachingIntent, TransitionGraph,
    select_strategy, select_strategy_legacy,
)


# =============================================================================
# E-FR-02：三层诊断底座
# =============================================================================

class TestErrorClass:
    """E-FR-02 验收：提交触发 NameError 的代码，即使不命中任何 M，
    diagnose 结果 error_class=runtime_name 非空。"""

    def test_acceptance_nameerror_without_misconception(self):
        result = {"concept_id": "variable", "misconceptions": []}
        out = enrich_diagnose_result(result, stderr="NameError: name 'x' is not defined")
        assert out["error_class"] == "runtime_name"
        assert out["beyond_misconceptions"] is True

    def test_backward_compatible_keys_untouched(self):
        result = {"concept_id": "list", "misconceptions": ["M3"], "confidence": 0.7}
        out = enrich_diagnose_result(result, stderr="")
        assert out["concept_id"] == "list"
        assert out["misconceptions"] == ["M3"]
        assert out["confidence"] == 0.7

    def test_chained_exception_takes_last(self):
        """异常链里真正终结程序的是最后一个，不是第一个。"""
        stderr = (
            "Traceback (most recent call last):\n"
            "KeyError: 'a'\n\n"
            "During handling of the above exception, another exception occurred:\n\n"
            "Traceback (most recent call last):\n"
            "TypeError: bad operand\n"
        )
        assert classify_error(stderr, True, None) == "runtime_type"

    def test_syntax_error_parsed_from_caret_block(self):
        stderr = '  File "<stdin>", line 1\n    x = \n       ^\nSyntaxError: invalid syntax'
        assert classify_error(stderr, True, None) == "syntax"
        assert is_syntax_level("syntax")

    def test_qualified_exception_name(self):
        assert classify_error("json.decoder.JSONDecodeError: x", True, None) == OTHER_ERROR

    def test_traceback_header_not_mistaken_for_exception(self):
        stderr = "Traceback (most recent call last):\n  File \"a.py\"\nValueError: bad"
        assert classify_error(stderr, True, None) == "runtime_value"

    def test_logic_error_when_ran_but_wrong_output(self):
        assert classify_error("", True, False) == LOGIC_ERROR

    def test_clean_run_returns_none(self):
        assert classify_error("", True, True) is None
        assert classify_error("", True, None) is None

    def test_killed_without_stderr_is_other_not_none(self):
        """超时/被资源限制杀掉：没有 stderr 但绝不是"没错误"。"""
        assert classify_error("", False, None) == OTHER_ERROR

    def test_beyond_misconceptions_false_when_m_hit(self):
        assert is_beyond_misconceptions("runtime_type", ["M4"]) is False
        assert is_beyond_misconceptions(None, []) is False


# =============================================================================
# E-FR-01 / E-FR-05：教学转向状态机
# =============================================================================

class TestSteering:
    """E-FR-01 验收：同一学生同一误区第 1 次→progressive_hint；
    第 ≥3 次→concept_explanation。转移图改配置即可切换分支。"""

    def test_acceptance_first_attempt_progressive_hint(self):
        s = StudentState(active_misconceptions=["M3"], attempt_count=1)
        assert select_strategy(s).intent is TeachingIntent.PROGRESSIVE_HINT

    def test_acceptance_third_attempt_concept_explanation(self):
        s = StudentState(active_misconceptions=["M3"], attempt_count=3)
        assert select_strategy(s).intent is TeachingIntent.CONCEPT_EXPLANATION

    def test_second_attempt_still_hint_but_higher_level(self):
        d1 = select_strategy(StudentState(active_misconceptions=["M3"], attempt_count=1))
        d2 = select_strategy(StudentState(active_misconceptions=["M3"], attempt_count=2))
        assert d2.intent is TeachingIntent.PROGRESSIVE_HINT
        assert d2.hint_level > d1.hint_level

    def test_hint_level_capped(self):
        d = select_strategy(StudentState(active_misconceptions=["M3"], attempt_count=1))
        assert d.hint_level == 1
        # concept_explanation 不是"更强的提示"，hint_level 应为 0
        d3 = select_strategy(StudentState(active_misconceptions=["M3"], attempt_count=9))
        assert d3.hint_level == 0

    def test_mastery_recovered_advances(self):
        s = StudentState(concept_mastery={"list": 0.8}, attempt_count=1,
                         last_intent=TeachingIntent.PROGRESSIVE_HINT)
        assert select_strategy(s).intent is TeachingIntent.ADVANCE

    def test_mastery_uses_min_not_max(self):
        """一个概念掌握了不等于都掌握了——用最小值，避免过早 advance。"""
        s = StudentState(concept_mastery={"list": 0.9, "loop": 0.2}, attempt_count=1,
                         last_intent=TeachingIntent.PROGRESSIVE_HINT)
        assert select_strategy(s).intent is not TeachingIntent.ADVANCE

    def test_efr05_prediction_leads_to_productive_failure(self):
        s = StudentState(attempt_count=1, prediction_submitted=True,
                         last_intent=TeachingIntent.ELICIT_PREDICTION)
        assert select_strategy(s).intent is TeachingIntent.PRODUCTIVE_FAILURE

    def test_matched_rule_is_recorded(self):
        d = select_strategy(StudentState(active_misconceptions=["M3"], attempt_count=3))
        assert "repeated_same_misconception" in d.matched_rule

    def test_illegal_attempt_count_rejected_not_degraded(self):
        """attempt_count=0 说明历史查询失败；静默降级会让 concept_explanation
        永久不可达（正是 B-FR-13 曾经的病）。"""
        try:
            select_strategy(StudentState(active_misconceptions=["M3"], attempt_count=0))
        except ValueError as e:
            assert "B-FR-13" in str(e)
        else:
            raise AssertionError("应当拒绝而非静默降级")

    def test_legacy_shim_matches_old_contract(self):
        assert select_strategy_legacy("M3", 1, False)["strategy"] == "progressive_hint"
        assert select_strategy_legacy("M3", 3, True)["strategy"] == "concept_explanation"

    def test_legacy_shim_detects_ordering_bug(self):
        """has_history=True 但 attempt=1 → 事件在查历史前入库（B-FR-18）。"""
        try:
            select_strategy_legacy("M3", 1, True)
        except ValueError as e:
            assert "B-FR-18" in str(e)
        else:
            raise AssertionError("应当检测出时序矛盾")


class TestTransitionGraphValidation:
    """载入时校验：配置写错应当在启动时炸，而不是等学生走到那条分支。"""

    def _write(self, tmp: Path, body: str) -> Path:
        p = tmp / "g.yaml"
        p.write_text(body, encoding="utf-8")
        return p

    def test_unknown_intent_rejected(self, tmp=Path(tempfile.gettempdir())):
        p = self._write(tmp, "start: elicit_prediction\ntransitions:\n"
                             "  - {from: elicit_prediction, when: always, to: teleport}\n")
        try:
            TransitionGraph.from_yaml(p)
        except ValueError as e:
            assert "teleport" in str(e)
        else:
            raise AssertionError("未知意图应被拒绝")

    def test_unknown_predicate_rejected(self, tmp=Path(tempfile.gettempdir())):
        p = self._write(tmp, "start: elicit_prediction\ntransitions:\n"
                             "  - {from: elicit_prediction, when: vibes, to: advance}\n")
        try:
            TransitionGraph.from_yaml(p)
        except ValueError as e:
            assert "vibes" in str(e)
        else:
            raise AssertionError("未注册谓词应被拒绝")

    def test_config_change_switches_branch_without_code_change(self, tmp=Path(tempfile.gettempdir())):
        """E-FR-01 验收判定的后半句：改配置即可切换分支。"""
        p = self._write(tmp,
            "start: elicit_prediction\n"
            "entry_on_misconception: productive_failure\n"
            "default: progressive_hint\n"
            "transitions:\n"
            "  - {from: productive_failure, when: first_time_misconception, to: counterexample}\n")
        g = TransitionGraph.from_yaml(p)
        from app.services.pedagogy.steering import select_next_intent
        intent, _ = select_next_intent(
            StudentState(active_misconceptions=["M3"], attempt_count=1), g)
        assert intent is TeachingIntent.COUNTEREXAMPLE


# =============================================================================
# E-FR-04：薄根因层
# =============================================================================

class TestRootCause:
    """E-FR-04 验收：默认 Flag 关闭时对现有诊断零影响；
    开启后 root_cause_weights 仅在映射被数据验证的子集上生效。"""

    def teardown_method(self):
        os.environ.pop(rc.FLAG_ENV, None)
        rc.reset()

    def test_acceptance_disabled_by_default(self):
        rc.reset()
        assert rc.is_enabled() is False
        assert rc.compute_weights(["M3", "M6"]) == {}

    def test_insufficient_samples_rejects_all(self):
        os.environ[rc.FLAG_ENV] = "true"
        vs = rc.validate_hypotheses({}, {}, n_samples=50)
        assert all(not v.validated for v in vs)
        rc.activate(vs)
        assert rc.compute_weights(["M3", "M6"]) == {}

    def test_acceptance_only_validated_subset_takes_effect(self):
        os.environ[rc.FLAG_ENV] = "true"
        marginal = {"M3": 200, "M6": 180, "M4": 150, "M5": 140}
        co = {("M3", "M6"): 90, ("M4", "M5"): 5}   # M4∧M5 几乎不共现
        vs = rc.validate_hypotheses(co, marginal, n_samples=1000)
        rc.activate(vs)
        assert rc.compute_weights(["M3", "M6"]) == {"value_not_auto_retained": 1.0}
        assert rc.compute_weights(["M4", "M5"]) == {}   # 假设被数据否决

    def test_single_symptom_hypothesis_structurally_valid(self):
        vs = rc.validate_hypotheses({}, {"M8": 50}, n_samples=1000)
        v = next(v for v in vs if v.root_cause == "state_over_loop")
        assert v.validated and "未主张共现" in v.reason

    def test_partial_hit_gives_partial_weight(self):
        os.environ[rc.FLAG_ENV] = "true"
        vs = rc.validate_hypotheses({("M3", "M6"): 90}, {"M3": 200, "M6": 180}, 1000)
        rc.activate(vs)
        assert rc.compute_weights(["M3"]) == {"value_not_auto_retained": 0.5}

    def test_force_bypasses_validation_but_is_explicit(self):
        os.environ[rc.FLAG_ENV] = "true"
        rc.activate([], force=True)
        assert rc.compute_weights(["M4", "M5"]) == {"off_by_boundary": 1.0}


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
                    finally:
                        if hasattr(inst, "teardown_method"):
                            inst.teardown_method()
    print(f"通过 {passed} / 失败 {failed}")
    for f in fails:
        print("  ✗", f)
    raise SystemExit(1 if failed else 0)
