"""
认证服务模块
============

负责注册和登录的业务逻辑。

为什么要把业务逻辑从 API 路由中分离出来？
1. 路由只负责接收请求和返回响应（"控制器"角色）
2. 服务层负责业务逻辑（可以复用、测试）
3. 如果未来要添加 CLI 命令或后台任务，可以直接调用服务函数
"""

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.auth import RegisterRequest, RegisterResponse, TokenResponse, UserInfoResponse
from app.security.jwt import create_access_token
from app.security.password import hash_password, verify_password
from app.observability.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# 注册
# =============================================================================

async def register_user(
    db: AsyncSession,
    request: RegisterRequest,
) -> RegisterResponse:
    """
    注册新用户。

    流程：
    1. 检查邮箱是否已被注册
    2. 对密码进行哈希处理
    3. 创建 User 记录
    4. 生成 JWT
    5. 返回用户信息 + Token

    参数:
        db: 数据库会话
        request: 注册请求（email, password, display_name）

    返回:
        RegisterResponse: 含用户信息和 JWT

    异常:
        HTTPException 409: 邮箱已被注册
    """
    # 步骤 1：检查邮箱是否已存在
    result = await db.execute(select(User).where(User.email == request.email))
    existing_user = result.scalar_one_or_none()

    if existing_user is not None:
        logger.warning("register_email_exists", email=request.email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该邮箱已被注册",
        )

    # 步骤 2：哈希密码（绝不存储明文密码！）
    hashed_pw = hash_password(request.password)

    # 步骤 3：创建用户记录
    user = User(
        email=request.email,
        password_hash=hashed_pw,
        display_name=request.display_name,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)  # 获取数据库生成的 id、created_at 等

    # 步骤 3.5：创建学习画像（SRS FR-PROFILE-001）
    from app.services.profile_service import get_or_create_profile
    await get_or_create_profile(db, user.id)

    # 步骤 4：生成 JWT
    token = create_access_token(user_id=user.id, role=user.role.value)

    logger.info(
        "user_registered",
        user_id=user.id,
        email=user.email,
        role=user.role.value,
    )

    # 步骤 5：构造响应
    return RegisterResponse(
        user=UserInfoResponse.model_validate(user),
        token=TokenResponse(access_token=token),
    )


# =============================================================================
# 登录
# =============================================================================

async def login_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> TokenResponse:
    """
    用户登录。

    流程：
    1. 根据邮箱查找用户
    2. 验证密码
    3. 生成 JWT
    4. 返回 Token

    安全考虑：
    - 无论邮箱不存在还是密码错误，统一返回"邮箱或密码错误"
    - 避免给攻击者提供"该邮箱已注册"的信息（防止账号枚举攻击）

    参数:
        db: 数据库会话
        email: 登录邮箱
        password: 明文密码

    返回:
        TokenResponse: 含 JWT

    异常:
        HTTPException 401: 邮箱或密码错误
        HTTPException 403: 账户已被禁用
    """
    # 步骤 1：查找用户
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    # 步骤 2：验证（统一错误提示，防止枚举攻击）
    if user is None or not verify_password(password, user.password_hash):
        logger.warning("login_failed", email=email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="邮箱或密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 步骤 3：检查账户状态
    if not user.is_active:
        logger.warning("login_disabled_account", user_id=user.id, email=email)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="账户已被禁用，请联系管理员",
        )

    # 步骤 4：生成 JWT
    token = create_access_token(user_id=user.id, role=user.role.value)

    logger.info("user_logged_in", user_id=user.id, email=email, role=user.role.value)

    return TokenResponse(access_token=token)
