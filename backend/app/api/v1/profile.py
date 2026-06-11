"""
学习画像 API
============

接口：
    GET /api/v1/profile/me               - 画像摘要
    GET /api/v1/profile/me/weaknesses    - 薄弱点列表
    GET /api/v1/profile/me/recommendations - 学习推荐
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.user import User
from app.security.dependencies import get_current_user
from app.services.profile_service import (
    get_profile_summary,
    get_recommendation,
    get_weaknesses,
)

router = APIRouter()


@router.get("/me")
async def get_my_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取个人学习画像摘要。"""
    return await get_profile_summary(db, current_user.id)


@router.get("/me/weaknesses")
async def get_my_weaknesses(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取薄弱知识点列表。"""
    return await get_weaknesses(db, current_user.id)


@router.get("/me/passed")
async def get_passed_exercises(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查看自己通过了哪些题目（去重）。"""
    from sqlalchemy import select
    from app.models.profile import LearningEvent
    r = await db.execute(
        select(LearningEvent)
        .where(LearningEvent.user_id == current_user.id, LearningEvent.event_type == "exercise_passed")
        .order_by(LearningEvent.created_at.desc())
        .limit(50)
    )
    seen = set()
    passed = []
    import json
    for e in r.scalars():
        concept = e.concept or "练习"
        if concept in seen:
            continue
        seen.add(concept)
        detail = {}
        if e.detail_json:
            try: detail = json.loads(e.detail_json)
            except: pass
        passed.append({
            "concept": concept,
            "score_pct": detail.get("score_pct", 0),
            "used_hints": detail.get("used_hints", 0),
            "time": e.created_at.isoformat(),
        })
    return {"passed": passed, "total": len(passed)}


@router.get("/me/passed-ids")
async def get_passed_exercise_ids(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回用户已通过的题目 ID 集合（用于前端显示对勾）。"""
    from sqlalchemy import select
    from app.models.profile import LearningEvent
    import json
    r = await db.execute(
        select(LearningEvent.detail_json)
        .where(LearningEvent.user_id == current_user.id, LearningEvent.event_type == "exercise_passed")
        .order_by(LearningEvent.created_at.desc())
        .limit(50)
    )
    ids = set()
    for (detail_json,) in r:
        if detail_json:
            try:
                d = json.loads(detail_json)
                if d.get("exercise_id"):
                    ids.add(d["exercise_id"])
            except Exception:
                pass
    return {"ids": list(ids), "count": len(ids)}


@router.post("/me/onboarding")
async def complete_onboarding(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    记录用户首次登录的基础选择。

    请求体：{"skill_level": "A/B/C/D"}
    A=零基础 B=学过一点 C=会基础想练习 D=自由提问
    """
    from app.services.profile_service import record_event, get_or_create_profile
    import json

    level = body.get("skill_level", "B")
    labels = {"A": "zero_basis", "B": "some_basics", "C": "can_practice", "D": "free_chat"}
    label = labels.get(level, "some_basics")

    await record_event(db, current_user.id, "onboarding_completed",
        concept=label,
        detail={"skill_level": level}
    )

    profile = await get_or_create_profile(db, current_user.id)
    if profile.concept_mastery_json:
        mastery = json.loads(profile.concept_mastery_json)
    else:
        mastery = {}
    mastery["_onboarding"] = label
    profile.concept_mastery_json = json.dumps(mastery, ensure_ascii=False)
    await db.commit()

    return {"skill_level": label, "next": "lesson_0" if level == "A" else "main"}


@router.post("/me/lesson/complete")
async def complete_lesson(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """记录课程完成。"""
    from app.services.profile_service import record_event
    lesson_id = body.get("lesson_id", "lesson_0")
    await record_event(db, current_user.id, "lesson_completed", concept=lesson_id)
    return {"lesson_id": lesson_id, "status": "completed"}


@router.get("/me/misconceptions")
async def get_my_misconceptions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的误区历史。"""
    from app.services.misconception_service import get_user_misconceptions
    return await get_user_misconceptions(db, current_user.id)


@router.get("/me/recommendations")
async def get_my_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取下一步学习推荐。"""
    return await get_recommendation(db, current_user.id)
