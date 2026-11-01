"""
聊天链路降级测试
================

历史问题（都会让一次 RAG/LLM 故障变成 500 或丢消息）：

1. RAG 检索失败时 `await db.rollback()`，把尚未提交的用户消息一起回滚，
   后面 `db.refresh(user_msg)` 抛 InvalidRequestError（会话里没有这个对象了）；
2. LLM 生成失败时先 rollback 再 commit，看似"保存用户消息"，其实什么都没存下。
"""

import pytest
from sqlalchemy import select
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
from app.models.chat import ChatMessage, ChatSession
from app.models.user import User, UserRole
from app.schemas.chat import AIResponse, SendMessageRequest
from app.services import chat_service
from app.services.rag_service import RAGBreaker


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'chat.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture(autouse=True)
def reset_breaker():
    RAGBreaker._fail_count = 0
    RAGBreaker._open_until = 0.0
    yield
    RAGBreaker._fail_count = 0
    RAGBreaker._open_until = 0.0


async def make_session(db) -> tuple[User, ChatSession]:
    user = User(
        id="u-chat", email="u-chat@example.com", password_hash="x",
        display_name="u-chat", role=UserRole.STUDENT,
    )
    db.add(user)
    await db.flush()
    session = ChatSession(id="sess-1", student_id=user.id, title="新对话")
    db.add(session)
    await db.commit()
    return user, session


async def _messages(db, session_id: str) -> list[ChatMessage]:
    return list((await db.execute(
        select(ChatMessage).where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )).scalars().all())


async def test_rag_failure_does_not_break_turn(db, monkeypatch):
    """RAG 挂了只是没有上下文，对话照常完成，用户消息不丢。"""
    from app.services import rag_service

    async def boom(*args, **kwargs):
        raise TimeoutError("dashscope timeout")

    monkeypatch.setattr(rag_service, "retrieve_context", boom)

    async def fake_tutor(**kwargs):
        return AIResponse(response_type="general", message="好的，我们来看循环。")

    monkeypatch.setattr(chat_service, "generate_tutor_response", fake_tutor)

    user, session = await make_session(db)
    result = await chat_service.send_message(
        db, session.id, user, SendMessageRequest(content="for 循环怎么用？"),
    )

    assert result["assistant_message"].content == "好的，我们来看循环。"
    stored = await _messages(db, session.id)
    assert [m.role for m in stored] == ["user", "assistant"]
    assert stored[0].content == "for 循环怎么用？"


async def test_llm_failure_still_persists_user_message(db, monkeypatch):
    """AI 生成失败：用户消息必须已经落库，接口返回 503。"""
    from fastapi import HTTPException

    async def boom(**kwargs):
        raise RuntimeError("deepseek 503")

    monkeypatch.setattr(chat_service, "generate_tutor_response", boom)

    user, session = await make_session(db)
    with pytest.raises(HTTPException) as exc:
        await chat_service.send_message(
            db, session.id, user, SendMessageRequest(content="解释一下字典"),
        )
    assert exc.value.status_code == 503

    stored = await _messages(db, session.id)
    assert len(stored) == 1
    assert stored[0].role == "user"
    assert stored[0].content == "解释一下字典"


async def test_unknown_model_is_rejected(db):
    from fastapi import HTTPException

    user, session = await make_session(db)
    with pytest.raises(HTTPException) as exc:
        await chat_service.send_message(
            db, session.id, user,
            SendMessageRequest(content="你好", model="openai/gpt-4o"),
        )
    assert exc.value.status_code == 400
    assert await _messages(db, session.id) == []


def test_model_choice_is_normalized():
    """裸模型名要补上 provider 前缀，否则 litellm 不认。"""
    assert chat_service.resolve_model_choice(None) is None
    assert chat_service.resolve_model_choice("deepseek-v4-pro") == "deepseek/deepseek-v4-pro"
    assert chat_service.resolve_model_choice("deepseek/deepseek-chat") == "deepseek/deepseek-chat"
