"""
输出校验节点
============

验证 AI 生成的回复是否符合结构化输出要求。
如果不符合 → 返回错误信息，前端可据此降级显示。
"""

from app.agents.state import AgentState
from app.observability.logger import get_logger

logger = get_logger(__name__)

# 必需字段
REQUIRED_FIELDS = ["response_type", "message", "hint_level", "related_concepts", "next_action"]

# 合法的 response_type 值
VALID_RESPONSE_TYPES = ["concept_explanation", "code_feedback", "hint", "exercise", "general"]


async def output_validator_node(state: AgentState) -> dict:
    """
    校验 AI 回复的结构和内容。

    检查项：
    1. tutor_response 是否存在
    2. 必需字段是否齐全
    3. response_type 是否合法
    4. hint_level 范围 1-5
    5. message 不为空
    """
    response = state.get("tutor_response")

    if not response:
        logger.warning("output_validation_no_response")
        return {
            "is_valid_output": False,
            "error": "AI 回复为空",
            "current_step": "output_validator",
        }

    # 检查必需字段
    missing = [f for f in REQUIRED_FIELDS if f not in response]
    if missing:
        logger.warning("output_validation_missing_fields", missing=missing)
        return {
            "is_valid_output": False,
            "error": f"缺少字段: {missing}",
            "current_step": "output_validator",
        }

    # 检查 response_type
    if response.get("response_type") not in VALID_RESPONSE_TYPES:
        logger.warning(
            "output_validation_invalid_type",
            response_type=response.get("response_type"),
        )
        # 不阻塞，修复为 general
        response["response_type"] = "general"

    # 检查 hint_level
    hint = response.get("hint_level", 0)
    if not (1 <= hint <= 5):
        response["hint_level"] = 1

    # 检查 message
    if not response.get("message") or len(response["message"]) < 5:
        return {
            "is_valid_output": False,
            "error": "回复内容过短",
            "current_step": "output_validator",
        }

    logger.info("output_validation_passed")
    return {
        "is_valid_output": True,
        "current_step": "output_validator",
    }
