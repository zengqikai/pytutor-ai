"""
RAG 检索测试
============

测试知识库检索和 RAG 增强的聊天。
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import AsyncSessionFactory
from app.rag.retriever import retriever
from app.schemas.rag import RAGRetrievalRequest
from app.services.rag_service import rebuild_index, retrieve_context


async def test_retrieval():
    # 1. 重建索引
    print("===== 1. 重建索引 =====")
    async with AsyncSessionFactory() as db:
        count = await rebuild_index(db)
        print(f"索引中的 chunk 数: {count}")

    # 2. 测试检索
    print("\n===== 2. 检索测试 =====")
    queries = [
        "什么是 Python 列表？",
        "for 循环怎么用？",
        "如何使用 if 判断分数？",
        "字符串怎么拼接？",
    ]

    async with AsyncSessionFactory() as db:
        for q in queries:
            print(f"\n查询: {q}")
            result = await retrieve_context(db, RAGRetrievalRequest(
                query=q,
                top_k=3,
            ))
            for i, r in enumerate(result.results):
                print(f"  [{i+1}] {r.heading or r.document_title} (score={r.score})")
                print(f"       {r.content[:80]}...")

    print("\n===== 全部测试完成! =====")


if __name__ == "__main__":
    asyncio.run(test_retrieval())
