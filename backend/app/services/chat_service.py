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
from app.core.config import settings
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

# 前端只能选这两个模型。直接把这个字段透传给 litellm 意味着客户端可以写到
# 任意 provider（例如 "openai/gpt-4o"），既绕开成本控制也会拿别的供应商 key 去请求。
SUPPORTED_CHAT_MODELS = ("deepseek-chat", "deepseek-v4-pro")


def resolve_model_choice(model: str | None) -> str | None:
    """把前端传来的模型名规范成 litellm 形式（deepseek/xxx），白名单外直接 400。

    前端历史版本传的是裸名（`deepseek-v4-pro`），litellm 不认，会抛
    "LLM Provider NOT provided"，所以这里统一补上 provider 前缀。
    """
    if not model or not model.strip():
        return None

    name = model.strip()
    if "/" in name:
        provider, _, rest = name.partition("/")
        if provider != "deepseek" or rest not in SUPPORTED_CHAT_MODELS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的模型：{model}",
            )
        return name

    if name not in SUPPORTED_CHAT_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的模型：{model}",
        )
    return f"deepseek/{name}"


async def _recover_user_message(
    db: AsyncSession,
    user_msg: ChatMessage,
    session_id: str,
    content: str,
) -> ChatMessage:
    """AI 生成失败时，保证用户消息已经落库且实例可用。

    之前这里是 `rollback()` + `commit()`：回滚把刚 add 的实例踢出了会话，
    随后的 commit 什么也没保住，"即使 AI 失败也要保存用户消息"实际没生效。
    """
    try:
        await db.commit()
    except Exception:
        await db.rollback()

    try:
        await db.refresh(user_msg)
        return user_msg
    except Exception:
        pass

    # 极端情况（实例已被 rollback 分离）：重建一条再保存
    recovered = ChatMessage(session_id=session_id, role="user", content=content)
    db.add(recovered)
    await db.commit()
    await db.refresh(recovered)
    return recovered


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

    # 步骤 1.8：模型白名单（拒绝把任意 provider/model 透传给 litellm）。
    # 兼容两种传法：显式参数优先，其次是请求体里的 model 字段。
    model = resolve_model_choice(model or request.model)

    # 步骤 2：保存用户消息
    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=request.content,
    )
    db.add(user_msg)
    # 先落库再走 RAG/LLM：retrieve_context 内部会 commit 检索计数，rollback 时
    # 又会把尚未提交的用户消息一起丢掉（历史上表现为 refresh 抛 InvalidRequestError）。
    await db.commit()
    await db.refresh(user_msg)

    # 步骤 3：获取对话历史（不含刚保存的用户消息）
    history = []
    for msg in session.messages:
        history.append({
            "role": msg.role,
            "content": msg.content,
            "hint_level": msg.hint_level,
        })

    # 步骤 4：RAG 检索相关知识（熔断 + 3s 超时保护）
    rag_context = None
    from app.services.rag_service import RAGBreaker
    if not RAGBreaker.is_open():
        try:
            import asyncio
            from app.schemas.rag import RAGRetrievalRequest
            from app.services.rag_service import format_context_for_llm, retrieve_context

            retrieval_result = await asyncio.wait_for(
                retrieve_context(
                    db,
                    RAGRetrievalRequest(query=request.content, top_k=3),
                ),
                timeout=10.0,  # DashScope 向量检索约 2-3s，3s 太紧会导致取消中断
            )
            if retrieval_result.results:
                rag_context = format_context_for_llm(retrieval_result.results)
                RAGBreaker.record_ok()
                logger.info(
                    "rag_context_retrieved",
                    session_id=session_id,
                    chunk_count=len(retrieval_result.results),
                )
        except Exception as e:
            # 不 rollback：用户消息上一步已经提交，这里回滚只会白白拆掉后续要用的
            # 会话状态，还会让 `db.refresh(user_msg)` 抛 InvalidRequestError。
            # RAG 是可选增强，失败就当作没有上下文。
            RAGBreaker.record_fail()
            logger.warning("rag_retrieval_failed", session_id=session_id, error=str(e)[:100])
    else:
        logger.info("rag_circuit_open", session_id=session_id)

    # 步骤 4.5：误区诊断（如果消息中包含代码）
    misconception_result = None
    if "```python" in request.content or "```" in request.content or "def " in request.content:
        try:
            from app.services.misconception_service import diagnose as mc_diagnose
            # 提取代码块
            import re
            code_match = re.search(r'```(?:python)?\s*\n?(.*?)```', request.content, re.DOTALL)
            code_to_check = code_match.group(1) if code_match else request.content
            mc_result = await mc_diagnose(db, code=code_to_check, stderr="")
            if mc_result.get("has_misconception"):
                misconception_result = mc_result
                logger.info("chat_misconception_detected",
                    code=mc_result.get("misconception_id"),
                    session_id=session_id)
                # v3.1（F2/F9 修复）：误区事件记录**延后**到策略选择之后。
                # 原实现在这里就 record_misconception_event，导致随后
                # get_misconception_history_count 把"本次"也算进历史，
                # 使 has_history 永远为 True、attempt_count 多计 1，
                # 令 B-FR-13 的"首次→progressive_hint"分支不可达。
                # 正确顺序：先查历史 → 选策略 → 生成回复 → 再记事件。
                # 保存诊断出的代码片段，供延后记录使用。
                misconception_result["_code_snippet"] = (
                    code_to_check[:500] if code_to_check else ""
                )
        except Exception as e:
            logger.debug("chat_misconception_skipped", error=str(e)[:100])

    # 本轮回复的结构化元数据（误区、策略、证据、提示等级）。
    # 生成前先建好，异常分支也要能拿到已诊断出的信息。
    turn_meta: dict = {}

    # 步骤 5：调用 AI 导师（2.0 增强：误区+策略+画像+修正检测）
    try:
        # 2.0: 画像驱动——注入学生历史信息
        profile_context = ""
        try:
            from app.services.profile_service import get_or_create_profile
            import json as _json2
            profile = await get_or_create_profile(db, user.id)
            recent_mc = []
            if profile.recent_misconceptions:
                try: recent_mc = _json2.loads(profile.recent_misconceptions)
                except: pass
            if recent_mc:
                profile_context = f"📊 学生画像：最近出现的误区有 {', '.join(recent_mc[-3:])}。"
                from app.services.profile_service import normalize_hint_dependency
                hint_dep = normalize_hint_dependency(profile.hint_dependency)
                if hint_dep == "high":
                    profile_context += "该学生提示依赖度较高，请降低提示等级鼓励独立思考。"
                elif hint_dep == "low":
                    profile_context += "该学生提示依赖度低，可以适当给更多概念解释。"
        except Exception:
            pass

        # 2.0: 修正后总结——检测学生是否从错误修正为正确
        fix_context = ""
        if len(history) >= 2:
            last_user = [m for m in history[-4:] if m.get("role") == "user"]
            has_code_before = any("```" in m.get("content", "") for m in last_user[:-1])
            has_code_now = "```" in request.content
            if has_code_before and has_code_now:
                fix_context = "🎯 学生刚才修改了代码。如果改对了，请先肯定学生的进步，然后用1句话总结'刚才的问题本质是什么'，帮学生形成长期记忆。"

        pedagogy_hint = ""
        if misconception_result:
            from app.services.pedagogy_service import select_strategy, get_hint_prompt
            from app.services.misconception_service import get_misconception_history_count
            mc_id = misconception_result["misconception_id"]
            # 从数据库获取该学生该误区的真实历史命中次数
            prior_count = await get_misconception_history_count(db, user.id, mc_id)
            strategy = select_strategy(
                misconception_id=mc_id,
                attempt_count=prior_count + 1,       # 真实累计次数
                has_history=(prior_count > 0),        # 真实历史
            )
            # 真实策略与提示等级要一路传到响应、消息记录和前端，
            # 不能在返回前写死成 progressive_hint。
            turn_meta.update({
                "misconception_id": mc_id,
                "misconception_name": misconception_result.get("misconception_name"),
                "confidence": misconception_result.get("confidence"),
                "evidence": misconception_result.get("evidence"),
                "strategy": strategy.get("strategy"),
                "hint_level": strategy.get("hint_level"),
                "strategy_reason": strategy.get("reason"),
                "prior_misconception_count": prior_count,
            })
            # F2/F9：在"查历史之后"才记录本次事件，保证 has_history/attempt_count
            # 反映的是"本次之前"的历史，不把本次算进去。
            try:
                from app.services.misconception_service import record_misconception_event
                await record_misconception_event(
                    db, user.id, mc_id or "",
                    misconception_result.get("confidence", 0.8),
                    misconception_result.get("evidence", ""),
                    code_snippet=misconception_result.get("_code_snippet", ""),
                    submission_id="",
                )
            except Exception as exc:
                # 不能静默吞掉：事件写入失败会让历史次数永远停在旧值，
                # 进而让教学策略退化为"每次都当第一次"。
                logger.warning(
                    "misconception_event_record_failed",
                    misconception_id=mc_id,
                    error=str(exc)[:200],
                )

            if settings.ENABLE_PEDAGOGY_STEERING:
                # SRS 3.2 接线（E-FR-01）：转移图决定教学意图，
                # 锚定 prompt 决定表达约束（不泄露答案 + 置信度调语气）。
                try:
                    from app.services.pedagogy.steering import (
                        StudentState, select_strategy as steering_select,
                    )
                    from app.services.prompts.misconception_anchored import (
                        build_system_prompt,
                    )
                    state = StudentState(
                        active_misconceptions=[mc_id] if mc_id else [],
                        attempt_count=prior_count + 1,
                    )
                    decision = steering_select(state)
                    anchored = build_system_prompt(
                        mc_id or "?",
                        float(misconception_result.get("confidence", 0.5)),
                    )
                    mc_ctx = (
                        f"[教学意图: {decision.intent.value}"
                        f"（{decision.matched_rule}）]\n{anchored}"
                    )
                    # 开启转移图后，它才是真正生效的策略
                    turn_meta.update({
                        "strategy": decision.intent.value,
                        "hint_level": decision.hint_level,
                        "strategy_source": "steering_graph",
                        "strategy_rule": decision.matched_rule,
                    })
                    logger.info(
                        "pedagogy_steering_decision",
                        intent=decision.intent.value,
                        hint_level=decision.hint_level,
                        rule=decision.matched_rule,
                        session_id=session_id,
                    )
                except Exception as e:
                    # 转移图/锚定 prompt 失败 → 回退旧策略文案，不断链
                    logger.warning("pedagogy_steering_failed", error=str(e)[:200])
                    pedagogy_hint = get_hint_prompt(
                        misconception_result["misconception_name"],
                        strategy["hint_level"],
                    )
                    mc_ctx = f"⚠️ 学生代码已诊断出误区：{misconception_result['misconception_name']}。{pedagogy_hint}"
            else:
                pedagogy_hint = get_hint_prompt(
                    misconception_result["misconception_name"],
                    strategy["hint_level"],
                )
                mc_ctx = f"⚠️ 学生代码已诊断出误区：{misconception_result['misconception_name']}。{pedagogy_hint}"
            rag_context = (rag_context or "") + "\n" + mc_ctx if rag_context else mc_ctx

        # 合并所有上下文
        full_context = "\n".join(filter(None, [rag_context or "", profile_context, fix_context]))
        if full_context:
            rag_context = full_context

        ai_response: AIResponse = await generate_tutor_response(
            user_message=request.content,
            conversation_history=history,
            student_level="beginner",
            rag_context=rag_context,
            model=model,
            misconception_id=(misconception_result or {}).get("misconception_id"),
        )
        # 2.0: 注入误区信息到响应（策略取实际决策结果，不写死）
        if misconception_result:
            ai_response.misconception_id = misconception_result.get("misconception_id")
        if turn_meta.get("strategy"):
            ai_response.pedagogical_strategy = turn_meta["strategy"]
        if turn_meta.get("hint_level"):
            ai_response.hint_level = int(turn_meta["hint_level"])
        # 质量分只有真正审核过才记录；审核失败时 verify_score 为 None，
        # 不写入元数据，页面也就不会把它显示成一个正常分数。
        if ai_response.verify_score and ai_response.verify_score > 0:
            turn_meta["quality_score"] = int(ai_response.verify_score)
            turn_meta["quality_reviewed"] = True
    except Exception as e:
        logger.error("ai_generation_failed", session_id=session_id, error=str(e))
        # 即使 AI 失败，用户消息也要保存。用户消息在第 2 步已经提交，
        # 这里只负责清掉失败事务并让实例可用于响应。
        try:
            user_msg = await _recover_user_message(db, user_msg, session_id, request.content)
        except Exception as recover_error:
            logger.error("user_message_recover_failed", session_id=session_id,
                         error=str(recover_error)[:120])
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="AI 服务暂时不可用，且消息未能保存，请稍后重试",
            )
        # F6: LLM 不可用但有 AST 误区诊断时，用模板兜底，degrade 而非 fail
        if misconception_result:
            fallback_msg = (
                f"我注意到一个常见的思路点：**{misconception_result['misconception_name']}**。\n\n"
                f"{misconception_result.get('evidence', '')}\n\n"
                f"（AI 导师暂时繁忙，先给你这条基于代码结构的提示，稍后可以再问我细节。）"
            )
            turn_meta["degraded"] = True
            assistant_msg = ChatMessage(
                session_id=session_id, role="assistant",
                content=fallback_msg, response_type="code_feedback",
                hint_level=int(turn_meta.get("hint_level") or 1),
                metadata_json=json.dumps(turn_meta, ensure_ascii=False),
            )
            db.add(assistant_msg)
            await db.commit()
            await db.refresh(assistant_msg)
            return {
                "user_message": MessageResponse.model_validate(user_msg),
                "assistant_message": MessageResponse.model_validate(assistant_msg),
                "ai_response": AIResponse(
                    response_type="code_feedback", message=fallback_msg,
                    hint_level=int(turn_meta.get("hint_level") or 1),
                    related_concepts=[], next_action="ask_question",
                    misconception_id=misconception_result.get("misconception_id"),
                    pedagogical_strategy=turn_meta.get("strategy"),
                ),
                "degraded": True,
            }
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
        # 诊断证据 + 实际策略：刷新页面后仍能还原"当时为什么这样提示"
        metadata_json=json.dumps(turn_meta, ensure_ascii=False) if turn_meta else None,
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
