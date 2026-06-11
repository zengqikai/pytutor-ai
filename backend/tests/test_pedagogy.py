"""
教学策略单元测试
================

测试策略选择逻辑和提示等级规则。
"""

import pytest
from app.services.pedagogy_service import select_strategy


class TestStrategySelection:
    """策略选择器测试。"""

    def test_first_attempt_no_history(self):
        """首次尝试 + 无历史 → clarification。"""
        result = select_strategy(None, attempt_count=1, has_history=False)
        assert result["strategy"] == "clarification"
        assert result["hint_level"] == 1

    def test_first_misconception(self):
        """首次误区 → progressive_hint, level 1-2。"""
        result = select_strategy("M3", attempt_count=1, has_history=False)
        assert result["strategy"] == "progressive_hint"
        assert result["hint_level"] in (1, 2)

    def test_repeated_misconception(self):
        """重复误区 3+ 次 → concept_explanation。"""
        result = select_strategy("M5", attempt_count=3, has_history=True)
        assert result["strategy"] == "concept_explanation"
        assert result["hint_level"] == 1  # 概念解释用低等级

    def test_multiple_failures_no_mc(self):
        """多次失败无误区 → debugging_guidance。"""
        result = select_strategy(None, attempt_count=4, has_history=True)
        assert result["strategy"] == "debugging_guidance"
        assert result["hint_level"] >= 2

    def test_hint_level_capped(self):
        """提示等级不超过 4（Level 5 只在明确请求时）。"""
        result = select_strategy("M3", attempt_count=10, has_history=True)
        assert result["hint_level"] <= 4

    def test_second_attempt(self):
        """第二次尝试 → 等级递增。"""
        result = select_strategy("M1", attempt_count=2, has_history=True)
        assert result["hint_level"] >= 2


class TestHintLevels:
    """提示等级边界测试。"""

    def test_known_strategies_exist(self):
        """所有策略名称在文档中有定义。"""
        from app.services.pedagogy_service import STRATEGIES
        expected = {
            "clarification", "progressive_hint", "concept_explanation",
            "debugging_guidance", "counterexample",
            "summary_reflection", "practice_recommendation",
        }
        assert set(STRATEGIES.keys()) >= expected

    def test_hint_levels_1_to_5(self):
        """提示等级为 1-5。"""
        from app.services.pedagogy_service import HINT_LEVELS
        assert set(HINT_LEVELS.keys()) == {1, 2, 3, 4, 5}
