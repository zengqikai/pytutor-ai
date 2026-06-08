"""
聊天 API
========

提供聊天会话和消息的接口。

接口列表：
    POST   /api/v1/chat/sessions              - 创建新会话
    GET    /api/v1/chat/sessions              - 获取会话列表
    GET    /api/v1/chat/sessions/{id}         - 获取会话详情（含消息）
    POST   /api/v1/chat/sessions/{id}/messages - 发送消息（获取 AI 回复）
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.user import User
from app.schemas.chat import (
    CreateSessionRequest,
    SendMessageRequest,
    SessionListItem,
    SessionResponse,
)
from app.security.dependencies import get_current_user
from app.services.chat_service import create_session, get_session, list_sessions, send_message

router = APIRouter()


@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_chat_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建新的 AI 导师聊天会话。

    请求示例:
        {"title": "学习 for 循环"}

    响应:
        新创建的会话对象（含 id、title、空消息列表）
    """
    return await create_session(db, current_user, request)


@router.get("/sessions", response_model=list[SessionListItem])
async def list_chat_sessions(
    limit: int = Query(default=20, ge=1, le=50, description="返回条数"),
    offset: int = Query(default=0, ge=0, description="偏移量"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取当前用户的会话列表（按更新时间倒序）。

    每个会话包含标题和最后一条消息的预览。
    """
    return await list_sessions(db, current_user, limit=limit, offset=offset)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取会话详情（包含所有消息历史）。
    """
    return await get_session(db, session_id, current_user)


@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除会话。"""
    from sqlalchemy import select as sa_select
    from app.models.chat import ChatSession
    result = await db.execute(sa_select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        return {"detail": "会话不存在"}
    if session.student_id != current_user.id:
        return {"detail": "无权操作"}
    await db.delete(session)
    await db.commit()
    return {"detail": "已删除"}


@router.patch("/sessions/{session_id}")
async def rename_chat_session(
    session_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """重命名会话（双击标题编辑）。"""
    from sqlalchemy import select as sa_select
    from app.models.chat import ChatSession

    result = await db.execute(sa_select(ChatSession).where(ChatSession.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        return {"detail": "会话不存在"}
    if session.student_id != current_user.id:
        return {"detail": "无权操作"}
    title = body.get("title", "").strip()
    if title:
        session.title = title[:100]
        await db.commit()
    return {"id": session.id, "title": session.title}


@router.post("/sessions/{session_id}/messages")
async def send_chat_message(
    session_id: str,
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    发送消息并获取 AI 导师的结构化回复。

    请求示例:
        {"content": "什么是 Python 中的 for 循环？"}

    响应包含三部分:
        - user_message: 刚保存的用户消息
        - assistant_message: AI 的回复消息
        - ai_response: 结构化的 AI 响应（response_type, hint_level, related_concepts, next_action...）

    如果消息中包含 ```python 代码块，AI 会自动切换到代码审查模式。
    """
    return await send_message(db, session_id, current_user, request, model=request.model)
