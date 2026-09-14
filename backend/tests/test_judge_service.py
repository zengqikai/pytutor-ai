"""
C 方向 Task 1/2 单元测试：Multi-Judge 评分聚合 + Rubric V2
==========================================================

纯计算逻辑测试（聚合、Kappa、降级），无 LLM / DB / API 依赖。

覆盖：
- _aggregate_verdicts（中位数聚合、多数投票、CANNOT_ASSESS 处理）
- _compute_inter_judge_kappa（一致性指标）
- _fallback_verdict（评委失败降级）
"""

from app.services.judge_service import (
    JudgeVerdict,
    _aggregate_verdicts,
    _compute_inter_judge_kappa,
    _fallback_verdict,
)

DIMS = ["D1_hint_adherence", "D2_beginner_appropriate",
        "D3_no_leakage", "D4_misconception_target", "D5_actionability"]


def make_verdict(overall: int, scores: dict[str, int], needs_revision: bool = False,
                 cannot_assess: list[str] | None = None, judge_index: int = 0) -> JudgeVerdict:
    """构造一个 JudgeVerdict，scores 缺省补 4 分。"""
    full = {d: 4 for d in DIMS}
    full.update(scores)
    return JudgeVerdict(
        judge_index=judge_index,
        temperature=0.7,
        scores=full,
        total=sum(full.values()),
        overall=overall,
        issues=[],
        needs_revision=needs_revision,
        brief_reason="",
        reasoning={d: "test" for d in DIMS},
        cannot_assess=cannot_assess or [],
        raw_json="{}",
        latency_ms=10.0,
    )


# =============================================================================
# 聚合
# =============================================================================

class TestAggregateVerdicts:
    def test_median_overall(self):
        """overall 取中位数，抗极端值。"""
        agg = _aggregate_verdicts([
            make_verdict(4, {}),
            make_verdict(4, {}),
            make_verdict(5, {}),
        ])
        assert agg.aggregated_score == 4.0

    def test_majority_vote_revision(self):
        """needs_revision 取多数投票。"""
        agg = _aggregate_verdicts([
            make_verdict(4, {}, needs_revision=True),
            make_verdict(4, {}, needs_revision=True),
            make_verdict(4, {}, needs_revision=False),
        ])
        assert agg.needs_revision is True

    def test_majority_vote_no_revision(self):
        agg = _aggregate_verdicts([
            make_verdict(4, {}, needs_revision=False),
            make_verdict(4, {}, needs_revision=False),
            make_verdict(4, {}, needs_revision=True),
        ])
        assert agg.needs_revision is False

    def test_severe_disagreement_flagged(self):
        """任一维度分歧 >1 级应被标记人工复核（基于维度分数）。"""
        agg = _aggregate_verdicts([
            make_verdict(5, {"D1_hint_adherence": 5}),
            make_verdict(3, {"D1_hint_adherence": 2}),
            make_verdict(1, {"D1_hint_adherence": 1}),
        ])
        assert agg.flagged_for_review is True

    def test_cannot_assess_excluded_from_score(self):
        """CANNOT_ASSESS 维度（0 分）不拉低有效维度统计。"""
        agg = _aggregate_verdicts([
            make_verdict(4, {"D3_no_leakage": 0}, cannot_assess=["D3_no_leakage"]),
            make_verdict(4, {"D3_no_leakage": 0}, cannot_assess=["D3_no_leakage"]),
        ])
        # D3 被两个评委标记无法评估 → 记录到 cannot_assess_dims
        assert "D3_no_leakage" in agg.cannot_assess_dims
        # 其余维度仍有有效中位数
        assert agg.scores_detail["D1_hint_adherence"]["median"] == 4

    def test_all_empty_verdicts_default(self):
        """空/无效 verdict 不应崩溃，回退默认分。"""
        agg = _aggregate_verdicts([])
        assert agg.aggregated_score >= 3.0


# =============================================================================
# 一致性
# =============================================================================

class TestKappa:
    def test_identical_verdicts_positive_kappa(self):
        """完全一致的评分应有正 kappa。"""
        verdicts = [
            make_verdict(4, {}, judge_index=i) for i in range(3)
        ]
        kappa = _compute_inter_judge_kappa(verdicts)
        assert kappa > 0

    def test_divergent_verdicts_lower_kappa(self):
        """维度分歧大的评分 kappa 应低于一致评分。"""
        agreed = [make_verdict(4, {}, judge_index=i) for i in range(3)]
        diverged = [
            make_verdict(4, {"D1_hint_adherence": 5}, judge_index=0),
            make_verdict(4, {"D1_hint_adherence": 2}, judge_index=1),
            make_verdict(4, {"D1_hint_adherence": 1}, judge_index=2),
        ]
        assert _compute_inter_judge_kappa(diverged) < _compute_inter_judge_kappa(agreed)


# =============================================================================
# 降级
# =============================================================================

class TestFallbackVerdict:
    def test_fallback_is_conservative(self):
        """评委失败降级应保守（全 3 分），不触发 revision。"""
        v = _fallback_verdict(judge_index=0, temperature=0.7, latency_ms=1.0, raw="error")
        assert v.overall == 3
        assert v.needs_revision is False
        assert all(s == 3 for s in v.scores.values())
        assert any("失败" in i for i in v.issues)
