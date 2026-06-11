"""
RAG 服务模块
===========

负责知识文档的导入、索引、检索和问答增强。

核心流程：
1. 文档导入：读取 Markdown → 切分成 chunk → 存入数据库 → 加入检索索引
2. 检索：查询 → TF-IDF 检索 → LLM 重排序 → 返回 Top-N 上下文
3. 增强回答：检索结果拼入 Prompt → LLM 生成带知识背景的回答
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rag import RAGChunk, RAGDocument
from app.observability.logger import get_logger
from app.rag.retriever import HybridRetriever, retriever
from app.rag.reranker import rerank_with_llm
from app.rag.splitter import simple_tokenize, split_markdown
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

    count = 0
    for chunk, doc in result:
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
        for chunk, doc in result
    ]
    rebuild_from_db(all_chunks_for_vector)

    logger.info("index_rebuilt", tfidf_count=count, vector_count=len(all_chunks_for_vector))
    return count


# =============================================================================
# 检索
# =============================================================================

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

    # 步骤 1：向量检索（ChromaDB） + TF-IDF 混合
    from app.rag.vector_store import search as vector_search

    # 向量检索
    vector_results = vector_search(
        query=request.query,
        top_k=request.top_k * 2,
        difficulty_filter=request.difficulty_filter,
        concept_filter=request.concept_filter,
    )

    # TF-IDF 关键词检索（补充精确匹配）
    tfidf_results = retriever.search(
        query=request.query,
        top_k=request.top_k,
        difficulty_filter=request.difficulty_filter,
        concept_filter=request.concept_filter,
    )

    # 合并去重（向量优先，TF-IDF 补充）
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

    # 步骤 2：简化为直接取 Top-K（跳过 LLM 重排序以加速）
    reranked = candidates[:request.top_k]

    # 步骤 3：更新检索统计
    chunk_ids = [r["chunk_id"] for r in reranked]
    if chunk_ids:
        _ = await db.execute(
            select(RAGChunk).where(RAGChunk.id.in_(chunk_ids))
        )
        chunks_to_update = (await db.execute(
            select(RAGChunk).where(RAGChunk.id.in_(chunk_ids))
        )).scalars().all()
        for chunk in chunks_to_update:
            chunk.retrieval_count += 1
        await db.commit()

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

    parts = []
    for i, result in enumerate(retrieval_results, 1):
        heading = result.heading or result.document_title
        parts.append(
            f"[知识点 {i}] {heading}\n"
            f"内容: {result.content}\n"
            f"相关度: {result.score}"
        )

    return "\n\n".join(parts)
