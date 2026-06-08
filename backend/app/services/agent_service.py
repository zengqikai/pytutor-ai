"""
Agent 服务模块
==============

封装 LangGraph Agent 的调用，对外提供简单的接口。

调用流程：
    agent_service.run(user_input, messages)
    → 构建 AgentState
    → agent_graph.ainvoke(state)
    → 提取最终结果（tutor_response, code_result 等）
    → 返回给调用方

与旧版 chat_service 的关系：
    - 旧版 chat_service 直接调用 tutor_service → LLM
    - 新版 agent_service 通过 Agent 工作流 → 多节点处理
    - chat_service 可以选择使用 agent_service 或直接调用（渐进迁移）
"""

from typing import Any, Optional

from app.agents.graph import agent_graph
from app.agents.state import AgentState
from app.observability.logger import get_logger

logger = get_logger(__name__)


async def run_agent(
    user_input: str,
    conversation_history: Optional[list[dict]] = None,
) -> dict[str, Any]:
    """
    运行 Agent 工作流，处理用户输入。

    参数:
        user_input: 用户的当前消息
        conversation_history: 之前的对话历史

    返回:
        dict: {
            "tutor_response": {...},    # AI 结构化回复
            "code_result": {...}|None,  # 代码执行结果（如有）
            "rag_context": str|None,    # 检索到的知识上下文
            "intent": str,              # 识别到的意图
            "intent_confidence": float, # 意图置信度
            "safety_result": str,       # 安全检查结果
            "is_valid_output": bool,    # 输出校验是否通过
            "error": str|None,          # 错误信息
            "execution_path": [str],    # 实际走过的节点路径
        }
    """
    # 步骤 1：构建初始状态
    initial_state: AgentState = {
        "messages": conversation_history or [],
        "user_input": user_input,
        "intent": "",
        "intent_confidence": 0.0,
        "rag_context": None,
        "safety_result": "",
        "safety_reason": "",
        "code_to_execute": None,
        "code_result": None,
        "tutor_response": None,
        "is_valid_output": False,
        "error": None,
        "current_step": "start",
    }

    # 步骤 2：执行工作流
    logger.info("agent_run_start", user_input_preview=user_input[:80])

    try:
        # ainvoke = async invoke：异步执行整个工作流图
        final_state = await agent_graph.ainvoke(initial_state)
    except Exception as e:
        logger.error("agent_graph_error", error=str(e), exc_info=True)
        return {
            "tutor_response": {
                "response_type": "general",
                "message": "抱歉，系统处理您的请求时出错了。请稍后重试。",
                "hint_level": 1,
                "related_concepts": [],
                "next_action": "ask_question",
                "code_blocks": [],
            },
            "code_result": None,
            "intent": "general",
            "error": str(e),
            "is_valid_output": False,
        }

    # 步骤 3：提取结果
    result = {
        "tutor_response": final_state.get("tutor_response"),
        "code_result": final_state.get("code_result"),
        "rag_context": final_state.get("rag_context"),
        "intent": final_state.get("intent", "general"),
        "intent_confidence": final_state.get("intent_confidence", 0.0),
        "safety_result": final_state.get("safety_result", "pass"),
        "is_valid_output": final_state.get("is_valid_output", False),
        "error": final_state.get("error"),
    }

    logger.info(
        "agent_run_completed",
        intent=result["intent"],
        has_response=result["tutor_response"] is not None,
        is_valid=result["is_valid_output"],
    )

    return result
