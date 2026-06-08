"""
JWT 令牌模块
============

负责生成和验证 JSON Web Token。

JWT 三段式结构：
    Header.Payload.Signature

    Header（头部）:   {"alg": "HS256", "typ": "JWT"}
    Payload（载荷）:  {"sub": "user_id", "role": "student", "exp": 1234567890, "iat": 1234567800}
    Signature（签名）: HMAC-SHA256(Header.Payload, secret_key)

工作流程：
    1. 用户登录成功 → 服务器用 secret_key 签发 JWT → 返回给客户端
    2. 客户端每次请求在 Authorization 头带上 JWT
    3. 服务器用同一个 secret_key 验证签名 → 确认是自家签发的 → 解析出 user_id 和 role

为什么可以信任 JWT？
    签名是用 secret_key 生成的。攻击者可以修改 Payload 中的 user_id（比如从自己的 ID 改成别人的），
    但无法生成正确的签名——因为没有 secret_key。服务器验证签名时会发现不匹配并拒绝。

为什么需要过期时间（exp）？
    万一 JWT 泄露，攻击者只能在一定时间内使用它。过期后自动失效。
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from jose import JWTError, jwt

from app.core.config import settings


# =============================================================================
# JWT 配置
# =============================================================================
# 注意：secret_key 在生产环境中必须是强随机字符串（至少 32 字符）
# 可以用以下命令生成：python -c "import secrets; print(secrets.token_urlsafe(32))"

ALGORITHM = "HS256"                          # 签名算法（HMAC + SHA-256）
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24        # Token 有效期：24 小时


def create_access_token(
    user_id: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    创建 JWT Access Token。

    参数:
        user_id: 用户 ID（UUID 字符串）
        role: 用户角色（"student" | "instructor" | "admin"）
        expires_delta: 自定义有效期（默认 24 小时）

    返回:
        str: 编码后的 JWT 字符串（三段 Base64，用 . 分隔）

    用法:
        token = create_access_token(user_id="abc-123", role="student")
    """
    # 计算过期时间
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    # JWT Payload（载荷）——包含需要传递的信息
    # sub = subject（主题，通常是用户 ID）
    # role = 用户角色
    # exp = expiration（过期时间，Unix 时间戳）
    # iat = issued at（签发时间）
    payload: dict[str, Any] = {
        "sub": user_id,
        "role": role,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    # 用 secret_key 签名并编码
    token = jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)
    return token


def decode_access_token(token: str) -> Optional[dict[str, Any]]:
    """
    解码并验证 JWT。

    参数:
        token: JWT 字符串

    返回:
        dict | None: 成功返回 Payload，失败（过期/签名不对/格式错误）返回 None

    JWTError 是最常见的异常，包括：
    - ExpiredSignatureError: Token 已过期
    - JWTClaimsError: Payload 中的字段不合法
    - JWTError: 签名验证失败、格式错误等

    用法:
        payload = decode_access_token(token)
        if payload is None:
            raise HTTPException(status_code=401, detail="无效的认证令牌")
        user_id = payload["sub"]
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
