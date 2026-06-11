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

开发降级：Docker 不可用时自动切回子进程模式。
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path

from app.observability.logger import get_logger

logger = get_logger(__name__)

EXECUTION_TIMEOUT = 10
MAX_OUTPUT_SIZE = 100 * 1024
DOCKER_IMAGE = "python:3.12-slim"


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


async def execute_in_docker(code: str, stdin_input: str = "") -> dict:
    """
    在 Docker 容器中安全执行 Python 代码。

    安全策略：
    - --network none: 禁止网络
    - --memory 128m --cpus 1: 资源限制
    - --read-only: 只读文件系统
    - --user 1000:1000: 非 root
    - --rm: 执行完自动删除容器
    - --pids-limit 50: 限制进程数
    """
    if not await _docker_available():
        logger.info("docker_unavailable_fallback")
        from app.sandbox.executor import execute_python_code_with_input
        return await execute_python_code_with_input(code, stdin_input)

    import re

    # 安全检查
    from app.sandbox.security import check_code_safety
    code = code.replace("\r\n", "\n").lstrip("﻿")
    is_safe, reason = check_code_safety(code)
    if not is_safe:
        return {"status": "blocked", "stdout": "", "stderr": f"[安全拦截] {reason}", "exit_code": None, "runtime_ms": 0, "memory_kb": None, "timeout_triggered": False}

    # 写入临时文件
    tmp_dir = tempfile.mkdtemp(prefix="sandbox_")
    tmp_file = Path(tmp_dir) / "code.py"

    try:
        tmp_file.write_text(code, encoding="utf-8")

        # 构建 Docker 命令
        cmd = [
            "docker", "run", "--rm",
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

        try:
            input_bytes = stdin_input.encode("utf-8") if stdin_input else None
            if input_bytes is None and stdin_input == "":
                input_bytes = b"\n"
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(input=input_bytes),
                timeout=EXECUTION_TIMEOUT,
            )
            timeout_triggered = False
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            stdout_bytes, stderr_bytes = b"", b"[超时] 代码执行超过10秒"
            timeout_triggered = True

        elapsed = (time.perf_counter() - start) * 1000
        stdout = stdout_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")[:MAX_OUTPUT_SIZE]
        stderr = stderr_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")
        stderr = re.sub(r'File ".*?/code\.py", line', 'File "<code>", line', stderr)[:MAX_OUTPUT_SIZE]

        return {
            "status": "timeout" if timeout_triggered else ("completed" if proc.returncode == 0 else "error"),
            "stdout": stdout.rstrip(),
            "stderr": stderr,
            "exit_code": proc.returncode,
            "runtime_ms": round(elapsed, 2),
            "memory_kb": None,
            "timeout_triggered": timeout_triggered,
        }
    except FileNotFoundError:
        return {"status": "error", "stdout": "", "stderr": "Docker 未安装", "exit_code": -1, "runtime_ms": 0, "memory_kb": None, "timeout_triggered": False}
    finally:
        import shutil
        try: shutil.rmtree(tmp_dir)
        except: pass
