"""
Agent API
=========

使用 LangGraph Agent 工作流处理用户消息。
相比 /chat 的简单 LLM 调用，/agent 走完整的多节点工作流。

接口：
    POST /api/v1/agent/chat - Agent 驱动的聊天（含安全检查、意图路由、RAG、代码执行）
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.user import User
from app.schemas.chat import SendMessageRequest
from app.security.dependencies import get_current_user
from app.services.agent_service import run_agent

router = APIRouter()


@router.post("/chat")
async def agent_chat(
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    通过 Agent 工作流处理用户消息。

    与 /api/v1/chat 的区别：
    - 走 LangGraph 多节点工作流（安全检查 → 意图路由 → RAG → 代码执行 → 生成 → 校验）
    - 返回额外的诊断信息（intent、intent_confidence、safety_result、execution_path）

    用法与普通聊天接口完全一致。
    """
    result = await run_agent(
        user_input=request.content,
        conversation_history=None,  # 后续可传入历史
    )

    return {
        "content": request.content,
        "ai_response": result.get("tutor_response"),
        "intent": result.get("intent"),
        "intent_confidence": result.get("intent_confidence"),
        "safety_result": result.get("safety_result"),
        "code_result": result.get("code_result"),
        "is_valid_output": result.get("is_valid_output"),
        "error": result.get("error"),
    }
