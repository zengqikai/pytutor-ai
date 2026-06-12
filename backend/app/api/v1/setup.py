"""一次性设置 API — 仅首次部署时使用"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db

router = APIRouter()

@router.post("/init-roles")
async def init_roles(db: AsyncSession = Depends(get_db)):
    """升级预设账号角色（幂等）。"""
    from app.models.user import User
    from sqlalchemy import select as sa_select

    upgrades = {
        "teacher@test.com": "INSTRUCTOR",
        "admin@test.com": "ADMIN",
    }
    result = []
    for email, role in upgrades.items():
        r = await db.execute(sa_select(User).where(User.email == email))
        user = r.scalar_one_or_none()
        if user:
            old_role = user.role.value
            user.role = role
            result.append(f"{email}: {old_role} -> {role}")
        else:
            result.append(f"{email}: NOT FOUND")

    await db.commit()
    return {"result": result}
