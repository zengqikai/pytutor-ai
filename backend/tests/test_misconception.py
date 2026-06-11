"""
误区诊断引擎单元测试
====================

测试 M1-M8 规则匹配逻辑，不依赖外部 API。
"""

import pytest
from app.services.misconception_service import _load_misconceptions, _rule_match


class TestRuleMatching:
    """规则匹配测试（纯逻辑，无 IO）。"""

    def test_m1_assignment_in_if(self):
        """M1: 检测 if x = 3 模式。"""
        mc = _find_mc("M1")
        assert _rule_match("if x = 3:", "", mc) is True

    def test_m1_no_false_positive(self):
        """M1: if x == 3 不应触发。"""
        mc = _find_mc("M1")
        assert _rule_match("if x == 3:", "", mc) is False

    def test_m3_append_assignment(self):
        """M3: 检测 new = list.append() 模式。"""
        mc = _find_mc("M3")
        assert _rule_match("new = nums.append(4)", "", mc) is True

    def test_m3_sort_assignment(self):
        """M3: 检测 sort() 赋值。"""
        mc = _find_mc("M3")
        assert _rule_match("result = items.sort()", "", mc) is True

    def test_m3_correct_usage(self):
        """M3: 正常 append 不应触发。"""
        mc = _find_mc("M3")
        assert _rule_match("nums.append(4)\nprint(nums)", "", mc) is False

    def test_m7_type_error(self):
        """M7: 检测 str + int 模式。"""
        mc = _find_mc("M7")
        assert _rule_match("", "TypeError: can only concatenate str", mc) is True

    def test_m7_no_error(self):
        """M7: 无 TypeError 不应触发。"""
        mc = _find_mc("M7")
        assert _rule_match("print(1+1)", "", mc) is False

    def test_clean_code_no_misconception(self):
        """干净代码不应诊断出任何误区。"""
        misconceptions = _load_misconceptions()
        for mc in misconceptions:
            assert _rule_match("print('hello')", "", mc) is False, \
                f"clean code falsely triggered {mc['code']}"


class TestMisconceptionData:
    """误区数据完整性测试。"""

    def test_all_8_types_loaded(self):
        """应加载 8 类误区。"""
        misconceptions = _load_misconceptions()
        codes = {m["code"] for m in misconceptions}
        expected = {f"M{i}" for i in range(1, 9)}
        assert codes == expected, f"Missing: {expected - codes}"

    def test_each_has_patterns(self):
        """每类误区至少有一个匹配规则。"""
        for mc in _load_misconceptions():
            assert len(mc.get("typical_patterns", [])) > 0, \
                f"{mc['code']} has no patterns"

    def test_each_has_recommended_strategy(self):
        """每类误区有推荐策略。"""
        for mc in _load_misconceptions():
            assert mc.get("recommended_strategy"), \
                f"{mc['code']} missing recommended_strategy"


# ── helpers ──

def _find_mc(code: str) -> dict:
    """按 code 查找单个误区。"""
    for mc in _load_misconceptions():
        if mc["code"] == code:
            return mc
    raise ValueError(f"Misconception {code} not found")
