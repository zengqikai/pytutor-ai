"""
统一执行边界测试
================

守护 task 03 的核心承诺：生产环境宁可拒绝执行，也不把学生代码
放进宿主进程。所有分支都用 monkeypatch 模拟，不真的启动 Docker 或跑代码。
"""

import pytest

from app.core.config import settings
from app.sandbox import runner

SUB_OK = {
    "status": "completed", "exit_code": 0, "stdout": "ok", "stderr": "",
    "runtime_ms": 1.0, "memory_kb": None, "timeout_triggered": False,
}


@pytest.fixture
def stub_execut(monkeypatch):
    """把子进程执行替换成固定返回，避免真的执行。"""
    calls = []

    async def fake(code, stdin_input=""):
        calls.append((code, stdin_input))
        return dict(SUB_OK)

    monkeypatch.setattr(runner, "execute_python_code_with_input", fake)
    return calls


@pytest.fixture
def no_docker(monkeypatch):
    async def unavailable():
        return False
    monkeypatch.setattr(runner, "_docker_ready", unavailable)


@pytest.fixture
def has_docker(monkeypatch):
    async def available():
        return True
    monkeypatch.setattr(runner, "_docker_ready", available)


def set_policy(monkeypatch, mode: str, require: bool, app_env: str = "development"):
    monkeypatch.setattr(settings, "sandbox_mode", mode)
    monkeypatch.setattr(settings, "sandbox_require_isolation", require)
    monkeypatch.setattr(settings, "app_env", app_env)


async def test_subprocess_allowed_in_development(monkeypatch, stub_execut, no_docker):
    set_policy(monkeypatch, "auto", require=False)
    result = await runner.execute_student_code("print(1)")
    assert result["status"] == "completed"
    assert stub_execut, "应当调用子进程执行器"


async def test_production_refuses_without_docker(monkeypatch, stub_execut, no_docker):
    """APP_ENV=production 时即使没显式配置也必须拒绝。"""
    set_policy(monkeypatch, "auto", require=False, app_env="production")
    result = await runner.execute_student_code("print(1)")
    assert result["status"] == "unavailable"
    assert stub_execut == [], "拒绝执行时不得退回子进程"


async def test_explicit_require_blocks_subprocess_mode(monkeypatch, stub_execut, no_docker):
    set_policy(monkeypatch, "subprocess", require=True)
    result = await runner.execute_student_code("print(1)")
    assert result["status"] == "unavailable"
    assert stub_execut == []


async def test_docker_mode_uses_container_when_available(monkeypatch, has_docker):
    set_policy(monkeypatch, "docker", require=True)
    calls = []

    async def fake_docker(code, stdin_input=""):
        calls.append(code)
        return {"status": "completed"}

    import app.sandbox.docker_executor as de
    monkeypatch.setattr(de, "run_in_docker", fake_docker)

    result = await runner.execute_student_code("print(1)")
    assert result["status"] == "completed"
    assert calls == ["print(1)"]


async def test_unknown_mode_does_not_silently_execute_when_required(monkeypatch, stub_execut, no_docker):
    set_policy(monkeypatch, "kubernetes", require=True)
    result = await runner.execute_student_code("print(1)")
    assert result["status"] == "unavailable"
    assert stub_execut == []
