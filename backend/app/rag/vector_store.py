"""
向量存储服务 (ChromaDB + sentence-transformers)
================================================

升级替代原 TF-IDF 内存检索，提供：
- 语义向量检索（不再只用关键词）
- 元数据过滤（难度、知识点）
- 持久化存储（ChromaDB 自动保存到磁盘）
"""

from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer

from app.observability.logger import get_logger

logger = get_logger(__name__)

# 全局单例
_embedding_model: Optional[SentenceTransformer] = None
_chroma_client = None
_collection = None


def get_embedding_model() -> SentenceTransformer:
    """获取 embedding 模型（延迟加载单例）。"""
    global _embedding_model
    if _embedding_model is None:
        # 中文优化的小模型，100MB，CPU 可用
        _embedding_model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
        logger.info("embedding_model_loaded", model="paraphrase-multilingual-MiniLM-L12-v2")
    return _embedding_model


def get_collection() -> chromadb.Collection:
    """获取 ChromaDB collection（延迟加载单例）。"""
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(
            path="./chroma_db",
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = _chroma_client.get_or_create_collection(
            name="python_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("chromadb_collection_ready", count=_collection.count())
    return _collection


def add_chunks(chunks: list[dict]) -> int:
    """
    批量添加 chunk 到向量库。

    参数:
        chunks: [{content, heading, concepts, difficulty, chunk_id}, ...]

    返回:
        添加的数量
    """
    if not chunks:
        return 0

    model = get_embedding_model()
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

    # 生成 embeddings
    embeddings = model.encode(texts, show_progress_bar=False).tolist()

    collection.add(ids=ids, embeddings=embeddings, documents=texts, metadatas=metadatas)
    logger.info("chunks_added_to_vectordb", count=len(chunks))
    return len(chunks)


def search(
    query: str,
    top_k: int = 5,
    difficulty_filter: Optional[str] = None,
    concept_filter: Optional[str] = None,
) -> list[dict]:
    """
    向量检索。

    返回:
        [{chunk_id, content, heading, score, difficulty, concepts}, ...]
    """
    collection = get_collection()
    model = get_embedding_model()

    if collection.count() == 0:
        return []

    query_embedding = model.encode([query], show_progress_bar=False).tolist()

    # 构建过滤条件
    where_filter = None
    if difficulty_filter:
        where_filter = {"difficulty": difficulty_filter}

    results = collection.query(
        query_embeddings=query_embedding,
        n_results=min(top_k * 3, collection.count()),  # 多检索一些，后续可选 rerank
        where=where_filter,
        include=["documents", "metadatas", "distances"],
    )

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

    # 按得分排序取 top_k
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:top_k]


def clear_collection():
    """清空向量库。"""
    global _collection
    if _chroma_client:
        try:
            _chroma_client.delete_collection("python_knowledge")
        except Exception:
            pass
        _collection = _chroma_client.get_or_create_collection(
            name="python_knowledge",
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("chromadb_collection_cleared")


def rebuild_from_db(chunks_from_db: list[dict]) -> int:
    """从数据库重建整个向量索引。"""
    clear_collection()
    return add_chunks(chunks_from_db)
