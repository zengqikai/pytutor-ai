"""
混合检索器
=========

实现向量检索 + 关键词检索的混合方案。

MVP 方案（无需外部向量数据库）：
- 关键词检索：基于 TF-IDF 的简单实现（BM25 的简化版）
- 不需要 embedding API，减少依赖
- 后续 Step 10 升级为真正的向量检索（pgvector + OpenAI Embedding）

混合检索原理：
    向量检索擅长语义相似（"循环" 能匹配到 "for"）
    关键词检索擅长精确匹配（"SyntaxError" 精确匹配到错误文档）
    混合两者可得最佳效果

TF-IDF 原理简介：
    TF（Term Frequency）：词在文档中出现的频率
    IDF（Inverse Document Frequency）：词的"稀有度"
    一个词在某文档中出现很多次（高 TF），但在整个语料库中很少见（高 IDF），
    则它对该文档很重要。

    score(q, d) = sum(TF(t, d) * IDF(t) for t in query_tokens)
"""

import math
import re
import time
from collections import Counter

from app.observability.logger import get_logger

logger = get_logger(__name__)


class HybridRetriever:
    """
    混合检索器。

    在内存中维护 chunk 索引，支持 TF-IDF 关键词检索 + 标题匹配。
    """

    def __init__(self):
        # chunk 索引: id → {content, heading, concepts, difficulty, document_title, tokens}
        self._chunks: dict[str, dict] = {}
        # IDF 缓存: token → idf_value
        self._idf_cache: dict[str, float] = {}
        # 总 chunk 数
        self._total_docs = 0

    def add_chunk(
        self,
        chunk_id: str,
        content: str,
        heading: str | None = None,
        concepts: str | None = None,
        difficulty: str = "beginner",
        document_title: str = "",
        tokens: str | None = None,
    ):
        """添加/更新一个 chunk 到索引。"""
        token_list = tokens.split() if tokens else _tokenize(content)

        self._chunks[chunk_id] = {
            "content": content,
            "heading": heading or "",
            "concepts": concepts or "",
            "difficulty": difficulty,
            "document_title": document_title,
            "tokens": token_list,
            "token_set": set(token_list),
        }
        self._total_docs = len(self._chunks)
        # 清除 IDF 缓存（新增文档后 IDF 值会变化）
        self._idf_cache = {}

    def remove_chunk(self, chunk_id: str):
        """从索引中移除 chunk。"""
        self._chunks.pop(chunk_id, None)
        self._total_docs = len(self._chunks)
        self._idf_cache = {}

    def clear(self):
        """清空所有索引。"""
        self._chunks.clear()
        self._idf_cache.clear()
        self._total_docs = 0

    def search(
        self,
        query: str,
        top_k: int = 5,
        difficulty_filter: str | None = None,
        concept_filter: str | None = None,
    ) -> list[dict]:
        """
        执行混合检索。

        参数:
            query: 检索查询
            top_k: 返回 Top-K 结果
            difficulty_filter: 难度过滤（如 "beginner"）
            concept_filter: 知识点过滤（如 "for_loop"）

        返回:
            list[dict]: 每个结果含 {chunk_id, content, heading, score, ...}
        """
        start_time = time.perf_counter()

        if not self._chunks:
            return []

        # 步骤 1：对查询分词
        query_tokens = _tokenize(query)
        if not query_tokens:
            return []

        # 步骤 2：计算每个 chunk 的 TF-IDF 得分
        scores: dict[str, float] = {}

        for chunk_id, chunk in self._chunks.items():
            # 过滤
            if difficulty_filter and chunk["difficulty"] != difficulty_filter:
                continue
            if concept_filter and concept_filter not in chunk["concepts"]:
                continue

            # TF-IDF 得分
            tfidf_score = _tfidf_score(
                query_tokens=query_tokens,
                doc_tokens=chunk["tokens"],
                doc_token_set=chunk["token_set"],
                total_docs=self._total_docs,
                idf_cache=self._idf_cache,
            )

            # 标题匹配加分（查询词出现在标题中 → 高度相关）
            heading_bonus = 0.0
            heading_lower = chunk["heading"].lower()
            for qt in query_tokens:
                if qt.lower() in heading_lower:
                    heading_bonus += 0.2

            # 综合得分 = TF-IDF + 标题奖励
            scores[chunk_id] = tfidf_score + heading_bonus

        # 步骤 3：排序并返回 Top-K
        sorted_chunks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top_chunks = sorted_chunks[:top_k]

        results = []
        for chunk_id, score in top_chunks:
            if score <= 0:
                continue
            chunk = self._chunks[chunk_id]
            results.append({
                "chunk_id": chunk_id,
                "document_title": chunk["document_title"],
                "heading": chunk["heading"] or None,
                "content": chunk["content"],
                "score": round(_normalize_score(score, scores), 4),
                "difficulty": chunk["difficulty"],
                "concepts": chunk["concepts"] or None,
            })

        elapsed = (time.perf_counter() - start_time) * 1000
        logger.debug(
            "retrieval_completed",
            query=query[:80],
            result_count=len(results),
            duration_ms=round(elapsed, 2),
        )

        return results


# =============================================================================
# 全局单例检索器
# =============================================================================
# 整个应用共享一个检索器实例，所有 chunk 统一索引。
# =============================================================================
retriever = HybridRetriever()


# =============================================================================
# TF-IDF 计算函数
# =============================================================================

def _tokenize(text: str) -> list[str]:
    """简单的中英文混合分词。"""
    tokens = []

    # Python 代码（反引号内的标识符）
    for match in re.finditer(r"`([^`]+)`", text):
        for id_match in re.finditer(r"[a-zA-Z_]\w+", match.group(1)):
            t = id_match.group().lower()
            if len(t) >= 2:
                tokens.append(t)

    # 移除反引号内容
    text_no_code = re.sub(r"`[^`]+`", " ", text)

    # 英文单词（3 字符以上）
    for w in re.findall(r"[a-zA-Z]{3,}", text_no_code):
        tokens.append(w.lower())

    # 中文 2-gram
    chinese = re.findall(r"[一-鿿]", text_no_code)
    for i in range(len(chinese) - 1):
        tokens.append(chinese[i] + chinese[i + 1])

    # 去重
    seen = set()
    result = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)
    return result


def _tfidf_score(
    query_tokens: list[str],
    doc_tokens: list[str],
    doc_token_set: set[str],
    total_docs: int,
    idf_cache: dict[str, float],
) -> float:
    """计算查询与文档的 TF-IDF 余弦相似度。"""
    if not query_tokens or not doc_tokens:
        return 0.0

    # 文档 TF
    doc_counter = Counter(doc_tokens)
    doc_len = len(doc_tokens)

    score = 0.0
    for token in query_tokens:
        if token not in doc_token_set:
            continue

        # TF（词频）
        tf = doc_counter[token] / doc_len

        # IDF（逆文档频率）
        if token not in idf_cache:
            # 计算包含此 token 的文档数
            # 简化：因为我们用 token_set 做成员测试，这里用缓存估算
            # 完整实现需要遍历所有文档（太慢），所以用启发式：
            # 对中文 2-gram：罕见（IDF 高）
            # 对英文单词：常见（IDF 低）
            doc_freq = _estimate_doc_freq(token, total_docs)
            idf_cache[token] = math.log((total_docs + 1) / (doc_freq + 1)) + 1

        idf = idf_cache[token]
        score += tf * idf

    return score


def _estimate_doc_freq(token: str, total_docs: int) -> float:
    """估算 token 的文档频率（启发式方法）。"""
    # 中文 2-gram：相对罕见
    if re.match(r"[一-鿿]{2}", token):
        return max(1, total_docs * 0.1)
    # 短英文词：常见
    if len(token) <= 3:
        return max(1, total_docs * 0.3)
    # 长英文词/Python 标识符：较罕见
    return max(1, total_docs * 0.15)


def _normalize_score(score: float, all_scores: dict[str, float]) -> float:
    """将得分归一化到 0-1 区间。"""
    if not all_scores:
        return 0.0
    max_score = max(all_scores.values())
    if max_score <= 0:
        return 0.0
    return min(1.0, score / max_score)
