"""
向量存储服务 (ChromaDB + DashScope Embedding)
===============================================

提供：
- 语义向量检索（DashScope text-embedding-v3 API）
- 元数据过滤（难度、知识点）
- 持久化存储（ChromaDB 自动保存到磁盘）
- 异步友好：API 调用不阻塞事件循环
- 自动降级：API 不可用 → 返回空结果 → 上层回退 TF-IDF

注意：不再依赖本地 sentence-transformers，无模型下载问题。
"""

import asyncio
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.observability.logger import get_logger
from app.rag.embedding import get_embedding, is_embedding_available

logger = get_logger(__name__)

# 全局单例
_chroma_client = None
_collection = None


def get_collection() -> chromadb.Collection:
    """获取 ChromaDB collection（延迟加载单例）。"""
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _chroma_client.get_or_create_collection(
            name="python_knowledge_v2",  # v2: 新的 embedding 维度
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("chromadb_collection_ready", name="python_knowledge_v2", count=_collection.count())
    return _collection


# =============================================================================
# 模型状态查询（兼容旧接口）
# =============================================================================

def is_model_available() -> bool:
    """检查 embedding 服务是否可用。"""
    return is_embedding_available()


# =============================================================================
# 文档索引
# =============================================================================

def add_chunks(chunks: list[dict]) -> int:
    """
    批量添加 chunk 到向量库。

    参数:
        chunks: [{content, heading, concepts, difficulty, chunk_id}, ...]

    返回:
        添加的数量。如果 embedding 服务不可用，返回 0（不写入 ChromaDB，
        仅依赖 TF-IDF 检索）。
    """
    if not chunks:
        return 0

    embedding = get_embedding()
    if embedding is None:
        logger.warning("embedding_unavailable_skip_index", count=len(chunks))
        return 0

    collection = get_collection()

    ids = [c["chunk_id"] for c in chunks]
    texts = [c["content"] for c in chunks]
    metadatas = [
        {
            "heading": c.get("heading", ""),
            "concepts": c.get("concepts", ""),
            "difficulty": c.get("difficulty", "beginner"),
        }
        for c in chunks
    ]

    # 通过 API 生成 embeddings
    try:
        embeddings = embedding.encode(texts)
    except Exception as e:
        logger.error("embedding_encode_failed", error=str(e)[:200])
        return 0

    collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    logger.info("chunks_added_to_vectordb", count=len(chunks))
    return len(chunks)


# =============================================================================
# 检索
# =============================================================================

def search(
    query: str,
    top_k: int = 5,
    difficulty_filter: Optional[str] = None,
    concept_filter: Optional[str] = None,
) -> list[dict]:
    """
    向量检索（同步版本）。

    返回:
        [{chunk_id, content, heading, score, difficulty, concepts}, ...]
    """
    embedding = get_embedding()
    if embedding is None:
        return []

    collection = get_collection()
    if collection.count() == 0:
        return []

    try:
        query_embeddings = embedding.encode([query])
    except Exception:
        return []

    where_filter = None
    if difficulty_filter:
        where_filter = {"difficulty": difficulty_filter}

    results = collection.query(
        query_embeddings=query_embeddings,
        n_results=min(top_k * 3, collection.count()),
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

    return _process_search_results(results, concept_filter)[:top_k]


async def search_async(
    query: str,
    top_k: int = 5,
    difficulty_filter: Optional[str] = None,
    concept_filter: Optional[str] = None,
) -> list[dict]:
    """
    向量检索（异步安全版本）。

    通过 DashScope API 获取查询向量，不阻塞事件循环。
    API 失败时自动返回空结果（上层回退 TF-IDF）。

    返回:
        [{chunk_id, content, heading, score, difficulty, concepts}, ...]
    """
    embedding = get_embedding()
    if embedding is None:
        return []

    collection = get_collection()
    if collection.count() == 0:
        return []

    # 异步获取查询向量
    query_embeddings = await embedding.encode_async([query])
    if query_embeddings is None:
        # API 失败 → 返回空，让上层用 TF-IDF
        return []

    # ChromaDB 查询（同步但很快，在线程池中执行）
    where_filter = None
    if difficulty_filter:
        where_filter = {"difficulty": difficulty_filter}

    def _query():
        return collection.query(
            query_embeddings=query_embeddings,
            n_results=min(top_k * 3, collection.count()),
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

    loop = asyncio.get_running_loop()
    results = await loop.run_in_executor(None, _query)

    return _process_search_results(results, concept_filter)[:top_k]


def _process_search_results(results, concept_filter: Optional[str] = None) -> list[dict]:
    """处理 ChromaDB 查询结果为统一格式。"""
    out = []
    if results["ids"] and results["ids"][0]:
        for i, chunk_id in enumerate(results["ids"][0]):
            metadata = results["metadatas"][0][i] if results["metadatas"] else {}
            distance = results["distances"][0][i] if results["distances"] else 0
            score = 1.0 - min(distance, 1.0)  # 余弦距离 → 相似度

            # 概念过滤
            if concept_filter and concept_filter not in metadata.get("concepts", ""):
                continue

            out.append({
                "chunk_id": chunk_id,
                "content": results["documents"][0][i] if results["documents"] else "",
                "heading": metadata.get("heading", ""),
                "difficulty": metadata.get("difficulty", "beginner"),
                "concepts": metadata.get("concepts", ""),
                "score": round(score, 4),
            })

    out.sort(key=lambda x: x["score"], reverse=True)
    return out


# =============================================================================
# 管理
# =============================================================================

def clear_collection():
    """清空向量库。"""
    global _collection
    if _chroma_client:
        try:
            _chroma_client.delete_collection("python_knowledge_v2")
        except Exception:
            pass
        _collection = _chroma_client.get_or_create_collection(
            name="python_knowledge_v2",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("chromadb_collection_cleared")


def rebuild_from_db(chunks_from_db: list[dict]) -> int:
    """从数据库重建整个向量索引。"""
    clear_collection()
    return add_chunks(chunks_from_db)
