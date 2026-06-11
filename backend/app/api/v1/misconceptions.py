"""
误区诊断 API
============

POST /api/v1/misconceptions/diagnose  — 诊断代码误区
GET  /api/v1/misconceptions           — 所有误区定义
GET  /api/v1/profile/me/misconceptions — 用户误区历史
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.user import User
from app.security.dependencies import get_current_user
from app.services.misconception_service import (
    diagnose,
    get_user_misconceptions,
    record_misconception_event,
)

router = APIRouter()


@router.post("/diagnose")
async def diagnose_code(
    body: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    诊断学生代码中的 Python 初学者误区。

    请求体：
        {"code": "...", "stderr": "...", "exercise_id": "..."}

    返回：
        {has_misconception, misconception_id, confidence, evidence, ...}
    """
    code = body.get("code", "")
    stderr = body.get("stderr", "")
    exercise_id = body.get("exercise_id", "")

    result = await diagnose(db, code=code, stderr=stderr)

    # 如果诊断出误区，记录事件
    if result["has_misconception"] and current_user:
        # 查找 misconception 的数据库 ID
        mc_code = result["misconception_id"]
        from sqlalchemy import select as sa_select
        from app.models.misconception import Misconception
        mc_result = await db.execute(
            sa_select(Misconception).where(Misconception.code == mc_code)
        )
        mc = mc_result.scalar_one_or_none()
        if mc:
            await record_misconception_event(
                db,
                user_id=current_user.id,
                misconception_id=mc.id,
                confidence=result["confidence"],
                evidence=result["evidence"],
                code_snippet=code[:500],
                exercise_id=exercise_id,
            )

    return result


@router.get("")
async def list_misconceptions(db: AsyncSession = Depends(get_db)):
    """列出所有误区定义。"""
    from sqlalchemy import select as sa_select
    from app.models.misconception import Misconception
    r = await db.execute(sa_select(Misconception).order_by(Misconception.code))
    return [
        {
            "id": m.id,
            "code": m.code,
            "name": m.name,
            "description": m.description,
            "related_concepts": m.related_concepts,
            "recommended_strategy": m.recommended_strategy,
        }
        for m in r.scalars()
    ]


@router.get("/profile/me/misconceptions")
async def get_my_misconceptions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的误区历史。"""
    return await get_user_misconceptions(db, current_user.id)
