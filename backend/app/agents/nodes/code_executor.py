"""
代码审查与执行节点
==================

当 intent 为 code_debug 时执行：
1. 在沙箱中执行代码
2. 分析执行结果（错误类型、位置）
3. 将结果写入 state 供 tutor_response_node 使用
"""

from app.agents.state import AgentState
from app.observability.logger import get_logger
from app.sandbox.executor import execute_python_code

logger = get_logger(__name__)


async def code_executor_node(state: AgentState) -> dict:
    """
    在沙箱中执行学生代码并分析结果。

    执行后结果存储在 state.code_result 中，
    后续 tutor_response_node 会基于结果生成反馈。
    """
    code = state.get("code_to_execute")

    if not code:
        logger.warning("code_executor_no_code")
        return {
            "current_step": "code_executor",
        }

    # 在沙箱中安全执行
    logger.info("code_executor_starting", code_len=len(code))
    result = await execute_python_code(code)

    logger.info(
        "code_executor_completed",
        status=result["status"],
        runtime_ms=result.get("runtime_ms", 0),
    )

    return {
        "code_result": result,
        "current_step": "code_executor",
    }
