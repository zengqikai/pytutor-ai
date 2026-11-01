"""
学习画像 API
============

接口：
    GET /api/v1/profile/me               - 画像摘要
    GET /api/v1/profile/me/weaknesses    - 薄弱点列表
    GET /api/v1/profile/me/recommendations - 学习推荐
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.user import User
from app.security.dependencies import get_current_user
from app.services.exercise_stats import load_attempt_events, passed_exercise_ids
from app.services.profile_service import (
    get_or_create_profile,
    get_profile_summary,
    get_recommendation,
    get_weaknesses,
    record_event,
    update_weakness,
)

router = APIRouter()


class OnboardingRequest(BaseModel):
    """新手引导完成请求。skill_level: A 零基础 / B 学过一点 / C 会基础 / D 自由提问"""
    skill_level: str = Field(default="B", pattern="^[ABCD]$")
    diagnosis: dict = Field(default_factory=dict)


class LessonCompleteRequest(BaseModel):
    """课程完成请求。"""
    lesson_id: str = Field(default="lesson_0", max_length=64, pattern=r"^[A-Za-z0-9_\-]+$")


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
    """查看自己通过了哪些题目。

    按 **exercise_id** 去重、只认计分通过（score_pct > 0）：
    以前按 concept 去重，同一知识点下做对第二题不会显示，看答案得 0 分的
    却会显示成"已通过"。
    """
    from app.services.exercise_stats import detail_score, is_counted_pass

    events = await load_attempt_events(db, user_id=current_user.id)

    # 每道题保留最新一次计分通过
    by_exercise: dict[str, dict] = {}
    for e in events:
        ex_id = e["exercise_id"]
        if not ex_id or not is_counted_pass(e["event_type"], e["detail"]):
            continue
        by_exercise[ex_id] = e

    passed = [
        {
            "exercise_id": ex_id,
            "concept": e["concept"] or e["detail"].get("title") or "练习",
            "score_pct": detail_score(e["detail"]),
            "used_hints": e["detail"].get("used_hints", 0),
            "time": e["created_at"].isoformat(),
        }
        for ex_id, e in sorted(
            by_exercise.items(), key=lambda kv: kv[1]["created_at"], reverse=True
        )
    ]
    return {"passed": passed, "total": len(passed)}


@router.get("/me/passed-ids")
async def get_passed_exercise_ids(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回用户已通过的题目 ID 集合（用于前端显示对勾）。

    只算计分通过，且不再限制最近 50 条事件（超过 50 次提交的学生，
    最早通过的题会对勾消失）。
    """
    ids = await passed_exercise_ids(db, current_user.id)
    return {"ids": sorted(ids), "count": len(ids)}


@router.post("/me/onboarding")
async def complete_onboarding(
    body: OnboardingRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    记录用户首次登录的基础选择。

    请求体：{"skill_level": "A/B/C/D"}
    A=零基础 B=学过一点 C=会基础想练习 D=自由提问
    """
    import json

    level = body.skill_level
    labels = {"A": "zero_basis", "B": "some_basics", "C": "can_practice", "D": "free_chat"}
    label = labels.get(level, "some_basics")

    diagnosis = body.diagnosis

    await record_event(db, current_user.id, "onboarding_completed",
        concept=label,
        detail={"skill_level": level, "diagnosis": diagnosis}
    )

    profile = await get_or_create_profile(db, current_user.id)
    if profile.concept_mastery_json:
        try:
            mastery = json.loads(profile.concept_mastery_json)
        except (ValueError, TypeError):
            mastery = {}
    else:
        mastery = {}
    mastery["_onboarding"] = label
    profile.concept_mastery_json = json.dumps(mastery, ensure_ascii=False)

    # 入门诊断的逐题结果要真正落到画像里，否则"测了等于没测"：
    # 薄弱点进 StudentWeakness + weak_topics，误区进 recent_misconceptions。
    weak = [c for c in (diagnosis.get("weak") or []) if isinstance(c, str)]
    for concept in weak:
        await update_weakness(db, current_user.id, concept)

    mcs = [m for m in (diagnosis.get("misconceptions") or []) if isinstance(m, str)]
    if mcs:
        profile.recent_misconceptions = json.dumps(mcs[:10], ensure_ascii=False)

    await db.commit()

    return {
        "skill_level": label,
        "next": "lesson_0" if level == "A" else "main",
        "weak_count": len(weak),
    }


@router.post("/me/lesson/complete")
async def complete_lesson(
    body: LessonCompleteRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """记录课程完成。"""
    lesson_id = body.lesson_id
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
