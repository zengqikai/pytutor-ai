"""
教学策略与渐进式提示服务
========================

根据学生误区诊断结果和学习历史，选择最合适的教学策略并生成分层提示。

核心原则：
- 禁止首次就给完整答案
- 提示等级随尝试次数递增
- 重复误区 → 概念解释而非更多提示
"""

from app.observability.logger import get_logger

logger = get_logger(__name__)

# 教学策略定义
STRATEGIES = {
    "clarification": "信息不足，先追问明确问题",
    "progressive_hint": "分层提示，逐步引导",
    "concept_explanation": "概念解释，纠正误解",
    "debugging_guidance": "调试引导，教学生自查",
    "counterexample": "反例说明，对比正误",
    "summary_reflection": "总结反思，巩固理解",
    "practice_recommendation": "推荐专项练习",
}

# 5 级提示系统
HINT_LEVELS = {
    1: "概念提示：指出相关的 Python 概念，不提及代码位置",
    2: "方向提示：给出解决问题的方向，不指出具体行",
    3: "位置提示：指出可疑的代码行或区域",
    4: "部分代码：给出关键部分的代码片段",
    5: "完整参考：给出完整参考答案（仅学生明确请求时）",
}


def select_strategy(
    misconception_id: str | None,
    attempt_count: int,
    has_history: bool,
) -> dict:
    """
    根据误区和学生状态选择教学策略。

    返回:
        {"strategy": str, "hint_level": int, "reason": str}
    """
    # 无误区且首次 → 简单确认
    if not misconception_id and attempt_count <= 1:
        return {"strategy": "clarification", "hint_level": 1,
                "reason": "信息不足或无明显误区，先确认学生问题"}

    # 无误区但多次尝试 → 调试引导
    if not misconception_id:
        return {"strategy": "debugging_guidance", "hint_level": 2,
                "reason": "多次尝试未成功，引导学生自己排查"}

    # 首次出现该误区 → 渐进提示（低级别）
    if not has_history:
        level = min(attempt_count, 2)  # 首次最多 Level 2
        return {"strategy": "progressive_hint", "hint_level": level,
                "reason": f"首次出现 {misconception_id}，用渐进提示引导"}

    # 重复出现同一误区 → 概念解释
    if attempt_count >= 3:
        return {"strategy": "concept_explanation", "hint_level": 1,
                "reason": f"{misconception_id} 已出现 {attempt_count} 次，需要概念纠正"}

    # 多次失败 → 调试引导
    return {"strategy": "debugging_guidance", "hint_level": min(attempt_count, 4),
            "reason": "多次未通过，引导调试方法"}


def get_hint_prompt(misconception_name: str, level: int) -> str:
    """生成指定等级提示的 System Prompt 指令。"""
    base = f"学生可能存在误区：{misconception_name}。当前提示等级：Level {level}。"

    if level == 1:
        return base + "\n只给概念提示，不指出代码位置。引导思考而非给答案。"
    elif level == 2:
        return base + "\n给出解决方向，不指出具体行号。用问题引导。"
    elif level == 3:
        return base + "\n指出可疑的代码位置，但不给正确代码。让学生自己改。"
    elif level == 4:
        return base + "\n给出关键代码片段，但保留部分让学生完成。"
    else:
        return base + "\n学生已多次尝试，可以给出完整参考答案，附带解释。"


async def verify_response(
    ai_message: str,
    expected_hint_level: int,
    misconception_id: str | None,
) -> dict:
    """
    检查 AI 回复是否符合教学要求。

    用 LLM rubric 检查：是否过早给答案、是否符合 hint level、是否适合初学者。
    不合格则返回 needs_revision=True。
    """
    if expected_hint_level <= 2 and len(ai_message) > 500:
        # 简单启发式：低级别提示不应太长
        pass

    try:
        from app.services.llm_service import chat_completion
        from app.schemas.ai import ChatMessage

        prompt = f"""你是教学质量管理员。请检查以下 AI 回复是否符合要求。

要求：
- 提示等级应为 Level {expected_hint_level}（{"不应给完整答案" if expected_hint_level < 5 else "可以给答案"}）
- 应适合 Python 初学者
- 应针对误区：{misconception_id or "无特定误区"}
- 应包含下一步操作建议

AI 回复：
{ai_message[:800]}

以 JSON 回复（不要其他文字）：
{{"is_valid": true/false, "score": 1-5, "issues": ["问题1"], "needs_revision": true/false}}"""

        response = await chat_completion(
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=0.1,
            max_tokens=150,
        )

        import re, json
        content = response.content.strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            return {
                "is_valid": result.get("is_valid", True),
                "score": result.get("score", 3),
                "issues": result.get("issues", []),
                "needs_revision": result.get("needs_revision", False),
            }
    except Exception as e:
        logger.warning("verify_failed", error=str(e)[:200])

    return {"is_valid": True, "score": 3, "issues": [], "needs_revision": False}
