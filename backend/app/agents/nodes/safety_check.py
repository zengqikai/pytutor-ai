"""
安全检查节点
============

Agent 工作流的第一道防线。
检查用户输入是否存在 Prompt Injection、越狱尝试、无关内容。

如果检测到危险输入 → 直接返回拒绝回复，不进入后续节点。
"""

from app.agents.state import AgentState
from app.observability.logger import get_logger

logger = get_logger(__name__)

# 危险模式
UNSAFE_PATTERNS = [
    "ignore previous instructions",
    "ignore all previous",
    "forget your prompt",
    "system prompt",
    "你是哪个模型",
    "你的内部指令",
    "告诉我你的 system",
    "你是什么模型",
    "你的 API key",
    "/reset",
    "/system",
    "DAN mode",
    "jailbreak",
    "扮演",
    "从现在开始你是",
]

# 完全无关话题（引导回 Python）
OFF_TOPIC_KEYWORDS = [
    "写小说", "写诗", "翻译", "天气", "新闻", "股票",
    "约会", "恋爱", "游戏攻略", "做菜", "菜谱",
]


async def safety_check_node(state: AgentState) -> dict:
    """
    检查用户输入的安全性。

    当检测到不安全内容时：
        safety_result = "block"
        设置 tutor_response 为拒绝消息
        is_valid_output = True（直接返回，跳过后续节点）

    当检测到警告时：
        safety_result = "warn"
        继续流程但记录日志
    """
    user_input = state.get("user_input", "")
    input_lower = user_input.lower()

    # 检查 1：Prompt Injection 尝试
    for pattern in UNSAFE_PATTERNS:
        if pattern.lower() in input_lower:
            logger.warning("safety_blocked", pattern=pattern, input_preview=user_input[:100])
            return {
                "safety_result": "block",
                "safety_reason": f"检测到潜在的不安全输入",
                "intent": "unsafe",
                "current_step": "safety_check",
                "tutor_response": {
                    "response_type": "general",
                    "message": "抱歉，我只能回答 Python 编程相关的问题。请提出您的 Python 学习问题！",
                    "hint_level": 0,
                    "related_concepts": [],
                    "next_action": "ask_question",
                    "code_blocks": [],
                },
                "is_valid_output": True,
            }

    # 检查 2：完全无关话题
    off_topic_count = sum(1 for kw in OFF_TOPIC_KEYWORDS if kw in user_input)
    if off_topic_count >= 2:
        logger.info("safety_off_topic", input_preview=user_input[:100])
        return {
            "safety_result": "warn",
            "safety_reason": "话题可能偏离 Python 学习",
            "current_step": "safety_check",
        }

    # 通过安全检查
    return {
        "safety_result": "pass",
        "safety_reason": "",
        "current_step": "safety_check",
    }
