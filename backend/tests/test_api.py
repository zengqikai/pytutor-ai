"""
API 集成测试
============

需要后端运行中（localhost:8000）。
测试核心 API 端点的响应格式和状态码。
"""

import pytest


@pytest.mark.integration
class TestHealthCheck:
    """健康检查。"""

    async def test_health_ok(self, test_client):
        resp = await test_client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["components"]["api"] == "healthy"
        assert data["components"]["database"] == "healthy"


@pytest.mark.integration
class TestAuth:
    """认证流程。"""

    async def test_login_ok(self, auth_headers):
        """登录成功返回 token。"""
        assert "Bearer" in auth_headers.get("Authorization", "")

    async def test_me_authenticated(self, test_client, auth_headers):
        """认证后可获取用户信息。"""
        resp = await test_client.get("/users/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in (data.get("data") or data)


@pytest.mark.integration
class TestMisconceptionAPI:
    """误区诊断 API。"""

    async def test_list_misconceptions(self, test_client, auth_headers):
        """列出所有误区。"""
        resp = await test_client.get("/misconceptions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 8

    async def test_diagnose_m1(self, test_client, auth_headers):
        """诊断 M1 误区。"""
        resp = await test_client.post("/misconceptions/diagnose", json={
            "code": "x = 5\nif x = 5:\n    print(x)",
            "stderr": "SyntaxError",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_misconception"] is True
        assert data["misconception_id"] == "M1"

    async def test_diagnose_clean_code(self, test_client, auth_headers):
        """干净代码不返回误区。"""
        resp = await test_client.post("/misconceptions/diagnose", json={
            "code": "print('hello')",
            "stderr": "",
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_misconception"] is False


@pytest.mark.integration
class TestProfileAPI:
    """学习画像 API。"""

    async def test_profile_me(self, test_client, auth_headers):
        """获取学习画像。"""
        resp = await test_client.get("/profile/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json().get("data") or resp.json()
        assert "level" in data
        assert "stats" in data
        assert "onboarding_done" in data

    async def test_profile_passed_ids(self, test_client, auth_headers):
        """获取已通过题目 ID。"""
        resp = await test_client.get("/profile/me/passed-ids", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "ids" in data
        assert isinstance(data["ids"], list)


@pytest.mark.integration
class TestTeacherAPI:
    """教师仪表盘 API。"""

    async def test_teacher_overview(self, test_client, auth_headers):
        """教师仪表盘返回聚合数据。"""
        resp = await test_client.get("/teacher/overview", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "misconception_stats" in data
        assert "students" in data
        assert data["summary"]["total_students"] >= 0
