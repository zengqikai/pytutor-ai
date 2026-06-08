"""
RAG 检索节点
============

在 Agent 工作流中执行知识检索。
结果写入 state.rag_context，供 tutor_response_node 使用。
"""

from app.agents.state import AgentState
from app.observability.logger import get_logger
from app.schemas.rag import RAGRetrievalRequest
from app.services.rag_service import format_context_for_llm, retrieve_context
from app.database.session import AsyncSessionFactory

logger = get_logger(__name__)


async def rag_retrieval_node(state: AgentState) -> dict:
    """
    检索相关知识并写入 state。

    如果意图是 concept_question 或 code_debug，执行 RAG 检索。
    对于 general 意图，跳过检索。
    """
    intent = state.get("intent", "")
    user_input = state.get("user_input", "")

    # 一般对话不需要检索
    if intent == "general":
        return {"current_step": "rag_retrieval", "rag_context": None}

    try:
        async with AsyncSessionFactory() as db:
            result = await retrieve_context(
                db,
                RAGRetrievalRequest(query=user_input, top_k=3),
            )

            if result.results:
                context = format_context_for_llm(result.results)
                logger.info(
                    "rag_node_completed",
                    intent=intent,
                    chunk_count=len(result.results),
                )
                return {
                    "rag_context": context,
                    "current_step": "rag_retrieval",
                }

    except Exception as e:
        logger.warning("rag_node_failed", error=str(e))

    return {
        "rag_context": None,
        "current_step": "rag_retrieval",
    }
