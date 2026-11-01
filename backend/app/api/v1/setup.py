"""一次性设置 API — 仅在受控部署阶段使用。

安全模型
--------
`/setup/init-roles` 会修改账户角色，绝不能匿名可调用。它由两把锁保护：

1. 必须配置 `SETUP_TOKEN` 环境变量；未配置时接口直接 404（默认关闭）。
2. 请求必须带 `X-Setup-Token` 头，且与配置值常量时间比较。

`/setup/list-users` 会返回全部用户信息，改为仅管理员可调用。

初始化完成后，从环境变量中移除 `SETUP_TOKEN` 即可永久关闭该接口。
"""

import hmac

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.models.user import User, UserRole
from app.security.dependencies import require_role

router = APIRouter()


def _verify_setup_token(x_setup_token: str | None) -> None:
    """校验一次性初始化令牌。未配置或为空时关闭接口。"""
    if not settings.SETUP_TOKEN:
        # 不暴露"接口存在但需要令牌"，直接当作不存在。
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not Found")
    if not x_setup_token or not hmac.compare_digest(x_setup_token, settings.SETUP_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="初始化令牌无效",
        )


@router.post("/init-roles")
async def init_roles(
    x_setup_token: str | None = Header(default=None, alias="X-Setup-Token"),
    db: AsyncSession = Depends(get_db),
):
    """升级预设账号角色（幂等）。需要 X-Setup-Token。"""
    _verify_setup_token(x_setup_token)

    upgrades = {
        "teacher@test.com": UserRole.INSTRUCTOR,
        "admin@test.com": UserRole.ADMIN,
    }
    result = []
    for email, role in upgrades.items():
        r = await db.execute(sa_select(User).where(User.email == email))
        user = r.scalar_one_or_none()
        if user:
            old_role = user.role.value
            user.role = role
            result.append(f"{email}: {old_role} -> {role.value}")
        else:
            result.append(f"{email}: NOT FOUND")

    await db.commit()
    return {"result": result}


@router.get("/list-users")
async def list_users(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """列出所有注册用户（仅管理员）。"""
    r = await db.execute(sa_select(User).order_by(User.created_at.desc()))
    return [{"email": u.email, "role": u.role.value, "name": u.display_name,
             "created": u.created_at.isoformat()} for u in r.scalars()]
