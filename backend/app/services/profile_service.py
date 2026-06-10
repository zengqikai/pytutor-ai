"""
学习画像服务
============

管理学生学习画像的生命周期：
- 创建画像（注册时自动创建）
- 更新画像（每次学习行为后）
- 薄弱知识点检测
- 学习路径推荐
"""

import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import LearningEvent, StudentProfile, StudentWeakness
from app.observability.logger import get_logger

logger = get_logger(__name__)

# 知识点依赖关系（前置知识 → 后续知识）
CONCEPT_PREREQUISITES = {
    "variables": [],
    "data_types": ["variables"],
    "string": ["data_types"],
    "list": ["data_types"],
    "dict": ["data_types"],
    "tuple": ["list"],
    "set": ["list"],
    "for_loop": ["list", "string"],
    "while_loop": ["for_loop"],
    "if_statement": ["data_types"],
    "function": ["for_loop", "if_statement"],
    "class": ["function"],
    "exception": ["if_statement", "function"],
    "file_io": ["function", "string"],
    "list_comprehension": ["for_loop", "list"],
}

# 推荐学习路径（按顺序）
LEARNING_PATH = [
    "variables", "data_types", "string", "list", "tuple",
    "if_statement", "for_loop", "while_loop", "dict", "set",
    "function", "exception", "list_comprehension", "file_io", "class",
]


async def get_or_create_profile(db: AsyncSession, user_id: str) -> StudentProfile:
    """获取或创建学习画像。"""
    result = await db.execute(
        select(StudentProfile).where(StudentProfile.user_id == user_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = StudentProfile(user_id=user_id)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        logger.info("profile_created", user_id=user_id)

    return profile


async def record_event(
    db: AsyncSession,
    user_id: str,
    event_type: str,
    concept: str | None = None,
    detail: dict | None = None,
):
    """记录学习事件并更新画像。"""
    # 保存事件
    event = LearningEvent(
        user_id=user_id,
        event_type=event_type,
        concept=concept,
        detail_json=json.dumps(detail, ensure_ascii=False) if detail else None,
    )
    db.add(event)

    # 更新画像统计
    profile = await get_or_create_profile(db, user_id)
    if event_type == "exercise_passed":
        profile.total_exercises_completed += 1
        profile.total_exercises_passed += 1
    elif event_type == "exercise_failed":
        profile.total_exercises_completed += 1
    elif event_type == "code_submitted":
        profile.total_code_submissions += 1
    elif "hint" in event_type:
        profile.total_hints_used += 1

    await db.commit()


async def update_weakness(
    db: AsyncSession,
    user_id: str,
    concept: str,
    error_type: str | None = None,
    is_success: bool = False,
):
    """
    更新薄弱知识点。

    规则：
    - 失败 → fail_count += 1, severity = min(5, fail_count)
    - 连续 3 次失败 → 标记为薄弱点
    - 成功 → 重置 fail_count, 标记 resolved
    """
    result = await db.execute(
        select(StudentWeakness)
        .where(
            StudentWeakness.user_id == user_id,
            StudentWeakness.concept == concept,
            StudentWeakness.is_resolved == False,
        )
    )
    weakness = result.scalar_one_or_none()

    if is_success:
        if weakness:
            weakness.is_resolved = True
            logger.info("weakness_resolved", user_id=user_id, concept=concept)
    else:
        if weakness:
            weakness.fail_count += 1
            weakness.last_error_type = error_type
            # 严重度 = 频率 + 持续性
            # 失败 1 次=1, 2 次=2, 3 次=3, 4 次=4, 5+ 次=5
            # 连续 3+ 次失败额外 +1（表示陷入困境）
            base = min(4, weakness.fail_count)
            stuck = 1 if weakness.fail_count >= 3 else 0
            weakness.severity = min(5, base + stuck)
        else:
            weakness = StudentWeakness(
                user_id=user_id,
                concept=concept,
                fail_count=1,
                severity=1,
                last_error_type=error_type,
            )
            db.add(weakness)
        logger.info("weakness_updated", user_id=user_id, concept=concept, fail_count=weakness.fail_count)

    await db.commit()


async def get_weaknesses(db: AsyncSession, user_id: str) -> list[dict]:
    """获取当前未解决的薄弱知识点。"""
    result = await db.execute(
        select(StudentWeakness)
        .where(
            StudentWeakness.user_id == user_id,
            StudentWeakness.is_resolved == False,
        )
        .order_by(StudentWeakness.severity.desc())
    )
    weaknesses = result.scalars().all()

    return [
        {
            "concept": w.concept,
            "fail_count": w.fail_count,
            "severity": w.severity,
            "last_error": w.last_error_type,
            "created_at": w.created_at.isoformat(),
        }
        for w in weaknesses
    ]


async def get_recommendation(db: AsyncSession, user_id: str) -> dict:
    """
    推荐下一步学习内容。

    推荐逻辑：
    1. 如果有薄弱点 → 推荐最严重的一个（需要复习）
    2. 如果无薄弱点 → 推荐学习路径上的下一个知识点
    3. 优先推荐有前置知识已完成的
    """
    profile = await get_or_create_profile(db, user_id)

    # 解析已掌握的知识点
    mastery = {}
    if profile.concept_mastery_json:
        try:
            mastery = json.loads(profile.concept_mastery_json)
        except json.JSONDecodeError:
            pass

    # 先检查薄弱点
    weaknesses = await get_weaknesses(db, user_id)
    if weaknesses:
        weakest = weaknesses[0]
        return {
            "action": "review",
            "concept": weakest["concept"],
            "reason": f"你在 '{weakest['concept']}' 上失败了 {weakest['fail_count']} 次，建议重点复习。",
            "severity": weakest["severity"],
        }

    # 推荐下一个知识点
    for concept in LEARNING_PATH:
        if concept not in mastery or mastery[concept] < 0.6:
            prerequisites = CONCEPT_PREREQUISITES.get(concept, [])
            prereqs_met = all(
                p in mastery and mastery[p] >= 0.5 for p in prerequisites
            )
            if prereqs_met:
                return {
                    "action": "learn",
                    "concept": concept,
                    "reason": f"你已经准备好学习 '{concept}'！",
                }

    # 所有基础知识点已完成 → 推荐进阶
    return {
        "action": "advance",
        "concept": "project",
        "reason": "基础扎实！可以尝试综合项目练习。",
    }


async def get_profile_summary(db: AsyncSession, user_id: str) -> dict:
    """获取画像摘要，供前端 Dashboard 展示。"""
    profile = await get_or_create_profile(db, user_id)
    weaknesses = await get_weaknesses(db, user_id)
    recommendation = await get_recommendation(db, user_id)

    # 计算练习通过率 + 经验值
    total = profile.total_exercises_completed
    passed = profile.total_exercises_passed
    pass_rate = round(passed / total * 100, 1) if total > 0 else 0
    import json
    mastery = {}
    if profile.concept_mastery_json:
        try: mastery = json.loads(profile.concept_mastery_json)
        except: pass
    total_exp = mastery.get("_total_exp", 0)
    next_level_exp = (profile.level) * 300  # 升级所需总经验

    return {
        "level": profile.level,
        "total_exp": total_exp,
        "next_level_exp": next_level_exp,
        "stats": {
            "exercises_completed": total,
            "exercises_passed": passed,
            "pass_rate": pass_rate,
            "code_submissions": profile.total_code_submissions,
            "hints_used": profile.total_hints_used,
            "chat_messages": profile.total_chat_messages,
        },
        "weaknesses": weaknesses,
        "recommendation": recommendation,
    }
