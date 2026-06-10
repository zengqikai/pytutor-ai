"""
管理员 API
==========

接口：
    GET  /api/v1/admin/stats    - 系统统计
    GET  /api/v1/admin/users    - 用户列表
    PATCH /api/v1/admin/users/{id} - 修改用户角色/状态
    GET  /api/v1/admin/logs     - 最近操作日志
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.user import User, UserRole
from app.models.chat import ChatSession, ChatMessage
from app.models.exercise import Exercise
from app.models.rag import RAGDocument
from app.models.submission import CodeSubmission
from app.models.profile import LearningEvent
from app.security.dependencies import get_current_user, require_role

router = APIRouter()


@router.get("/students/{student_id}")
async def student_detail(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.INSTRUCTOR)),
):
    """查看单个学生的学习记录。"""
    from app.models.profile import StudentProfile
    from app.models.submission import CodeSubmission, ExecutionResult

    r = await db.execute(select(User).where(User.id == student_id))
    user = r.scalar_one_or_none()
    if not user: return {"detail": "学生不存在"}

    r = await db.execute(select(StudentProfile).where(StudentProfile.user_id == student_id))
    profile = r.scalar_one_or_none()

    # 从学习事件查练习记录
    from app.models.profile import LearningEvent
    import json

    # 预加载所有题目，建立 concept → title 映射
    all_exercises = (await db.execute(select(Exercise))).scalars().all()
    concept_map: dict[str, str] = {}
    for ex in all_exercises:
        if ex.concepts:
            for c in ex.concepts.split(","):
                concept_map[c.strip()] = ex.title

    r = await db.execute(
        select(LearningEvent)
        .where(LearningEvent.user_id == student_id, LearningEvent.event_type.in_(["exercise_passed", "exercise_failed"]))
        .order_by(LearningEvent.created_at.desc())
        .limit(50)
    )
    events = []
    for e in r.scalars():
        detail = {}
        if e.detail_json:
            try: detail = json.loads(e.detail_json)
            except: pass
        # 优先用 detail 里的 title，其次从题库 concept 映射，最后用原始 concept
        title = detail.get("title") or concept_map.get(e.concept or "") or e.concept or "练习"
        events.append({
            "type": e.event_type,
            "title": title,
            "score_pct": detail.get("score_pct", 0),
            "used_hints": detail.get("used_hints", 0),
            "time": e.created_at.isoformat(),
        })

    passed_count = sum(1 for e in events if e["type"] == "exercise_passed")

    return {
        "student": {
            "id": user.id, "name": user.display_name, "email": user.email,
            "level": profile.level if profile else 1,
            "exercises_passed": passed_count,
            "hints_used": profile.total_hints_used if profile else 0,
        },
        "events": events,
    }


@router.get("/exercises/{exercise_id}/records")
async def exercise_records(
    exercise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.INSTRUCTOR)),
):
    """查看某道题的提交记录：哪些学生通过了。"""
    from app.models.submission import CodeSubmission, ExecutionResult

    r = await db.execute(
        select(CodeSubmission, ExecutionResult)
        .join(ExecutionResult, CodeSubmission.id == ExecutionResult.submission_id, isouter=True)
        .where(CodeSubmission.exercise_id == exercise_id)
        .order_by(CodeSubmission.created_at.desc())
        .limit(50)
    )
    records = []
    for sub, res in r:
        ur = await db.execute(select(User).where(User.id == sub.user_id))
        user = ur.scalar_one_or_none()
        passed = res and res.status == "completed" and res.exit_code == 0
        records.append({
            "student_name": user.display_name if user else "?",
            "student_email": user.email if user else "",
            "passed": passed,
            "status": res.status if res else "unknown",
            "runtime_ms": res.runtime_ms if res else 0,
            "time": sub.created_at.isoformat(),
        })
    return {"records": records}


@router.get("/stats")
async def admin_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """系统统计概览。"""
    tables = {
        "users": User,
        "chat_sessions": ChatSession,
        "chat_messages": ChatMessage,
        "exercises": Exercise,
        "rag_documents": RAGDocument,
        "code_submissions": CodeSubmission,
    }
    stats = {}
    for name, model in tables.items():
        r = await db.execute(select(func.count()).select_from(model))
        stats[name] = r.scalar() or 0

    r = await db.execute(
        select(func.count()).select_from(User).where(User.role == "student")
    )
    stats["students"] = r.scalar() or 0

    return stats


@router.get("/users")
async def list_users(
    search: str = Query(default=""),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """用户列表（可搜索）。"""
    query = select(User)
    if search:
        query = query.where(
            User.email.contains(search) | User.display_name.contains(search)
        )
    query = query.order_by(User.created_at.desc()).offset(offset).limit(limit)
    r = await db.execute(query)
    users = r.scalars().all()
    return [
        {
            "id": u.id,
            "email": u.email,
            "display_name": u.display_name,
            "role": u.role.value if isinstance(u.role, UserRole) else u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
        }
        for u in users
    ]


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """修改用户角色或状态。"""
    r = await db.execute(select(User).where(User.id == user_id))
    user = r.scalar_one_or_none()
    if not user:
        return {"detail": "用户不存在"}

    if "role" in body:
        try:
            user.role = UserRole(body["role"])
        except ValueError:
            return {"detail": f"无效角色: {body['role']}"}
    if "is_active" in body:
        user.is_active = bool(body["is_active"])

    await db.commit()
    return {"id": user.id, "role": user.role.value, "is_active": user.is_active}


@router.get("/students")
async def student_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.INSTRUCTOR)),
):
    """教师专属：班级学生概览。"""
    from app.models.profile import StudentProfile

    r = await db.execute(
        select(User, StudentProfile)
        .join(StudentProfile, User.id == StudentProfile.user_id, isouter=True)
        .where(User.role == "student")
        .order_by(User.created_at.desc())
        .limit(100)
    )
    students = []
    # 预加载所有学生的通过数
    from app.models.profile import LearningEvent
    event_counts = {}
    all_events = (await db.execute(
        select(LearningEvent.user_id, func.count())
        .where(LearningEvent.event_type == "exercise_passed")
        .group_by(LearningEvent.user_id)
    )).all()
    for uid, cnt in all_events:
        event_counts[uid] = cnt

    for user, profile in r:
        students.append({
            "id": user.id,
            "name": user.display_name,
            "email": user.email,
            "level": profile.level if profile else 1,
            "exercises_passed": event_counts.get(user.id, 0),
            "hints_used": profile.total_hints_used if profile else 0,
            "last_active": user.updated_at.isoformat() if user.updated_at else "",
            "is_active": user.is_active,
        })
    return {"students": students, "total": len(students)}


@router.get("/logs")
async def view_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """查看最近的学习事件日志。"""
    r = await db.execute(
        select(LearningEvent)
        .order_by(LearningEvent.created_at.desc())
        .limit(limit)
    )
    events = r.scalars().all()
    return [
        {
            "id": e.id,
            "user_id": e.user_id,
            "event_type": e.event_type,
            "concept": e.concept,
            "detail": e.detail_json,
            "created_at": e.created_at.isoformat(),
        }
        for e in events
    ]


@router.get("/exercises")
async def admin_exercises(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.INSTRUCTOR)),
):
    """题库管理列表。"""
    r = await db.execute(
        select(Exercise).order_by(Exercise.created_at.desc()).limit(limit)
    )
    exercises = r.scalars().all()
    return [
        {
            "id": e.id,
            "title": e.title,
            "difficulty": e.difficulty,
            "concepts": e.concepts,
            "source": e.source,
            "is_published": e.is_published,
            "use_count": e.use_count,
            "pass_rate": e.pass_rate,
            "created_at": e.created_at.isoformat(),
        }
        for e in exercises
    ]


@router.patch("/exercises/{exercise_id}")
async def toggle_exercise(
    exercise_id: str,
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN, UserRole.INSTRUCTOR)),
):
    """发布/取消发布练习。"""
    r = await db.execute(select(Exercise).where(Exercise.id == exercise_id))
    ex = r.scalar_one_or_none()
    if not ex:
        return {"detail": "不存在"}
    if "is_published" in body:
        ex.is_published = bool(body["is_published"])
        await db.commit()
    return {"id": ex.id, "is_published": ex.is_published}
