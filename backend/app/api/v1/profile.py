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


@router.get("/me/recommendations")
async def get_my_recommendations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取下一步学习推荐。"""
    return await get_recommendation(db, current_user.id)
