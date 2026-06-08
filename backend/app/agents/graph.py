"""
Agent 工作流图
==============

LangGraph 工作流定义：节点 + 边 + 条件路由。

工作流结构：
```
                         ┌──→ [拒绝回复] ──→ END
                         │ (block)
[用户输入] → [安全检查] ──┤
                         │ (pass/warn)
                         └──→ [意图识别] ──→ {
                              concept_question → [RAG检索] → [教学回复]
                              code_debug       → [RAG检索] → [代码执行] → [教学回复]
                              exercise_request → [RAG检索] → [教学回复]
                              general          → [教学回复]
                              unsafe           → [拒绝回复]
                         }
                              ↓
                         [输出校验] → END
```

LangGraph 核心概念：
    StateGraph: 状态图——定义了节点和它们之间的流转
    Node: 处理函数——接收 State，返回 State 的部分更新
    Edge: 普通边——无条件从 A 到 B
    ConditionalEdge: 条件边——根据 State 的值决定去哪个节点
"""

from langgraph.graph import END, StateGraph

from app.agents.nodes.code_executor import code_executor_node
from app.agents.nodes.intent_router import intent_router_node
from app.agents.nodes.output_validator import output_validator_node
from app.agents.nodes.rag_retrieval import rag_retrieval_node
from app.agents.nodes.safety_check import safety_check_node
from app.agents.nodes.tutor_node import tutor_response_node
from app.agents.state import AgentState
from app.observability.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# 条件路由函数
# =============================================================================

def route_after_safety(state: AgentState) -> str:
    """安全检查后决定去向。"""
    if state.get("safety_result") == "block":
        return "reject_response"
    return "intent_router"


def route_after_intent(state: AgentState) -> str:
    """意图识别后决定去向。"""
    intent = state.get("intent", "general")

    routes = {
        "concept_question": "rag_retrieval",
        "code_debug": "rag_retrieval",
        "exercise_request": "rag_retrieval",
        "general": "tutor_response",
        "unsafe": "reject_response",
    }

    return routes.get(intent, "tutor_response")


def route_after_rag(state: AgentState) -> str:
    """RAG 检索后决定去向。"""
    intent = state.get("intent", "")
    if intent == "code_debug" and state.get("code_to_execute"):
        return "code_executor"
    return "tutor_response"


# =============================================================================
# 构建工作流图
# =============================================================================

def build_agent_graph() -> StateGraph:
    """
    构建并编译 Agent 工作流图。

    返回:
        编译后的 StateGraph（可被 invoke 调用）
    """
    # 创建状态图
    workflow = StateGraph(AgentState)

    # ==============================
    # 注册节点
    # ==============================
    workflow.add_node("safety_check", safety_check_node)
    workflow.add_node("intent_router", intent_router_node)
    workflow.add_node("rag_retrieval", rag_retrieval_node)
    workflow.add_node("code_executor", code_executor_node)
    workflow.add_node("tutor_response", tutor_response_node)
    workflow.add_node("output_validator", output_validator_node)
    workflow.add_node("reject_response", _reject_node)

    # ==============================
    # 设置入口
    # ==============================
    workflow.set_entry_point("safety_check")

    # ==============================
    # 添加条件边（根据 State 动态路由）
    # ==============================
    workflow.add_conditional_edges(
        "safety_check",
        route_after_safety,
        {
            "reject_response": "reject_response",
            "intent_router": "intent_router",
        },
    )

    workflow.add_conditional_edges(
        "intent_router",
        route_after_intent,
        {
            "rag_retrieval": "rag_retrieval",
            "tutor_response": "tutor_response",
            "reject_response": "reject_response",
        },
    )

    workflow.add_conditional_edges(
        "rag_retrieval",
        route_after_rag,
        {
            "code_executor": "code_executor",
            "tutor_response": "tutor_response",
        },
    )

    # ==============================
    # 添加普通边（无条件流转）
    # ==============================
    workflow.add_edge("code_executor", "tutor_response")
    workflow.add_edge("tutor_response", "output_validator")
    workflow.add_edge("output_validator", END)
    workflow.add_edge("reject_response", END)

    # ==============================
    # 编译
    # ==============================
    compiled_graph = workflow.compile()
    logger.info("agent_graph_compiled")
    return compiled_graph


# =============================================================================
# 拒绝回复节点（无需 async，直接返回固定内容）
# =============================================================================

async def _reject_node(state: AgentState) -> dict:
    """生成拒绝回复。"""
    existing = state.get("tutor_response")
    if existing:
        return {"current_step": "reject_response"}

    return {
        "tutor_response": {
            "response_type": "general",
            "message": "抱歉，我只能回答 Python 编程学习相关的问题。请提出您的 Python 问题！",
            "hint_level": 0,
            "related_concepts": [],
            "next_action": "ask_question",
            "code_blocks": [],
        },
        "is_valid_output": True,
        "current_step": "reject_response",
    }


# =============================================================================
# 全局单例（应用启动时编译一次）
# =============================================================================
agent_graph = build_agent_graph()
