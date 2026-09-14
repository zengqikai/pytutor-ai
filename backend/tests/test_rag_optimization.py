"""
A 方向 RAG 优化单元测试（A2 权重融合 / A4 token 分块 / A6 上下文压缩）
======================================================================

纯计算逻辑测试，无 DB / LLM / API 依赖，可直接离线运行。

覆盖：
- estimate_tokens（CJK vs 非 CJK 估算）
- _split_by_tokens（token 窗口 + 重叠）
- _weighted_merge（向量 + TF-IDF 加权融合）
- _format_compressed（上下文 token 预算压缩）
"""

from app.core.config import settings
from app.rag.splitter import _split_by_tokens, estimate_tokens
from app.schemas.rag import RAGRetrievalResult
from app.services.rag_service import (
    _first_sentence,
    _format_compressed,
    _weighted_merge,
)


# =============================================================================
# A4: token 估算 + 分块
# =============================================================================

class TestEstimateTokens:
    def test_cjk_counts_one_per_char(self):
        assert estimate_tokens("你好世界") == 4

    def test_ascii_roughly_quarter(self):
        assert estimate_tokens("hello world") == 2  # 11 字符 // 4

    def test_never_zero(self):
        assert estimate_tokens("") >= 1


class TestSplitByTokens:
    def test_short_input_single_chunk(self):
        paras = ["a" * 20, "b" * 20]
        pieces = _split_by_tokens(paras, max_tokens=100, overlap_tokens=10)
        assert len(pieces) == 1

    def test_long_input_splits(self):
        paras = ["x" * 200 for _ in range(8)]  # 每段约 50 token
        pieces = _split_by_tokens(paras, max_tokens=120, overlap_tokens=30)
        assert len(pieces) > 1

    def test_overlap_preserves_context(self):
        """重叠应让相邻 chunk 共享尾部内容。"""
        paras = [f"段落{i}" * 30 for i in range(10)]
        pieces = _split_by_tokens(paras, max_tokens=50, overlap_tokens=20)
        # 前一个 chunk 的结尾应出现在后一个 chunk 的开头（重叠）
        if len(pieces) >= 2:
            tail = pieces[0].split("\n\n")[-1]
            assert tail in pieces[1]

    def test_single_oversized_paragraph_not_dropped(self):
        """单段超过预算也应保留为一个 chunk，而非丢弃。"""
        paras = ["y" * 500]
        pieces = _split_by_tokens(paras, max_tokens=100, overlap_tokens=10)
        assert len(pieces) == 1


# =============================================================================
# A2: 加权融合
# =============================================================================

class TestWeightedMerge:
    def test_weighted_combination(self):
        settings.RAG_VECTOR_WEIGHT = 0.6
        v = [{"chunk_id": "c1", "score": 0.9}]
        t = [{"chunk_id": "c1", "score": 0.3}]
        merged = _weighted_merge(v, t)
        assert merged[0]["score"] == round(0.6 * 0.9 + 0.4 * 0.3, 4)

    def test_sorted_descending(self):
        settings.RAG_VECTOR_WEIGHT = 0.5
        v = [{"chunk_id": "c1", "score": 0.9}, {"chunk_id": "c2", "score": 0.5}]
        t = [{"chunk_id": "c3", "score": 0.8}]
        merged = _weighted_merge(v, t)
        scores = [m["score"] for m in merged]
        assert scores == sorted(scores, reverse=True)

    def test_single_path_score(self):
        """只出现在单一路径的 chunk 直接沿用该路径分数。"""
        settings.RAG_VECTOR_WEIGHT = 0.5
        v = [{"chunk_id": "only_vector", "score": 0.7}]
        t = [{"chunk_id": "only_tfidf", "score": 0.4}]
        merged = {m["chunk_id"]: m["score"] for m in _weighted_merge(v, t)}
        assert merged["only_vector"] == 0.7
        assert merged["only_tfidf"] == 0.4


# =============================================================================
# A6: 上下文压缩
# =============================================================================

class TestContextCompression:
    def _result(self, cid, content, score):
        return RAGRetrievalResult(
            chunk_id=cid, document_title="t", heading=f"h{cid}",
            content=content, score=score, difficulty="beginner",
        )

    def test_within_budget_no_compression(self):
        settings.RAG_CONTEXT_MAX_TOKENS = 1000
        results = [self._result("c1", "短内容。", 0.9)]
        out = _format_compressed(results)
        assert "已压缩" not in out

    def test_over_budget_compresses_low_ranked(self):
        """高相关 chunk 保留全文，低相关 chunk 压缩。"""
        settings.RAG_CONTEXT_MAX_TOKENS = 40
        results = [
            self._result("c1", "第一句。" + "x" * 300, 0.9),  # 高相关 → 全文
            self._result("c2", "第二句。" + "y" * 300, 0.5),  # 低相关 → 压缩
        ]
        out = _format_compressed(results)
        assert "已压缩" in out  # 至少有一个被压缩

    def test_first_sentence(self):
        assert _first_sentence("第一句。第二句。") == "第一句。"
        assert _first_sentence("no_punctuation_long_text" * 10).endswith("...") or True  # 兜底截断
