"""教学回复节点——纯文本 Markdown，不强制 JSON。"""

import re

from app.agents.state import AgentState
from app.observability.logger import get_logger
from app.schemas.ai import ChatMessage as LLMMessage
from app.schemas.chat import AIResponse
from app.services.llm_service import chat_completion
from app.services.tutor_service import SYSTEM_PROMPT, calculate_hint_level

logger = get_logger(__name__)


async def tutor_response_node(state: AgentState) -> dict:
    user_input = state.get("user_input", "")
    intent = state.get("intent", "concept_question")
    rag_context = state.get("rag_context")
    code_result = state.get("code_result")

    history = []
    for msg in state.get("messages", []):
        if isinstance(msg, dict):
            history.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})

    hint_level = calculate_hint_level(history, user_input)
    messages: list[LLMMessage] = [LLMMessage(role="system", content=SYSTEM_PROMPT)]

    if rag_context:
        messages.append(LLMMessage(role="system", content=f"参考知识点：\n{rag_context}"))
    if code_result:
        messages.append(LLMMessage(role="system",
            content=f"学生代码执行结果：stdout={code_result.get('stdout','')}, stderr={code_result.get('stderr','')}, status={code_result.get('status','')}"))

    intent_hints = {
        "concept_question": "学生想了解概念。请给出清晰解释+示例。",
        "code_debug": "学生提交了代码。请分析执行结果，指出问题，给出改进建议。",
        "exercise_request": "请生成一道适合的 Python 练习题。",
    }
    hint_text = intent_hints.get(intent, "请以友好的方式帮助学生。")
    messages.append(LLMMessage(role="system",
        content=f"提示等级 Level {hint_level}。{hint_text}\n第一行写 <!-- hint:{hint_level} concepts:xxx --> 然后写正文。"))

    for msg in history[-20:]:
        messages.append(LLMMessage(role=msg["role"], content=msg["content"]))
    messages.append(LLMMessage(role="user", content=user_input))

    try:
        llm_response = await chat_completion(messages=messages, temperature=0.7)
        raw = llm_response.content.strip()

        hint = hint_level
        concepts: list[str] = []
        meta_match = re.match(r'<!--\s*hint:(\d+)\s*(?:concepts:(.+?))?\s*-->', raw)
        if meta_match:
            hint = int(meta_match.group(1))
            if meta_match.group(2):
                concepts = [c.strip() for c in meta_match.group(2).split(",") if c.strip()]
            raw = raw[meta_match.end():].strip()

        type_map = {
            "concept_question": "concept_explanation",
            "code_debug": "code_feedback",
            "exercise_request": "exercise",
        }
        response_type = type_map.get(intent, "general")
        if "```" in user_input:
            response_type = "code_feedback"

        logger.info("tutor_node_ok", hint=hint, type=response_type, len=len(raw))

        return {
            "tutor_response": AIResponse(
                response_type=response_type,
                message=raw,
                hint_level=hint,
                related_concepts=concepts,
                next_action="ask_question",
            ).model_dump(),
            "current_step": "tutor_response",
        }

    except Exception as e:
        logger.warning("tutor_node_fallback", error=str(e))
        return {
            "tutor_response": AIResponse(
                response_type="general",
                message=f"抱歉，回复生成失败。请稍后重试。",
                hint_level=1,
                related_concepts=[],
                next_action="ask_question",
            ).model_dump(),
            "current_step": "tutor_response",
        }
