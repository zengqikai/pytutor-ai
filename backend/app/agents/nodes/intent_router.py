"""
意图识别节点
============

将用户输入分类为不同意图，决定后续走哪条处理路径。

意图分类：
    concept_question  → RAG 检索 → 教学回复
    code_debug        → RAG 检索 → 代码执行 → 教学回复
    exercise_request  → RAG 检索 → 练习生成
    general           → 教学回复（无 RAG）
    unsafe            → 拒绝回复（由 safety_check 处理）
"""

import json
import re

from app.agents.state import AgentState
from app.observability.logger import get_logger
from app.schemas.ai import ChatMessage as LLMMessage
from app.services.llm_service import chat_completion

logger = get_logger(__name__)

INTENT_PROMPT = """分析以下学生消息的意图。只返回 JSON，不要其他内容。

学生消息："{message}"

可能的意图类型：
- concept_question: 学生在问 Python 概念或知识点（"什么是列表？"、"for 循环怎么用？"）
- code_debug: 学生提交了代码，需要调试或审查（消息中包含 ```python 代码块或明显的代码片段）
- exercise_request: 学生请求练习题（"给我一些练习"、"有没有题目？"）
- general: 一般性对话或问候

返回格式：
{{"intent": "concept_question", "confidence": 0.95}}
"""


async def intent_router_node(state: AgentState) -> dict:
    """
    识别用户意图，设置路由。

    使用 LLM 进行意图分类（比关键词匹配更准确）。
    如果 LLM 调用失败，回退到关键词匹配。
    """
    user_input = state.get("user_input", "")

    # 快速关键词预判（不调用 LLM 的情况）
    # 包含代码块 → code_debug（确定性高，无需 LLM）
    if "```python" in user_input or "```" in user_input:
        return {
            "intent": "code_debug",
            "intent_confidence": 0.99,
            "current_step": "intent_router",
            "code_to_execute": _extract_code(user_input),
        }

    # 练习请求关键词
    exercise_keywords = ["练习", "题目", "做题", "测试一下", "出题", "给我一道", "有什么题"]
    if any(kw in user_input for kw in exercise_keywords):
        return {
            "intent": "exercise_request",
            "intent_confidence": 0.9,
            "current_step": "intent_router",
        }

    # 使用 LLM 做精细分类
    try:
        prompt = INTENT_PROMPT.format(message=user_input)
        llm_response = await chat_completion(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.0,
            max_tokens=100,
        )

        content = llm_response.content.strip()
        # 提取 JSON（处理可能的代码块包裹）
        json_match = re.search(r'\{[^}]+\}', content)
        if json_match:
            data = json.loads(json_match.group())
            intent = data.get("intent", "general")
            confidence = data.get("confidence", 0.5)

            logger.info("intent_recognized", intent=intent, confidence=confidence)
            return {
                "intent": intent,
                "intent_confidence": confidence,
                "current_step": "intent_router",
                "code_to_execute": _extract_code(user_input) if intent == "code_debug" else None,
            }

    except Exception as e:
        logger.warning("intent_llm_failed", error=str(e))

    # 回退：默认为概念问题
    return {
        "intent": "concept_question",
        "intent_confidence": 0.5,
        "current_step": "intent_router",
    }


def _extract_code(text: str) -> str | None:
    """从用户消息中提取 ```python 代码块。"""
    match = re.search(r'```(?:python)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # 如果没有代码块标记，检查是否整段都是代码
    # 简单启发式：包含 print、def、for、if 等关键字且没有问号
    code_indicators = ["print(", "def ", "for ", "if ", "while ", "import ", "class "]
    if any(ind in text for ind in code_indicators) and "?" not in text and "？" not in text:
        return text.strip()

    return None
