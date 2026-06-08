"""
认证 API
========

提供用户注册和登录接口。

接口列表：
    POST /api/v1/auth/register  - 用户注册
    POST /api/v1/auth/login     - 用户登录
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.schemas.auth import LoginRequest, RegisterRequest, RegisterResponse, TokenResponse
from app.services.auth_service import login_user, register_user

router = APIRouter()


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    request: RegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    用户注册接口。

    请求体示例:
        {
            "email": "student@example.com",
            "password": "mypass123",
            "display_name": "小明"
        }

    响应:
        {
            "user": { "id": "uuid...", "email": "...", "display_name": "小明", "role": "student" },
            "token": { "access_token": "eyJ...", "token_type": "bearer", "expires_in": 86400 }
        }
    """
    return await register_user(db, request)


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    用户登录接口。

    请求体示例:
        {
            "email": "student@example.com",
            "password": "mypass123"
        }

    响应:
        {
            "access_token": "eyJ...",
            "token_type": "bearer",
            "expires_in": 86400
        }

    注意：无论邮箱不存在还是密码错误，统一返回"邮箱或密码错误"（防止账号枚举攻击）。
    """
    return await login_user(db, request.email, request.password)
