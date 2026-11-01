"""
认证服务与令牌的离线测试
========================

覆盖之前只靠集成测试的路径：
- 密码哈希不存明文、错误密码不通过
- JWT 往返、篡改与过期
- 注册重复邮箱返回 409，登录错误统一返回 401（不泄露邮箱是否存在）
- 禁用账户返回 403
"""

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.chat  # noqa: F401
import app.models.exercise  # noqa: F401
import app.models.misconception  # noqa: F401
import app.models.profile  # noqa: F401
import app.models.prompt  # noqa: F401
import app.models.rag  # noqa: F401
import app.models.submission  # noqa: F401
import app.models.user  # noqa: F401
from app.database.base import Base
from app.schemas.auth import RegisterRequest
from app.security.jwt import create_access_token, decode_access_token
from app.security.password import hash_password, verify_password
from app.services.auth_service import login_user, register_user


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


def test_password_hash_is_salted_and_verifiable():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("secret124", hashed)
    # 同一密码两次哈希不同（随机盐），但都能验证
    assert hashed != hash_password("secret123")


def test_jwt_roundtrip_and_tamper():
    token = create_access_token("u-1", "student")
    payload = decode_access_token(token)
    assert payload["sub"] == "u-1"
    assert payload["role"] == "student"

    assert decode_access_token(token + "x") is None


def test_jwt_expiry_rejected():
    from datetime import timedelta

    token = create_access_token("u-1", "student", expires_delta=timedelta(seconds=-1))
    assert decode_access_token(token) is None


@pytest.mark.asyncio
async def test_register_then_login(db):
    req = RegisterRequest(
        email="a@example.com", password="secret123", display_name="学生A"
    )
    created = await register_user(db, req)
    assert created.user.email == "a@example.com"
    assert created.token.access_token

    token = await login_user(db, "a@example.com", "secret123")
    assert token.access_token


@pytest.mark.asyncio
async def test_duplicate_email_conflict(db):
    req = RegisterRequest(
        email="dup@example.com", password="secret123", display_name="重复"
    )
    await register_user(db, req)

    with pytest.raises(HTTPException) as exc:
        await register_user(db, req)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_login_does_not_reveal_which_field_is_wrong(db):
    req = RegisterRequest(
        email="b@example.com", password="secret123", display_name="学生B"
    )
    await register_user(db, req)

    with pytest.raises(HTTPException) as wrong_pw:
        await login_user(db, "b@example.com", "wrongpass1")
    with pytest.raises(HTTPException) as no_user:
        await login_user(db, "nobody@example.com", "secret123")

    assert wrong_pw.value.status_code == no_user.value.status_code == 401
    assert wrong_pw.value.detail == no_user.value.detail


@pytest.mark.asyncio
async def test_disabled_account_rejected(db):
    req = RegisterRequest(
        email="off@example.com", password="secret123", display_name="停用"
    )
    created = await register_user(db, req)

    from sqlalchemy import select

    from app.models.user import User

    user = (
        await db.execute(select(User).where(User.id == created.user.id))
    ).scalar_one()
    user.is_active = False
    await db.commit()

    with pytest.raises(HTTPException) as exc:
        await login_user(db, "off@example.com", "secret123")
    assert exc.value.status_code == 403
