"""
初始知识库数据导入脚本
======================

预置 Python 基础知识点，让 RAG 知识库有初始内容。
数据本体在 app/rag/seed_data.py；应用启动时若知识库为空会自动调用同一个函数，
这个脚本用于手动补种或重新导入。

运行方式：
    cd backend
    python scripts/seed_knowledge.py

注意：重复执行会产生重复文档，重新导入前先清空 rag_documents / rag_chunks。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import AsyncSessionFactory
from app.rag.retriever import retriever
from app.rag.seed_data import KNOWLEDGE_BASE, seed_knowledge


async def main():
    print(f"开始导入知识库（{len(KNOWLEDGE_BASE)} 篇）...")
    async with AsyncSessionFactory() as db:
        count = await seed_knowledge(db)
    print(f"\n导入完成！共 {count} 篇文档，索引中 {len(retriever._chunks)} 个 chunk。")


if __name__ == "__main__":
    asyncio.run(main())
