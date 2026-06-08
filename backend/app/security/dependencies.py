"""
鉴权依赖模块
============

提供 FastAPI 依赖注入函数，用于验证用户身份和权限。

FastAPI 的 Depends() 机制：
    路由函数中的 Depends(get_current_user) 会自动调用 get_current_user 函数，
    返回值直接注入到路由函数的参数中。

依赖链：
    get_current_user  → 解析 JWT → 查询数据库 → 返回 User 对象
    require_role(...) → 调用 get_current_user → 检查角色 → 通过/403

用法示例：
    # 需要登录
    @router.get("/users/me")
    async def get_me(current_user: User = Depends(get_current_user)):
        return current_user

    # 需要管理员权限
    @router.delete("/users/{user_id}")
    async def delete_user(
        user_id: str,
        current_user: User = Depends(require_role(UserRole.ADMIN)),
    ):
        ...
"""

from typing import Sequence

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.user import User, UserRole
from app.security.jwt import decode_access_token

# =============================================================================
# Bearer Token 认证方案
# =============================================================================
# HTTPBearer 会从请求头中提取 Authorization: Bearer <token>
# auto_error=True 表示如果没有提供 Bearer Token，自动返回 401 错误
# =============================================================================
security_scheme = HTTPBearer(auto_error=True)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    获取当前登录用户。

    这个函数做了三件事：
    1. 从 Authorization 头中提取 JWT
    2. 验证 JWT 签名并解码出 user_id
    3. 从数据库查询用户信息

    任何一步失败都返回 401（未认证）。

    参数:
        credentials: FastAPI 自动从请求头提取的 Bearer Token
        db: 数据库会话（自动注入）

    返回:
        User: 当前登录的用户对象

    异常:
        HTTPException 401: Token 无效、过期、用户不存在或已禁用
    """
    token = credentials.credentials

    # 步骤 1：验证 JWT
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证令牌无效或已过期，请重新登录",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 步骤 2：从 Payload 提取 user_id
    user_id: str | None = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="认证令牌格式无效",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 步骤 3：查询用户
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户不存在",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 步骤 4：检查账户是否被禁用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="账户已被禁用，请联系管理员",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


# =============================================================================
# 角色权限控制
# =============================================================================
# 这是一个"依赖工厂"——它返回一个依赖函数。
# require_role(UserRole.ADMIN) 返回一个只允许管理员访问的依赖。
# require_role(UserRole.INSTRUCTOR, UserRole.ADMIN) 返回允许教师和管理员访问的依赖。
# =============================================================================

def require_role(*allowed_roles: UserRole):
    """
    创建一个权限依赖——只允许特定角色访问。

    这是一个"闭包"模式：外层函数接收角色参数，返回一个实际的 FastAPI 依赖函数。

    参数:
        allowed_roles: 允许访问的角色列表

    返回:
        一个 FastAPI 依赖函数

    用法:
        # 仅管理员可访问
        @router.delete("/users/{user_id}")
        async def delete_user(
            user_id: str,
            current_user: User = Depends(require_role(UserRole.ADMIN)),
        ):
            ...

        # 教师和管理员都可访问
        @router.get("/admin/dashboard")
        async def dashboard(
            current_user: User = Depends(require_role(UserRole.INSTRUCTOR, UserRole.ADMIN)),
        ):
            ...
    """

    async def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        """
        检查当前用户是否具有所需角色。
        先调用 get_current_user 验证身份，再检查角色。
        """
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"权限不足，需要以下角色之一: {[r.value for r in allowed_roles]}",
            )
        return current_user

    return role_checker
