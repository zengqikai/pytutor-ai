"""
RAG 服务模块
===========

负责知识文档的导入、索引、检索和问答增强。

核心流程：
1. 文档导入：读取 Markdown → 切分成 chunk → 存入数据库 → 加入检索索引
2. 检索：查询 → TF-IDF 检索 → LLM 重排序 → 返回 Top-N 上下文
3. 增强回答：检索结果拼入 Prompt → LLM 生成带知识背景的回答
"""

import asyncio
import time

from sqlalchemy import select


# =============================================================================
# RAG 熔断器（进程内，轻量）
# =============================================================================

class RAGBreaker:
    """RAG 检索熔断器。连续失败 N 次后进入 open 状态，跳过 RAG。"""

    _fail_count: int = 0
    _open_until: float = 0.0
    THRESHOLD: int = 3
    COOLDOWN: int = 30  # 秒

    @classmethod
    def is_open(cls) -> bool:
        return time.time() < cls._open_until

    @classmethod
    def record_fail(cls):
        cls._fail_count += 1
        if cls._fail_count >= cls.THRESHOLD:
            cls._open_until = time.time() + cls.COOLDOWN

    @classmethod
    def record_ok(cls):
        cls._fail_count = 0
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.rag import RAGChunk, RAGDocument
from app.observability.logger import get_logger
from app.rag.retriever import HybridRetriever, retriever
from app.rag.reranker import rerank_with_llm
from app.rag.splitter import estimate_tokens, simple_tokenize, split_markdown
from app.schemas.rag import RAGRetrievalRequest, RAGRetrievalResponse, RAGRetrievalResult

logger = get_logger(__name__)


# =============================================================================
# 文档导入
# =============================================================================

async def ingest_document(
    db: AsyncSession,
    title: str,
    content: str,
    difficulty: str = "beginner",
    concepts: str | None = None,
    source_type: str = "manual",
) -> RAGDocument:
    """
    导入一篇教学文档。

    流程：
    1. 创建 RAGDocument 记录
    2. 切分内容为 chunk
    3. 为每个 chunk 生成 tokens → 存入 DB → 加入检索索引

    参数:
        db: 数据库会话
        title: 文档标题
        content: Markdown 格式的文档内容
        difficulty: 难度级别
        concepts: 知识点标签（逗号分隔）
        source_type: 来源类型

    返回:
        RAGDocument: 创建的文档对象（含 chunks）
    """
    # 步骤 1：创建文档记录
    doc = RAGDocument(
        title=title,
        content=content,
        difficulty=difficulty,
        concepts=concepts,
        source_type=source_type,
    )
    db.add(doc)
    await db.commit()
    await db.refresh(doc)

    # 步骤 2：切分为 chunk
    chunks_data = split_markdown(content, title)

    # 步骤 3：创建 chunk 记录并加入索引
    for chunk_data in chunks_data:
        tokens = simple_tokenize(chunk_data["content"])
        tokens_str = " ".join(tokens)

        chunk = RAGChunk(
            document_id=doc.id,
            chunk_index=chunk_data["chunk_index"],
            content=chunk_data["content"],
            heading=chunk_data.get("heading"),
            tokens=tokens_str,
            difficulty=difficulty,
            concepts=concepts,
        )
        db.add(chunk)
        await db.commit()
        await db.refresh(chunk)

        # 加入 TF-IDF 索引
        retriever.add_chunk(
            chunk_id=chunk.id,
            content=chunk.content,
            heading=chunk.heading,
            concepts=concepts,
            difficulty=difficulty,
            document_title=title,
            tokens=tokens_str,
        )

    # 同步写入向量库
    from app.rag.vector_store import add_chunks as add_to_vector

    vector_chunks = [
        {
            "chunk_id": chunk.id,
            "content": chunk.content,
            "heading": chunk.heading or "",
            "concepts": concepts or "",
            "difficulty": difficulty,
        }
        for chunk in doc.chunks
    ]
    add_to_vector(vector_chunks)

    logger.info(
        "document_ingested",
        doc_id=doc.id,
        title=title,
        chunk_count=len(chunks_data),
        difficulty=difficulty,
    )

    # 返回一个含 chunk_count 的简单对象，避免访问 lazy-loaded relationship
    doc._chunk_count = len(chunks_data)
    return doc


# =============================================================================
# 索引重建（从数据库加载所有 chunk 到内存检索器）
# =============================================================================

async def rebuild_index(db: AsyncSession) -> int:
    """
    从数据库重新加载所有 chunk 到内存索引。

    用途：服务重启后恢复索引。

    返回:
        int: 加载的 chunk 数量
    """
    retriever.clear()

    result = await db.execute(
        select(RAGChunk, RAGDocument)
        .join(RAGDocument, RAGChunk.document_id == RAGDocument.id)
        .where(RAGDocument.is_active == True)
    )
    rows = result.all()  # 物化结果，避免被后续循环消耗

    count = 0
    for chunk, doc in rows:
        retriever.add_chunk(
            chunk_id=chunk.id,
            content=chunk.content,
            heading=chunk.heading,
            concepts=chunk.concepts,
            difficulty=chunk.difficulty,
            document_title=doc.title,
            tokens=chunk.tokens or "",
        )
        count += 1

    # 同步重建向量库
    from app.rag.vector_store import rebuild_from_db
    all_chunks_for_vector = [
        {
            "chunk_id": chunk.id,
            "content": chunk.content,
            "heading": chunk.heading or "",
            "concepts": chunk.concepts or "",
            "difficulty": chunk.difficulty,
        }
        for chunk, doc in rows
    ]
    rebuild_from_db(all_chunks_for_vector)

    logger.info("index_rebuilt", tfidf_count=count, vector_count=len(all_chunks_for_vector))
    return count


# =============================================================================
# 检索
# =============================================================================

def _weighted_merge(vector_results: list[dict], tfidf_results: list[dict]) -> list[dict]:
    """A2：向量 + TF-IDF 加权融合。

    score = α·vector_score + (1-α)·tfidf_score，α = settings.RAG_VECTOR_WEIGHT。
    只出现在单一路径的 chunk 直接用该路径分数。
    """
    alpha = settings.RAG_VECTOR_WEIGHT
    merged: dict[str, dict] = {}

    for r in vector_results:
        merged[r["chunk_id"]] = {"data": r, "v": r.get("score", 0.0), "t": None}
    for r in tfidf_results:
        cid = r["chunk_id"]
        if cid in merged:
            merged[cid]["t"] = r.get("score", 0.0)
        else:
            merged[cid] = {"data": r, "v": None, "t": r.get("score", 0.0)}

    result = []
    for cid, entry in merged.items():
        v, t = entry["v"], entry["t"]
        if v is not None and t is not None:
            combined = alpha * v + (1 - alpha) * t
        elif v is not None:
            combined = v
        else:
            combined = t
        d = entry["data"].copy()
        d["score"] = round(combined, 4)
        result.append(d)

    result.sort(key=lambda x: x.get("score", 0), reverse=True)
    return result


async def retrieve_context(
    db: AsyncSession,
    request: RAGRetrievalRequest,
) -> RAGRetrievalResponse:
    """
    检索相关知识片段。

    流程：检索 → 重排序 → 返回结构化结果

    参数:
        db: 数据库会话
        request: 检索请求

    返回:
        RAGRetrievalResponse: 含检索结果列表和元数据
    """
    import time
    start_time = time.perf_counter()

    # 步骤 1：向量检索（ChromaDB) + TF-IDF 混合
    from app.rag.vector_store import is_model_available, search_async as vector_search

    # 向量检索（仅在 embedding 模型可用时执行）
    vector_results = []
    if is_model_available():
        try:
            vector_results = await asyncio.wait_for(
                vector_search(
                    query=request.query,
                    top_k=request.top_k * 2,
                    difficulty_filter=request.difficulty_filter,
                    concept_filter=request.concept_filter,
                ),
                timeout=12.0,
            )
        except (asyncio.TimeoutError, Exception) as e:
            logger.warning(
                "vector_search_failed",
                query=request.query[:60],
                error=str(e)[:120],
            )

    # TF-IDF 关键词检索（补充精确匹配）
    tfidf_results = retriever.search(
        query=request.query,
        top_k=request.top_k,
        difficulty_filter=request.difficulty_filter,
        concept_filter=request.concept_filter,
    )

    # 合并去重
    if settings.ENABLE_HYBRID_WEIGHTS:
        # A2：向量 + TF-IDF 加权融合（score = α·vector + (1-α)·tfidf）
        candidates = _weighted_merge(vector_results, tfidf_results)
    else:
        # 旧逻辑：向量优先，TF-IDF 补充
        seen = set()
        candidates = []
        for r in vector_results + tfidf_results:
            if r["chunk_id"] not in seen:
                seen.add(r["chunk_id"])
                candidates.append(r)

    if not candidates:
        return RAGRetrievalResponse(
            query=request.query,
            results=[],
            total_hits=0,
            retrieval_time_ms=0,
        )

    # 步骤 2：重排序（A1：LLM 重排序，开关控制）
    if settings.ENABLE_RAG_RERANK:
        try:
            reranked = await rerank_with_llm(request.query, candidates, request.top_k)
        except Exception as e:
            logger.warning("rag_rerank_failed", query=request.query[:60], error=str(e)[:120])
            reranked = candidates[:request.top_k]
    else:
        reranked = candidates[:request.top_k]

    # 步骤 3：更新检索统计（非关键副作用，失败不阻断检索、不毒化会话）
    chunk_ids = [r["chunk_id"] for r in reranked]
    if chunk_ids:
        try:
            chunks_to_update = (await db.execute(
                select(RAGChunk).where(RAGChunk.id.in_(chunk_ids))
            )).scalars().all()
            for chunk in chunks_to_update:
                chunk.retrieval_count += 1
            await db.commit()
        except Exception as e:
            # 统计更新失败不影响检索结果；回滚避免 PendingRollbackError 污染后续 commit
            await db.rollback()
            logger.warning("retrieval_count_update_failed", error=str(e)[:120])

    elapsed = (time.perf_counter() - start_time) * 1000

    # 步骤 4：组装结果
    results = []
    for r in reranked:
        results.append(RAGRetrievalResult(
            chunk_id=r["chunk_id"],
            document_title=r.get("document_title", ""),
            heading=r.get("heading"),
            content=r["content"],
            score=r.get("rerank_score") or r.get("score", 0),
            difficulty=r.get("difficulty", ""),
            concepts=r.get("concepts"),
        ))

    logger.info(
        "retrieval_completed",
        query=request.query[:80],
        result_count=len(results),
        duration_ms=round(elapsed, 2),
    )

    return RAGRetrievalResponse(
        query=request.query,
        results=results,
        total_hits=len(results),
        retrieval_time_ms=round(elapsed, 2),
    )


# =============================================================================
# 知识上下文格式化（用于注入到 LLM Prompt）
# =============================================================================

def format_context_for_llm(retrieval_results: list[RAGRetrievalResult]) -> str:
    """
    将检索结果格式化为可注入 System Prompt 的上下文字符串。

    格式：
        [知识点 1] 标题: xxx
        内容: xxx

        [知识点 2] 标题: xxx
        内容: xxx

    参数:
        retrieval_results: 检索结果列表

    返回:
        str: 格式化的上下文字符串
    """
    if not retrieval_results:
        return ""

    # A6：上下文压缩（开关控制）
    if settings.ENABLE_CONTEXT_COMPRESSION:
        return _format_compressed(retrieval_results)

    parts = []
    for i, result in enumerate(retrieval_results, 1):
        heading = result.heading or result.document_title
        parts.append(
            f"[知识点 {i}] {heading}\n"
            f"内容: {result.content}\n"
            f"相关度: {result.score}"
        )

    return "\n\n".join(parts)


def _format_compressed(retrieval_results: list[RAGRetrievalResult]) -> str:
    """A6：按 token 预算压缩 RAG 上下文。

    策略：
    - 高相关 chunk（排序靠前）保留全文，直到预算的 ~70%。
    - 剩余 chunk 压缩为「标题 + 首句」。
    """
    budget = settings.RAG_CONTEXT_MAX_TOKENS
    full_budget = int(budget * 0.7)

    parts = []
    used = 0
    for i, result in enumerate(retrieval_results, 1):
        heading = result.heading or result.document_title
        if used < full_budget:
            body = result.content
            used += estimate_tokens(result.content)
        else:
            # 压缩：标题 + 首句
            first_sentence = _first_sentence(result.content)
            body = f"{first_sentence} …（已压缩）"
            used += estimate_tokens(body)
        parts.append(
            f"[知识点 {i}] {heading}\n"
            f"内容: {body}\n"
            f"相关度: {result.score}"
        )

    return "\n\n".join(parts)


def _first_sentence(text: str, max_len: int = 80) -> str:
    """取文本首句（按中文句号/换行截断），用于压缩展示。"""
    text = (text or "").strip()
    for sep in ("。", "\n", ". "):
        idx = text.find(sep)
        if idx != -1:
            return text[:idx + 1].strip()
    return text[:max_len]
