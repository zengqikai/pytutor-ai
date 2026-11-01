"""
代码执行器
==========

在隔离环境中执行用户提交的 Python 代码。

支持两种模式：
1. Subprocess（dev）：子进程执行，适用于本地开发
2. Docker（prod）：容器执行，适用于生产环境

执行流程：
    1. 代码写入临时目录（不是仓库目录）
    2. 在隔离环境中执行 Python 脚本
    3. 捕获 stdout、stderr、exit_code、运行时间
    4. 清理临时目录
    5. 返回结构化结果

安全措施：
    - 执行超时（10 秒），超时杀掉整棵进程树
    - 输出边读边截断（最多保留 100KB），不会先把全部输出读进内存
    - 子进程只拿白名单环境变量（绝不把 API Key 传给学生的代码）
    - 子进程工作目录是临时目录，相对路径读不到 backend/.env 或数据库
    - 静态安全检查（strict 模式额外禁止 open/importlib 等）
    - 在受限用户下运行（Docker 模式）

重要：subprocess 模式只是"开发降级"，不构成安全边界。生产环境请使用
Docker（APP_ENV=production 会强制要求隔离沙箱）。
"""

import asyncio
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path

from app.observability.logger import get_logger
from app.sandbox.process import communicate_with_limit, terminate_process_tree

logger = get_logger(__name__)

# =============================================================================
# 执行限制配置
# =============================================================================
EXECUTION_TIMEOUT = 10  # 代码执行超时（秒）
MAX_OUTPUT_SIZE = 100 * 1024  # 最大输出大小（100KB）

# 子进程只继承这些环境变量。DEEPSEEK_API_KEY / DASHSCOPE_API_KEY 等
# 应用密钥绝不能让学生的代码读到。
_SAFE_ENV_KEYS = (
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "LANG",
    "LC_ALL",
)

_PATH_REPLACERS = (
    (r'File ".*?\\Temp\\\\?[^"]+", line', 'File "<code>", line'),
    (r'File ".*?/tmp/[^"]+", line', 'File "<code>", line'),
    (r'File ".*?student_code\.py", line', 'File "<code>", line'),
)


def _build_safe_env() -> dict[str, str]:
    env = {}
    for key in _SAFE_ENV_KEYS:
        value = os.environ.get(key)
        if value:
            env[key] = value
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONHASHSEED"] = "0"
    return env


def _sanitize_stderr(stderr: str) -> str:
    for pattern, replacement in _PATH_REPLACERS:
        stderr = re.sub(pattern, replacement, stderr)
    return stderr


async def _run_python(
    code: str, stdin_input: str, *, strict: bool
) -> dict:
    """两种入口共用的执行实现。"""
    from app.sandbox.security import check_code_safety

    code = code.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    is_safe, reason = check_code_safety(code, strict=strict)
    if not is_safe:
        logger.warning("code_blocked_by_security", reason=reason, strict=strict)
        return {
            "status": "blocked",
            "exit_code": None,
            "stdout": "",
            "stderr": f"[安全拦截] {reason}",
            "runtime_ms": 0,
            "memory_kb": None,
            "timeout_triggered": False,
        }

    # 每次执行一个独立临时目录：cwd 不是 backend/，相对路径读不到 .env
    run_dir = Path(tempfile.mkdtemp(prefix="ai_tutor_run_"))
    script_path = run_dir / "student_code.py"
    process = None
    try:
        script_path.write_text(code, encoding="utf-8")

        start = time.perf_counter()
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-X",
            "utf8",
            str(script_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=_build_safe_env(),
            cwd=str(run_dir),
            start_new_session=(os.name != "nt"),
        )

        # ACM 标准：空输入 = 一个空行（\n），不是关闭 stdin
        input_bytes = stdin_input.encode("utf-8")
        if not stdin_input or not stdin_input.endswith("\n"):
            input_bytes = (stdin_input + "\n").encode("utf-8")

        try:
            stdout_bytes, stderr_bytes, truncated = await asyncio.wait_for(
                communicate_with_limit(process, input_bytes, MAX_OUTPUT_SIZE),
                timeout=EXECUTION_TIMEOUT,
            )
            timeout_triggered = False
        except asyncio.TimeoutError:
            await terminate_process_tree(process)
            stdout_bytes = b""
            stderr_bytes = "[超时] 代码执行超过 10 秒，已被终止。".encode("utf-8")
            timeout_triggered = True
            truncated = False

        elapsed_ms = (time.perf_counter() - start) * 1000
        stdout = stdout_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")
        stderr = _sanitize_stderr(
            stderr_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")
        )
        if truncated:
            stderr = (stderr + "\n[输出超过 100KB，已截断]").strip()

        return {
            "status": "timeout"
            if timeout_triggered
            else ("error" if process.returncode != 0 else "completed"),
            "exit_code": process.returncode,
            "stdout": stdout.rstrip(),  # ACM 模式去除末尾换行
            "stderr": stderr,
            "runtime_ms": round(elapsed_ms, 2),
            "memory_kb": None,
            "timeout_triggered": timeout_triggered,
        }
    except FileNotFoundError:
        return {
            "status": "error",
            "exit_code": -1,
            "stdout": "",
            "stderr": "Python 解释器未找到",
            "runtime_ms": 0,
            "memory_kb": None,
            "timeout_triggered": False,
        }
    except Exception as e:
        logger.error("execution_error", error=str(e))
        return {
            "status": "error",
            "exit_code": -1,
            "stdout": "",
            "stderr": f"执行错误: {str(e)}",
            "runtime_ms": 0,
            "memory_kb": None,
            "timeout_triggered": False,
        }
    finally:
        if process is not None and process.returncode is None:
            await terminate_process_tree(process)
        shutil.rmtree(run_dir, ignore_errors=True)


async def execute_python_code_with_input(code: str, stdin_input: str = "") -> dict:
    """
    执行 Python 代码，可选传入 stdin 数据。

    参数:
        code: Python 源代码
        stdin_input: 标准输入数据（模拟 input() 读取的数据）

    返回: 同 execute_python_code
    """
    return await _run_python(code, stdin_input, strict=True)


async def execute_python_code(code: str) -> dict:
    """
    执行 Python 代码并返回结果（不带 stdin）。

    返回:
        dict: {
            "status": "completed" | "timeout" | "error" | "blocked",
            "exit_code": int | None,
            "stdout": str,
            "stderr": str,
            "runtime_ms": float,
            "memory_kb": int | None,
            "timeout_triggered": bool,
        }
    """
    return await _run_python(code, "", strict=True)
