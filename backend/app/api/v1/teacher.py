"""
教师视图 API
============

提供教学效果分析仪表盘的聚合数据，包括：
- 学生总览（人数、平均等级、通过率）
- 误区频次排行（M1-M8）
- 薄弱知识点 TOP 10
- 提示依赖度分布（低/中/高）
- 学生列表（含画像摘要）
- 最近学习动态

GET /teacher/overview — 教师仪表盘聚合数据
"""

import json

from fastapi import APIRouter, Depends
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.misconception import Misconception, MisconceptionEvent
from app.models.profile import LearningEvent, StudentProfile, StudentWeakness
from app.models.user import User
from app.security.dependencies import get_current_user

router = APIRouter()


@router.get("/overview")
async def teacher_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回教师仪表盘所需的全部聚合数据。"""

    # ── 学生总体统计 ──
    total_students = (await db.execute(
        sa_func.count(StudentProfile.user_id)
    )).scalar() or 0

    avg_level = (await db.execute(
        sa_func.avg(StudentProfile.level)
    )).scalar() or 0

    total_completed = (await db.execute(
        sa_func.sum(StudentProfile.total_exercises_completed)
    )).scalar() or 0
    total_passed = (await db.execute(
        sa_func.sum(StudentProfile.total_exercises_passed)
    )).scalar() or 0
    pass_rate = round(total_passed / total_completed * 100, 1) if total_completed > 0 else 0

    # ── 提示依赖分布 ──
    hint_low = (await db.execute(
        select(sa_func.count()).select_from(StudentProfile)
        .where(StudentProfile.hint_dependency == "low")
    )).scalar() or 0
    hint_med = (await db.execute(
        select(sa_func.count()).select_from(StudentProfile)
        .where(StudentProfile.hint_dependency == "medium")
    )).scalar() or 0
    hint_high = (await db.execute(
        select(sa_func.count()).select_from(StudentProfile)
        .where(StudentProfile.hint_dependency == "high")
    )).scalar() or 0

    # ── 误区频次排行（M1-M8） ──
    mc_rows = (await db.execute(
        select(Misconception.code, Misconception.name, sa_func.count(MisconceptionEvent.id))
        .join(Misconception, MisconceptionEvent.misconception_id == Misconception.id, isouter=True)
        .group_by(Misconception.code)
        .order_by(sa_func.count(MisconceptionEvent.id).desc())
    )).all()
    misconception_stats = [
        {"code": code, "name": name, "count": count}
        for code, name, count in mc_rows
    ]

    # ── 薄弱知识点 TOP 10 ──
    weak_rows = (await db.execute(
        select(StudentWeakness.concept, sa_func.count())
        .where(StudentWeakness.is_resolved == False)
        .group_by(StudentWeakness.concept)
        .order_by(sa_func.count().desc())
        .limit(10)
    )).all()
    weak_topic_stats = [{"concept": c, "count": ct} for c, ct in weak_rows]

    # ── 最近学习动态 ──
    recent_events = (await db.execute(
        select(LearningEvent, User.display_name)
        .join(User, LearningEvent.user_id == User.id)
        .order_by(LearningEvent.created_at.desc())
        .limit(20)
    )).all()
    event_list = [{
        "user": name,
        "event": e.event_type,
        "concept": e.concept or "",
        "time": e.created_at.isoformat(),
    } for e, name in recent_events]

    # ── 学生列表 ──
    student_rows = (await db.execute(
        select(User.display_name, User.email, StudentProfile)
        .join(StudentProfile, User.id == StudentProfile.user_id)
        .limit(30)
    )).all()
    students = []
    for name, email, sp in student_rows:
        mc = []
        if sp.recent_misconceptions:
            try:
                mc = json.loads(sp.recent_misconceptions)
            except (json.JSONDecodeError, TypeError):
                pass
        students.append({
            "name": name,
            "email": email,
            "level": sp.level,
            "exercises_passed": sp.total_exercises_passed,
            "exercises_completed": sp.total_exercises_completed,
            "hint_dependency": sp.hint_dependency or "low",
            "recent_misconceptions": mc[-3:] if mc else [],
        })

    return {
        "summary": {
            "total_students": total_students,
            "avg_level": round(avg_level, 1),
            "total_completed": total_completed,
            "total_passed": total_passed,
            "pass_rate": pass_rate,
            "hint_dependency": {"low": hint_low, "medium": hint_med, "high": hint_high},
        },
        "misconception_stats": misconception_stats,
        "weak_topic_stats": weak_topic_stats,
        "students": students,
        "recent_events": event_list,
    }
