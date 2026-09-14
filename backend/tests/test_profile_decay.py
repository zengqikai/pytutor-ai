"""
C 方向 Task 3/4 单元测试：画像时间衰减 + 转移矩阵 + Hint 依赖量化
================================================================

纯计算逻辑测试，无 DB / LLM / API 依赖，可直接离线运行。

覆盖：
- compute_decayed_severity（指数衰减、半衰期、边界防护）
- TransitionMatrix（转移记录、相关性、风险预测、序列化）
- compute_hint_dependency（阈值边界）
- compute_hint_dependency_trend（趋势判定）
- mastery_to_state（掌握度状态映射）
"""

from datetime import datetime, timedelta, timezone

from app.services.profile_decay_service import (
    DAYS_HALF_LIFE,
    HINT_DEP_THRESHOLDS,
    TransitionMatrix,
    compute_decayed_severity,
    compute_hint_dependency,
    compute_hint_dependency_trend,
    mastery_to_state,
)


# =============================================================================
# 时间衰减
# =============================================================================

class TestDecayedSeverity:
    def test_half_life_halves_severity(self):
        """一个半衰期后，严重度应衰减为一半。"""
        ref = datetime.now(timezone.utc)
        r = compute_decayed_severity(
            5, ref - timedelta(days=DAYS_HALF_LIFE), reference_time=ref
        )
        assert r["decayed"] == 2.5
        assert r["days_since"] == DAYS_HALF_LIFE

    def test_zero_days_no_decay(self):
        """刚发生的弱项不应衰减。"""
        ref = datetime.now(timezone.utc)
        r = compute_decayed_severity(5, ref, reference_time=ref)
        assert r["decayed"] == 5.0

    def test_decay_never_below_floor(self):
        """衰减有下限，彻底遗忘 ≠ 从未犯错。"""
        ref = datetime.now(timezone.utc)
        r = compute_decayed_severity(5, ref - timedelta(days=365), reference_time=ref)
        assert r["decayed"] >= 0.1

    def test_future_time_clamped_to_zero(self):
        """未来时间（时钟偏差防护）应视为 0 天。"""
        ref = datetime.now(timezone.utc)
        r = compute_decayed_severity(
            5, ref + timedelta(days=1), reference_time=ref
        )
        assert r["days_since"] == 0.0

    def test_naive_datetime_assumed_utc(self):
        """naive datetime 应被当作 UTC 处理，不抛异常。"""
        r = compute_decayed_severity(5, datetime(2026, 1, 1, 0, 0, 0))
        assert r["decayed"] >= 0.1


# =============================================================================
# 转移矩阵
# =============================================================================

class TestTransitionMatrix:
    def test_record_and_correlation(self):
        """正向转移（学好 A → B 也好）应产生正相关性。"""
        tm = TransitionMatrix()
        for _ in range(4):
            tm.record_transition("M3", "M4", from_improved=True, to_improved=True)
        tm.record_transition("M3", "M4", from_improved=False, to_improved=False)
        corr = tm.get_correlation("M3", "M4")
        assert corr > 0

    def test_unknown_pair_correlation_zero(self):
        tm = TransitionMatrix()
        assert tm.get_correlation("M3", "M4") == 0.0

    def test_worsened_propagation_raises_risk(self):
        """恶化传播模式（A→B 频繁一起变差）应预测 B 有风险。"""
        tm = TransitionMatrix()
        for _ in range(5):
            tm.record_transition("M3", "M5", from_improved=False, to_improved=False)
        risks = tm.predict_weakness_risk(["M3"])
        assert any(r["concept"] == "M5" for r in risks)

    def test_related_concepts_returns_correlated(self):
        """正相关超过阈值且有足够观测的概念应被返回。"""
        tm = TransitionMatrix()
        for _ in range(5):
            tm.record_transition("M3", "M4", True, True)
        for _ in range(5):
            tm.record_transition("M3", "M6", True, True)
        related = tm.get_related_concepts("M3")
        concepts = {r["concept"] for r in related}
        assert concepts == {"M4", "M6"}

    def test_related_concepts_respects_top_k(self):
        tm = TransitionMatrix()
        for to in ("M4", "M6", "M7"):
            for _ in range(5):
                tm.record_transition("M3", to, True, True)
        related = tm.get_related_concepts("M3", top_k=2)
        assert len(related) == 2

    def test_roundtrip_serialization(self):
        tm = TransitionMatrix()
        tm.record_transition("M3", "M4", True, True)
        tm2 = TransitionMatrix.from_dict(tm.to_dict())
        assert tm2.get_correlation("M3", "M4") == tm.get_correlation("M3", "M4")


# =============================================================================
# Hint 依赖
# =============================================================================

class TestHintDependency:
    def test_low_dependency(self):
        r = compute_hint_dependency(total_hints=3, total_exercises=10)
        assert r["label"] == "low"
        assert 0.0 <= r["score"] < HINT_DEP_THRESHOLDS["medium"][0]

    def test_high_dependency(self):
        r = compute_hint_dependency(total_hints=10, total_exercises=2)
        assert r["label"] == "high"

    def test_zero_denominator_safe(self):
        """hints=0 且 exercises=0 不应除零。"""
        r = compute_hint_dependency(total_hints=0, total_exercises=0)
        assert r["score"] == 0.0
        assert r["label"] == "low"

    def test_boundary_medium(self):
        """40% 依赖应落在 medium 区间。"""
        r = compute_hint_dependency(total_hints=4, total_exercises=6)  # 4/10 = 0.4
        assert r["label"] == "medium"

    def test_trend_increasing(self):
        assert compute_hint_dependency_trend("low", 0.1, 0.3) == "increasing"

    def test_trend_decreasing(self):
        assert compute_hint_dependency_trend("high", 0.6, 0.3) == "decreasing"

    def test_trend_stable(self):
        assert compute_hint_dependency_trend("medium", 0.30, 0.32) == "stable"


# =============================================================================
# 掌握度状态映射
# =============================================================================

class TestMasteryState:
    def test_proficient(self):
        assert mastery_to_state(0.9) == "proficient"

    def test_developing(self):
        assert mastery_to_state(0.4) == "developing"
