"""
聊天服务模块
============

负责聊天会话和消息的业务逻辑：
- 创建/获取/关闭会话
- 发送消息 + 生成 AI 回复
- 获取历史记录
"""

import json

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import ChatMessage, ChatSession
from app.models.user import User
from app.observability.logger import get_logger
from app.schemas.chat import (
    AIResponse,
    CreateSessionRequest,
    MessageResponse,
    SendMessageRequest,
    SessionListItem,
    SessionResponse,
)
from app.services.tutor_service import generate_tutor_response

logger = get_logger(__name__)


# =============================================================================
# 会话管理
# =============================================================================

async def create_session(
    db: AsyncSession,
    user: User,
    request: CreateSessionRequest,
) -> SessionResponse:
    """
    创建新的聊天会话。

    参数:
        db: 数据库会话
        user: 当前用户
        request: 创建请求（含标题）

    返回:
        SessionResponse: 新创建的会话（含空消息列表）
    """
    session = ChatSession(
        student_id=user.id,
        title=request.title,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    logger.info("chat_session_created", session_id=session.id, user_id=user.id)

    # 新会话没有消息，手动构造响应（避免异步懒加载问题）
    return SessionResponse(
        id=session.id,
        title=session.title,
        is_active=session.is_active,
        messages=[],  # 新会话无消息
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


async def get_session(
    db: AsyncSession,
    session_id: str,
    user: User,
) -> SessionResponse:
    """
    获取会话详情（含所有消息）。

    安全检查：学生只能看自己的会话，教师和管理员可以看所有。
    """
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .options(selectinload(ChatSession.messages))  # 预加载消息（避免 N+1 查询）
    )
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 权限检查：学生只能访问自己的会话
    if user.role == "student" and session.student_id != user.id:
        raise HTTPException(status_code=403, detail="无权访问此会话")

    return SessionResponse.model_validate(session)


async def list_sessions(
    db: AsyncSession,
    user: User,
    limit: int = 20,
    offset: int = 0,
) -> list[SessionListItem]:
    """
    获取用户的会话列表（按更新时间倒序）。

    只返回摘要信息（标题 + 最后消息预览），不含完整消息内容。
    """
    query = (
        select(ChatSession)
        .where(
            ChatSession.student_id == user.id,
            ChatSession.is_active == True,
        )
        .order_by(ChatSession.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(query)
    sessions = result.scalars().all()

    # 组装列表项（含消息计数和最后消息预览）
    items = []
    for s in sessions:
        # 获取消息数量
        count_result = await db.execute(
            select(func.count()).where(ChatMessage.session_id == s.id)
        )
        msg_count = count_result.scalar() or 0

        # 获取最后一条消息的预览
        last_msg_result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.session_id == s.id)
            .order_by(ChatMessage.created_at.desc())
            .limit(1)
        )
        last_msg = last_msg_result.scalar_one_or_none()

        items.append(SessionListItem(
            id=s.id,
            title=s.title,
            is_active=s.is_active,
            message_count=msg_count,
            last_message_preview=last_msg.content[:100] if last_msg else None,
            created_at=s.created_at,
            updated_at=s.updated_at,
        ))

    return items


# =============================================================================
# 消息处理
# =============================================================================

async def send_message(
    db: AsyncSession,
    session_id: str,
    user: User,
    request: SendMessageRequest,
    model: str | None = None,
) -> dict:
    """
    发送消息并获取 AI 回复。

    完整流程：
    1. 验证会话权限
    2. 保存用户消息
    3. 获取对话历史
    4. 调用 AI 导师生成回复
    5. 保存 AI 回复
    6. 更新会话标题（如果是第一条消息，用问题内容作为标题）
    7. 返回 AI 回复

    参数:
        db: 数据库会话
        session_id: 会话 ID
        user: 当前用户
        request: 消息内容

    返回:
        dict: 含用户消息和 AI 回复
    """
    # 步骤 1：验证会话
    session_result = await db.execute(
        select(ChatSession)
        .where(ChatSession.id == session_id)
        .options(selectinload(ChatSession.messages))
    )
    session = session_result.scalar_one_or_none()

    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")

    if session.student_id != user.id:
        raise HTTPException(status_code=403, detail="无权操作此会话")

    # 步骤 1.5：检查是否首条消息（必须在 add 之前，否则 auto-flush 会提前写入）
    from sqlalchemy import func as sa_func, select as sa_select
    count_result = await db.execute(
        sa_select(sa_func.count()).select_from(ChatMessage).where(ChatMessage.session_id == session_id)
    )
    is_first_message = (count_result.scalar() or 0) == 0

    # 步骤 2：保存用户消息
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=request.content,
    )
    db.add(user_msg)

    # 步骤 3：获取对话历史（不含刚保存的用户消息）
    history = []
    for msg in session.messages:
        history.append({
            "role": msg.role,
            "content": msg.content,
            "hint_level": msg.hint_level,
        })

    # 步骤 4：RAG 检索相关知识
    rag_context = None
    try:
        from app.schemas.rag import RAGRetrievalRequest
        from app.services.rag_service import format_context_for_llm, retrieve_context

        retrieval_result = await retrieve_context(
            db,
            RAGRetrievalRequest(query=request.content, top_k=3),
        )
        if retrieval_result.results:
            rag_context = format_context_for_llm(retrieval_result.results)
            logger.info(
                "rag_context_retrieved",
                session_id=session_id,
                chunk_count=len(retrieval_result.results),
            )
    except Exception as e:
        # RAG 检索失败不影响对话（降级到无知识库模式）
        logger.warning("rag_retrieval_failed", session_id=session_id, error=str(e))

    # 步骤 5：调用 AI 导师
    try:
        ai_response: AIResponse = await generate_tutor_response(
            user_message=request.content,
            conversation_history=history,
            student_level="beginner",
            rag_context=rag_context,
            model=model,
        )
    except Exception as e:
        logger.error("ai_generation_failed", session_id=session_id, error=str(e))
        # 即使 AI 失败，用户消息也要保存
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="AI 服务暂时不可用，请稍后重试",
        )

    # 步骤 5：保存 AI 回复
    # content 只存消息文本；结构化字段存到独立列（便于前端渲染和 SQL 查询）
    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=ai_response.message,  # 只存纯文本 Markdown，不存 JSON
        response_type=ai_response.response_type,
        hint_level=ai_response.hint_level,
        related_concepts=",".join(ai_response.related_concepts) if ai_response.related_concepts else None,
        next_action=ai_response.next_action,
    )
    db.add(assistant_msg)

    # 步骤 6：首条消息时自动更新标题
    if is_first_message:
        session.title = request.content[:40] + ("..." if len(request.content) > 40 else "")

    await db.commit()
    await db.refresh(user_msg)
    await db.refresh(assistant_msg)

    logger.info(
        "chat_message_sent",
        session_id=session_id,
        user_id=user.id,
        response_type=ai_response.response_type,
        hint_level=ai_response.hint_level,
    )

    # 步骤 7：返回
    return {
        "user_message": MessageResponse.model_validate(user_msg),
        "assistant_message": MessageResponse.model_validate(assistant_msg),
        "ai_response": ai_response,  # 也返回原始结构化对象，方便前端直接使用
    }
