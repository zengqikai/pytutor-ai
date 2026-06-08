"""
认证相关 Schemas
================

定义认证相关 API 的请求和响应数据结构。
Pydantic 负责自动校验和序列化。

为什么需要这些 Schema？
- 区分"API 模型"和"数据库模型"——数据库结构变化时不影响 API
- 自动校验输入（邮箱格式、密码长度等）
- 控制哪些字段对外暴露（比如绝不会返回 password_hash）
"""

import re
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_serializer, field_validator


# =============================================================================
# 请求 Schema（客户端 → 服务器）
# =============================================================================

class RegisterRequest(BaseModel):
    """
    注册请求。

    字段:
        email:        邮箱（必须是有效邮箱格式）
        password:     密码（8-72 字符，至少含一个字母和一个数字）
        display_name: 显示名称（2-50 字符）

    Pydantic 的 EmailStr 会自动校验邮箱格式。
    如果传入 "not-an-email"，Pydantic 会返回 422 错误。
    """
    email: EmailStr = Field(..., description="注册邮箱")
    password: str = Field(
        ...,
        min_length=8,
        max_length=72,  # bcrypt 最多处理 72 字节
        description="密码（8-72 字符）",
    )
    display_name: str = Field(
        ...,
        min_length=2,
        max_length=50,
        description="显示名称",
    )

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """
        校验密码强度。

        规则：
        - 至少包含一个字母
        - 至少包含一个数字
        """
        if not re.search(r"[a-zA-Z]", v):
            raise ValueError("密码必须至少包含一个字母")
        if not re.search(r"\d", v):
            raise ValueError("密码必须至少包含一个数字")
        return v

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        """清理显示名称的前后空格。"""
        v = v.strip()
        if not v:
            raise ValueError("显示名称不能为空")
        return v


class LoginRequest(BaseModel):
    """登录请求。"""
    email: EmailStr = Field(..., description="登录邮箱")
    password: str = Field(..., description="登录密码")


# =============================================================================
# 响应 Schema（服务器 → 客户端）
# =============================================================================

class TokenResponse(BaseModel):
    """
    Token 响应。

    返回给客户端用于后续请求的认证凭证。

    access_token: JWT 字符串
    token_type:   认证类型（Bearer）
    expires_in:   过期时间（秒）
    """
    access_token: str = Field(..., description="JWT 访问令牌")
    token_type: str = Field(default="bearer", description="令牌类型")
    expires_in: int = Field(default=86400, description="过期时间（秒）")


class UserInfoResponse(BaseModel):
    """
    用户信息响应。

    注意：不包含 password_hash！永远不通过 API 返回密码。
    """
    id: str
    email: str
    display_name: str
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, dt: datetime | None) -> str | None:
        """将 datetime 对象序列化为 ISO 8601 字符串。"""
        if dt is None:
            return None
        return dt.isoformat()

    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    """注册成功响应。"""
    user: UserInfoResponse
    token: TokenResponse
