"""
权限回归测试
============

这些用例守护三处"曾经敞开"的入口。它们不依赖运行中的服务器，
直接调用依赖函数 / 纯函数，因此可以在 CI 里离线跑：

1. /setup/*        —— 未配置令牌等于关闭；令牌错误返回 403；比较用常数时间
2. require_role    —— 学生不能进入教师/管理员接口
3. 参考答案闸门     —— 学生没通过、也没试够次数时不能拿到答案
"""

import pytest
from fastapi import HTTPException

from app.api.v1.exercises import SOLUTION_ATTEMPT_THRESHOLD, solution_denial_reason
from app.api.v1.setup import _verify_setup_token
from app.core.config import settings
from app.models.user import User, UserRole
from app.security.dependencies import require_role


def make_user(role: UserRole) -> User:
    """构造一个未入库的 User 对象，只用于角色判断。"""
    return User(
        id="u-1",
        email="u1@example.com",
        password_hash="x",
        display_name="测试用户",
        role=role,
    )


# =============================================================================
# /setup/* 令牌
# =============================================================================

class TestSetupToken:
    def test_disabled_when_token_unset(self, monkeypatch):
        """未配置 SETUP_TOKEN 时接口应表现为不存在（404），而不是放行。"""
        monkeypatch.setattr(settings, "SETUP_TOKEN", "")
        with pytest.raises(HTTPException) as exc:
            _verify_setup_token(None)
        assert exc.value.status_code == 404

    def test_missing_header_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "SETUP_TOKEN", "secret-value")
        with pytest.raises(HTTPException) as exc:
            _verify_setup_token(None)
        assert exc.value.status_code == 403

    def test_wrong_token_rejected(self, monkeypatch):
        monkeypatch.setattr(settings, "SETUP_TOKEN", "secret-value")
        with pytest.raises(HTTPException) as exc:
            _verify_setup_token("wrong-value")
        assert exc.value.status_code == 403

    def test_correct_token_accepted(self, monkeypatch):
        monkeypatch.setattr(settings, "SETUP_TOKEN", "secret-value")
        assert _verify_setup_token("secret-value") is None


# =============================================================================
# require_role
# =============================================================================

class TestRequireRole:
    async def test_student_blocked_from_staff_routes(self):
        """学生调用教师接口必须 403。"""
        checker = require_role(UserRole.INSTRUCTOR, UserRole.ADMIN)
        with pytest.raises(HTTPException) as exc:
            await checker(current_user=make_user(UserRole.STUDENT))
        assert exc.value.status_code == 403

    async def test_instructor_allowed(self):
        checker = require_role(UserRole.INSTRUCTOR, UserRole.ADMIN)
        user = make_user(UserRole.INSTRUCTOR)
        assert await checker(current_user=user) is user

    async def test_admin_only_route_blocks_instructor(self):
        """仅管理员的路由，教师也不能进。"""
        checker = require_role(UserRole.ADMIN)
        with pytest.raises(HTTPException) as exc:
            await checker(current_user=make_user(UserRole.INSTRUCTOR))
        assert exc.value.status_code == 403


# =============================================================================
# 参考答案闸门
# =============================================================================

class TestSolutionGate:
    def test_student_with_no_attempts_denied(self):
        assert solution_denial_reason(UserRole.STUDENT, []) is not None

    def test_student_with_few_failed_attempts_denied(self):
        events = ["exercise_failed"] * (SOLUTION_ATTEMPT_THRESHOLD - 1)
        assert solution_denial_reason(UserRole.STUDENT, events) is not None

    def test_student_at_threshold_allowed(self):
        events = ["exercise_failed"] * SOLUTION_ATTEMPT_THRESHOLD
        assert solution_denial_reason(UserRole.STUDENT, events) is None

    def test_hint_requests_do_not_count_as_attempts(self):
        """反复要提示不能凑够次数骗开答案。"""
        events = ["hint_requested"] * 10
        assert solution_denial_reason(UserRole.STUDENT, events) is not None

    def test_student_who_passed_allowed_on_first_try(self):
        assert solution_denial_reason(UserRole.STUDENT, ["exercise_passed"]) is None

    def test_staff_always_allowed(self):
        for role in (UserRole.INSTRUCTOR, UserRole.ADMIN):
            assert solution_denial_reason(role, []) is None


# =============================================================================
# SSE 入口
# =============================================================================

class TestStreamingDisabled:
    """流式入口未复用诊断/检索/画像上下文，必须明确拒绝而不是降级回复。"""

    @pytest.mark.asyncio
    async def test_stream_endpoint_returns_501(self):
        from app.api.v1.chat import stream_chat_message
        from app.schemas.chat import SendMessageRequest

        with pytest.raises(HTTPException) as exc:
            await stream_chat_message(
                session_id="s-1",
                request=SendMessageRequest(content="for i in range(3): print(i)"),
                db=None,  # 未使用：应在触库前就拒绝
                current_user=make_user(UserRole.STUDENT),
            )
        assert exc.value.status_code == 501
        assert "messages" in exc.value.detail
