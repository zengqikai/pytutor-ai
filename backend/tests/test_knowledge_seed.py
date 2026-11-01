"""
知识库自动导入测试
==================

对应任务 09 的验收："空库首次启动即可使用知识库"。

这里不调用真实 embedding API，只验证导入决策：
空库会导入全部条目、单篇失败不中断、已有数据不会重复导入。
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.rag  # noqa: F401
from app.database.base import Base
from app.models.rag import RAGDocument
from app.rag import seed_data
from app.rag.seed_data import KNOWLEDGE_BASE, ensure_knowledge_seeded


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'kb.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def fake_ingest(monkeypatch):
    """替换 ingest_document，记录标题并返回一个占位文档对象。"""
    calls = []

    async def _fake(db, title, content, difficulty, concepts):
        calls.append(title)
        return type("Doc", (), {"title": title})()

    monkeypatch.setattr("app.services.rag_service.ingest_document", _fake)
    return calls


async def test_empty_db_imports_whole_knowledge_base(db, fake_ingest):
    count = await ensure_knowledge_seeded(db)
    assert count == len(KNOWLEDGE_BASE)
    assert fake_ingest == [kb["title"] for kb in KNOWLEDGE_BASE]


async def test_second_start_does_not_duplicate(db, fake_ingest):
    await ensure_knowledge_seeded(db)
    db.add(RAGDocument(title="已有文档", content="x", difficulty="beginner"))
    await db.commit()

    fake_ingest.clear()
    assert await ensure_knowledge_seeded(db) == 0
    assert fake_ingest == []


async def test_single_failure_does_not_stop_import(db, monkeypatch):
    async def _flaky(db, title, content, difficulty, concepts):
        if title == KNOWLEDGE_BASE[0]["title"]:
            raise RuntimeError("embedding api down")
        return type("Doc", (), {"title": title})()

    monkeypatch.setattr("app.services.rag_service.ingest_document", _flaky)
    count = await seed_data.seed_knowledge(db)
    assert count == len(KNOWLEDGE_BASE) - 1
