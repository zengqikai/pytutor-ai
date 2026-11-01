"""
Docker 代码沙箱（工业级隔离）
=============================

生产环境使用 Docker 容器执行用户代码，提供：
- 完全文件系统隔离
- 网络隔离（--network none）
- 资源限制（CPU/内存/进程数）
- 非 root 用户执行
- 只读根文件系统
- seccomp/AppArmor 安全策略

本模块只负责"在容器里跑"，不做任何降级决策。是否允许退回子进程由
app.sandbox.runner 按配置统一决定，避免每个入口各自判断。

超时清理：容器带唯一 `--name`，超时后 `docker kill` + `docker rm -f`
双保险。只 kill 客户端进程的话，`--rm` 不会触发，容器会一直挂着。
"""

import asyncio
import re
import shutil
import tempfile
import time
import uuid
from pathlib import Path

from app.observability.logger import get_logger
from app.sandbox.process import communicate_with_limit

logger = get_logger(__name__)

EXECUTION_TIMEOUT = 10
MAX_OUTPUT_SIZE = 100 * 1024
DOCKER_IMAGE = "python:3.12-slim"

# 容器名只允许字母数字和连字符
_CONTAINER_PREFIX = "pytutor-sandbox-"


async def _docker_available() -> bool:
    """检查 Docker 是否可用。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "info",
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await proc.wait()
        return proc.returncode == 0
    except Exception:
        return False


async def _remove_container(name: str) -> None:
    """强行删除容器（幂等）。"""
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "rm", "-f", name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        await asyncio.wait_for(proc.wait(), timeout=5)
    except Exception as exc:  # docker 不存在 / 卡住
        logger.debug("docker_rm_failed", container=name, error=str(exc)[:120])


def _unavailable(reason: str) -> dict:
    return {
        "status": "unavailable",
        "stdout": "",
        "stderr": reason,
        "exit_code": None,
        "runtime_ms": 0,
        "memory_kb": None,
        "timeout_triggered": False,
    }


async def run_in_docker(code: str, stdin_input: str = "") -> dict:
    """
    在 Docker 容器中安全执行 Python 代码（严格模式，不降级）。

    Docker 不可用时直接返回 status="unavailable"——是否退回子进程由
    app.sandbox.runner 按配置决定。这里自行降级会让"生产环境必须隔离"
    的约束形同虚设。

    安全策略：
    - --network none: 禁止网络
    - --memory 128m --cpus 1: 资源限制
    - --read-only: 只读文件系统
    - --user 1000:1000: 非 root
    - --pids-limit 50: 限制进程数
    - --rm: 执行完自动删除容器（超时另走 docker rm -f）
    """
    if not await _docker_available():
        logger.error("docker_unavailable_strict")
        return _unavailable("Docker 不可用，已拒绝执行学生代码。")

    from app.sandbox.security import check_code_safety

    code = code.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    is_safe, reason = check_code_safety(code)
    if not is_safe:
        return {
            "status": "blocked",
            "stdout": "",
            "stderr": f"[安全拦截] {reason}",
            "exit_code": None,
            "runtime_ms": 0,
            "memory_kb": None,
            "timeout_triggered": False,
        }

    tmp_dir = tempfile.mkdtemp(prefix="sandbox_")
    tmp_file = Path(tmp_dir) / "code.py"
    container_name = f"{_CONTAINER_PREFIX}{uuid.uuid4().hex[:16]}"
    proc = None

    try:
        tmp_file.write_text(code, encoding="utf-8")

        cmd = [
            "docker", "run", "--rm",
            "--name", container_name,
            "--network", "none",
            "--memory", "128m",
            "--cpus", "1",
            "--pids-limit", "50",
            "--read-only",
            "--tmpfs", "/tmp:exec",
            "--user", "1000:1000",
            "-v", f"{tmp_dir}:/code:ro",
            "-w", "/code",
            "-e", "PYTHONIOENCODING=utf-8",
            "-e", "PYTHONUTF8=1",
            DOCKER_IMAGE,
            "python", "-X", "utf8", "code.py",
        ]

        start = time.perf_counter()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # 空输入 = 一个空行，和本地模式保持一致
        input_bytes = (stdin_input if stdin_input else "").encode("utf-8")
        if not input_bytes.endswith(b"\n"):
            input_bytes += b"\n"

        try:
            stdout_bytes, stderr_bytes, truncated = await asyncio.wait_for(
                communicate_with_limit(proc, input_bytes, MAX_OUTPUT_SIZE),
                timeout=EXECUTION_TIMEOUT,
            )
            timeout_triggered = False
        except asyncio.TimeoutError:
            await _remove_container(container_name)
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except Exception:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
            stdout_bytes = b""
            stderr_bytes = "[超时] 代码执行超过10秒".encode("utf-8")
            timeout_triggered = True
            truncated = False

        elapsed = (time.perf_counter() - start) * 1000
        stdout = stdout_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")
        stderr = stderr_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")
        stderr = re.sub(r'File ".*?/code\.py", line', 'File "<code>", line', stderr)
        if truncated:
            stderr = (stderr + "\n[输出超过 100KB，已截断]").strip()

        return {
            "status": "timeout"
            if timeout_triggered
            else ("completed" if proc.returncode == 0 else "error"),
            "stdout": stdout.rstrip(),
            "stderr": stderr,
            "exit_code": proc.returncode,
            "runtime_ms": round(elapsed, 2),
            "memory_kb": None,
            "timeout_triggered": timeout_triggered,
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "stdout": "",
            "stderr": "Docker 未安装",
            "exit_code": -1,
            "runtime_ms": 0,
            "memory_kb": None,
            "timeout_triggered": False,
        }
    finally:
        # 无论正常/超时/异常，容器都不能留下
        if proc is not None and proc.returncode is None:
            await _remove_container(container_name)
            try:
                await asyncio.wait_for(proc.wait(), timeout=5)
            except Exception:
                proc.kill()
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def execute_in_docker(code: str, stdin_input: str = "") -> dict:
    """兼容旧调用名：交给统一执行边界 runner 决定隔离策略。"""
    from app.sandbox.runner import execute_student_code
    return await execute_student_code(code, stdin_input)
