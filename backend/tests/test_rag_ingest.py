"""
RAG 文档导入 / 删除的回归测试
============================

历史问题：
- `ingest_document` 用 `doc.chunks` 构造向量数据，未加载的 relationship 在
  async 会话里抛 MissingGreenlet，`POST /rag/documents` 直接 500，
  启动时的知识库种子也永远写不进向量库；
- `DELETE /rag/documents/{id}` 只删 DB 和 TF-IDF，ChromaDB 里的旧片段
  仍然会被检索到。

这里用替身接管 embedding/ChromaDB，测试不联网、不写开发库。
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.chat  # noqa: F401
import app.models.exercise  # noqa: F401
import app.models.misconception  # noqa: F401
import app.models.profile  # noqa: F401
import app.models.prompt  # noqa: F401
import app.models.rag  # noqa: F401
import app.models.submission  # noqa: F401
import app.models.user  # noqa: F401
from app.database.base import Base
from app.models.rag import RAGChunk
from app.services import rag_service


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'rag.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def fake_indexes(monkeypatch):
    """记录写入/删除的向量与 TF-IDF 片段，不触碰真实 index。"""
    vector_added: list[dict] = []
    vector_deleted: list[str] = []
    tfidf_added: list[str] = []

    monkeypatch.setattr(
        "app.rag.vector_store.add_chunks",
        lambda chunks: (vector_added.extend(chunks), len(chunks))[1],
    )
    monkeypatch.setattr(
        "app.rag.vector_store.delete_chunks",
        lambda ids: (vector_deleted.extend(ids), len(ids))[1],
    )
    monkeypatch.setattr(
        "app.rag.retriever.retriever.add_chunk",
        lambda **kw: tfidf_added.append(kw["chunk_id"]),
    )
    monkeypatch.setattr("app.rag.retriever.retriever.remove_chunk", lambda cid: None)

    return {
        "vector_added": vector_added,
        "vector_deleted": vector_deleted,
        "tfidf_added": tfidf_added,
    }


async def test_ingest_writes_chunks_to_db_and_vector_store(db, fake_indexes):
    """导入文档：DB、TF-IDF、向量库三处都要有，且不抛 MissingGreenlet。"""
    doc = await rag_service.ingest_document(
        db,
        title="for 循环入门",
        content="# 标题\n\n这是第一段内容，讲 for 循环。\n\n## 小节\n\n这是第二段内容。",
        difficulty="beginner",
        concepts="for_loop",
    )

    chunks = (await db.execute(
        RAGChunk.__table__.select().where(RAGChunk.document_id == doc.id)
    )).all()

    assert len(chunks) > 0
    assert getattr(doc, "_chunk_count") == len(chunks)
    assert len(fake_indexes["vector_added"]) == len(chunks)
    assert len(fake_indexes["tfidf_added"]) == len(chunks)
    assert {c["chunk_id"] for c in fake_indexes["vector_added"]} == {c.id for c in chunks}


async def test_delete_document_also_clears_vector_store(db, fake_indexes):
    """删除文档：DB、TF-IDF、向量库一起清，不能留下检索得到的孤儿片段。"""
    from app.api.v1.rag import delete_document
    from app.models.user import User, UserRole

    doc = await rag_service.ingest_document(
        db, title="while 循环", content="# 标题\n\n循环体内容。", concepts="while_loop",
    )
    chunk_ids = {c["chunk_id"] for c in fake_indexes["vector_added"]}

    admin = User(
        id="admin-1", email="admin@example.com", password_hash="x",
        display_name="admin", role=UserRole.ADMIN,
    )
    db.add(admin)
    await db.commit()

    result = await delete_document(document_id=doc.id, db=db, current_user=admin)

    assert result["chunk_count"] == len(chunk_ids)
    assert set(fake_indexes["vector_deleted"]) == chunk_ids
    remaining = (await db.execute(
        RAGChunk.__table__.select().where(RAGChunk.document_id == doc.id)
    )).all()
    assert remaining == []


async def test_create_document_response_reports_chunk_count(db, fake_indexes):
    """POST /rag/documents 的 chunk_count 不能再去读 lazy relationship。"""
    from app.api.v1.rag import create_document
    from app.models.user import User, UserRole
    from app.schemas.rag import RAGDocumentCreate

    user = User(
        id="admin-2", email="admin2@example.com", password_hash="x",
        display_name="admin2", role=UserRole.ADMIN,
    )
    db.add(user)
    await db.commit()

    response = await create_document(
        request=RAGDocumentCreate(
            title="列表基础", content="# 标题\n\n列表内容一。\n\n列表内容二。",
            difficulty="beginner", concepts="list",
        ),
        db=db,
        current_user=user,
    )

    assert response.chunk_count > 0
