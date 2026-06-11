"""
Pytest 共享 fixtures。

提供：
- test_client: 异步 HTTP 测试客户端（httpx.AsyncClient）
- auth_headers: 已认证的请求头
- db_session: 测试数据库会话
"""

import asyncio
import pytest
import httpx

BASE_URL = "http://localhost:8000/api/v1"
TEST_EMAIL = "test_ci@t.com"
TEST_PASSWORD = "test12345"


@pytest.fixture(scope="session")
def event_loop():
    """创建 session 级别的事件循环。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_client():
    """返回一个异步 HTTP 客户端。"""
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=30) as client:
        yield client


@pytest.fixture
async def auth_headers(test_client):
    """返回带有 JWT token 的 Authorization 头（自动注册/登录）。"""
    # 尝试登录
    resp = await test_client.post("/auth/login", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD,
    })
    if resp.status_code != 200:
        # 注册新用户
        resp = await test_client.post("/auth/register", json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
            "display_name": "CI Test User",
        })
        assert resp.status_code == 201, f"Register failed: {resp.text}"

        # 注册后重新登录
        resp = await test_client.post("/auth/login", json={
            "email": TEST_EMAIL, "password": TEST_PASSWORD,
        })

    assert resp.status_code == 200, f"Login failed: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
