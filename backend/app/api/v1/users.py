"""
用户 API
========

提供用户信息查询接口。

接口列表：
    GET /api/v1/users/me - 获取当前登录用户信息
"""

from fastapi import APIRouter, Depends

from app.models.user import User
from app.schemas.auth import UserInfoResponse
from app.security.dependencies import get_current_user

router = APIRouter()


@router.get("/me", response_model=UserInfoResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
):
    """
    获取当前登录用户信息。

    需要在请求头中携带 JWT：
        Authorization: Bearer eyJ...

    响应示例:
        {
            "id": "uuid...",
            "email": "student@example.com",
            "display_name": "小明",
            "role": "student",
            "is_active": true,
            "created_at": "2026-06-08T00:00:00+00:00"
        }
    """
    return current_user
