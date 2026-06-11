"""
AI 导师服务（简化为纯文本回复）
================================

不再强制 LLM 输出 JSON——改为自然的 Markdown 文本。
DeepSeek 对纯文本回复非常稳定，JSON 输出不稳定。

格式约定：
    AI 回复的首行可选标记：<!-- hint:1 concepts:for_loop,list -->
    前端从首行注释提取元数据，其余为 Markdown 内容。
    如果没有注释行，默认为 general + Level 1。
"""

import re

from app.core.config import settings
from app.observability.logger import get_logger
from app.schemas.ai import ChatMessage as LLMMessage
from app.schemas.chat import AIResponse
from app.services.llm_service import chat_completion

logger = get_logger(__name__)

# 简化版 System Prompt——不要求 JSON，自然对话即可
SYSTEM_PROMPT = """你是 PyTutor，Python 编程导师。用中文回复，简洁明了。

规则：引导思考优先，不直接给答案。代码用 ```python 包裹。首行标注 <!-- hint:N concepts:x,y -->（N=1~5）。"""


def calculate_hint_level(history: list[dict], question: str) -> int:
    """根据对话历史计算提示等级 1-5。"""
    question_lower = question.lower()
    if any(kw in question for kw in ["直接给答案", "给我完整代码", "帮我写"]):
        return 3
    if any(kw in question_lower for kw in ["什么是", "为什么", "怎么理解", "解释"]):
        return 1
    if "```" in question:
        return 2
    recent_hints = [m.get("hint_level", 0) for m in history[-6:] if m.get("role") == "assistant"]
    if len(recent_hints) >= 3 and sum(recent_hints[-3:]) / 3 >= 3:
        return min(4, int(sum(recent_hints[-3:]) / 3))
    return 1


async def generate_tutor_response(
    user_message: str,
    conversation_history: list[dict],
    student_level: str = "beginner",
    rag_context: str | None = None,
    model: str | None = None,
) -> AIResponse:
    """生成 AI 导师回复（纯文本 Markdown）。"""
    hint_level = calculate_hint_level(conversation_history, user_message)

    messages: list[LLMMessage] = [LLMMessage(role="system", content=SYSTEM_PROMPT)]

    if rag_context:
        messages.append(LLMMessage(role="system", content=f"参考知识点：\n{rag_context}"))

    messages.append(LLMMessage(role="system",
        content=f"学生水平: {student_level}。本次回复提示等级应为 Level {hint_level}。"
                f"第一行写 <!-- hint:{hint_level} concepts:xxx --> 然后写正文。"))

    for msg in conversation_history[-20:]:
        messages.append(LLMMessage(role=msg.get("role", "user"), content=msg.get("content", "")))

    messages.append(LLMMessage(role="user", content=user_message))

    try:
        llm_response = await chat_completion(messages=messages, temperature=0.7, model=model)
        raw = llm_response.content.strip()

        # 解析首行元数据标记
        hint = hint_level
        concepts: list[str] = []
        response_type = "general"

        meta_match = re.match(r'<!--\s*hint:(\d+)\s*(?:concepts:(.+?))?\s*-->', raw)
        if meta_match:
            hint = int(meta_match.group(1))
            if meta_match.group(2):
                concepts = [c.strip() for c in meta_match.group(2).split(",") if c.strip()]
            raw = raw[meta_match.end():].strip()

        # 推断 response_type
        if "```python" in user_message or "```" in user_message:
            response_type = "code_feedback"
        elif any(kw in user_message for kw in ["什么是", "解释", "为什么"]):
            response_type = "concept_explanation"
        elif any(kw in user_message for kw in ["练习", "题目"]):
            response_type = "exercise"

        # 2.0: 回复质量自检
        verify_score = 0
        try:
            from app.services.pedagogy_service import verify_response
            verification = await verify_response(raw, hint, None)
            verify_score = verification.get("score", 3)
            if verification.get("needs_revision") and verify_score < 3:
                # 不合格 → 重新生成（更严格的提示）
                logger.info("tutor_response_revision", score=verify_score)
                messages.append(LLMMessage(role="system",
                    content="上一轮回复不合格。请确保：1) 不给完整答案 2) 符合提示等级 3) 用初学者能理解的语言。重新回复。"))
                llm_response2 = await chat_completion(messages=messages, temperature=0.5, model=model)
                raw = llm_response2.content.strip()
                # 再次解析元数据
                meta_match2 = re.match(r'<!--\s*hint:(\d+)\s*(?:concepts:(.+?))?\s*-->', raw)
                if meta_match2:
                    hint = int(meta_match2.group(1))
                    if meta_match2.group(2):
                        concepts = [c.strip() for c in meta_match2.group(2).split(",") if c.strip()]
                    raw = raw[meta_match2.end():].strip()
                verify_score = 2  # 标记为已修正
        except Exception:
            pass

        logger.info("tutor_response_ok", hint=hint, type=response_type, length=len(raw), verify_score=verify_score)

        return AIResponse(
            response_type=response_type,
            message=raw,
            hint_level=hint,
            related_concepts=concepts,
            next_action="ask_question",
        )

    except Exception as e:
        logger.error("tutor_failed", error=str(e))
        return AIResponse(
            response_type="general",
            message=f"抱歉，回复生成失败。请稍后重试。\n\n错误信息：{str(e)[:200]}",
            hint_level=1,
            related_concepts=[],
            next_action="ask_question",
        )


async def generate_tutor_response_stream(
    user_message: str,
    conversation_history: list[dict],
    student_level: str = "beginner",
    rag_context: str | None = None,
    model: str | None = None,
):
    """流式生成 AI 导师回复——逐 token yield"""
    import litellm
    from app.core.config import settings as s

    hint_level = calculate_hint_level(conversation_history, user_message)
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if rag_context:
        messages.append({"role": "system", "content": f"参考知识点：\n{rag_context}"})
    messages.append({"role": "system", "content": f"提示等级 Level {hint_level}。第一行写 <!-- hint:{hint_level} concepts:xxx -->"})

    for msg in conversation_history[-20:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": user_message})

    provider_cfg = {"model": f"deepseek/{s.deepseek_model}", "api_key": s.deepseek_api_key, "api_base": s.deepseek_base_url}
    litellm_model = model or provider_cfg["model"]

    try:
        response = await litellm.acompletion(
            model=litellm_model, messages=messages,
            temperature=s.llm_temperature, max_tokens=s.llm_max_tokens,
            api_key=provider_cfg["api_key"], api_base=provider_cfg["api_base"],
            stream=True, timeout=s.llm_timeout,
        )
        async for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    except Exception as e:
        logger.error("stream_failed", error=str(e))
        yield f"\n[流式中断: {str(e)[:100]}]"


def _parse_ai_json(raw_content: str, default_hint_level: int) -> AIResponse:
    """保留兼容旧版 JSON 解析。"""
    import json
    content = raw_content.strip()
    code_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
    if code_match:
        content = code_match.group(1).strip()
    if not content.startswith("{"):
        first, last = content.find("{"), content.rfind("}")
        if first != -1 and last > first:
            content = content[first:last + 1]
    data = json.loads(content)
    return AIResponse(
        response_type=data.get("response_type", "general"),
        message=data.get("message", "无内容"),
        hint_level=data.get("hint_level", default_hint_level),
        related_concepts=data.get("related_concepts", []),
        next_action=data.get("next_action", "ask_question"),
        code_blocks=data.get("code_blocks", []),
    )
