"""
代码执行器
==========

在隔离环境中执行用户提交的 Python 代码。

支持两种模式：
1. Subprocess（dev）：子进程执行，适用于本地开发
2. Docker（prod）：容器执行，适用于生产环境

执行流程：
    1. 代码写入临时文件
    2. 在隔离环境中执行 Python 脚本
    3. 捕获 stdout、stderr、exit_code、运行时间
    4. 清理临时文件
    5. 返回结构化结果

安全措施：
    - 执行超时（10 秒）
    - 输出大小限制（100KB）
    - 在受限用户下运行（Docker 模式）
    - 静态安全检查（在执行前调用 security.py）
"""

import asyncio
import os
import tempfile
import time
from pathlib import Path

from app.observability.logger import get_logger

logger = get_logger(__name__)

# =============================================================================
# 执行限制配置
# =============================================================================
EXECUTION_TIMEOUT = 10  # 代码执行超时（秒）
MAX_OUTPUT_SIZE = 100 * 1024  # 最大输出大小（100KB）


async def execute_python_code_with_input(code: str, stdin_input: str = "") -> dict:
    """
    执行 Python 代码，可选传入 stdin 数据。

    参数:
        code: Python 源代码
        stdin_input: 标准输入数据（模拟 input() 读取的内容）

    返回: 同 execute_python_code
    """
    from app.sandbox.security import check_code_safety

    code = code.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    is_safe, reason = check_code_safety(code)
    if not is_safe:
        return {"status": "blocked", "exit_code": None, "stdout": "", "stderr": f"[安全拦截] {reason}", "runtime_ms": 0, "memory_kb": None, "timeout_triggered": False}

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", prefix="ai_tutor_", delete=False, encoding="utf-8") as f:
            f.write(code)
            tmp_path = Path(f.name)

        # 构建 UTF-8 环境
        import os as _os, sys as _sys
        env = {}
        for k, v in _os.environ.items():
            try: env[k] = v
            except Exception: env[k] = ""
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"

        start_time = time.perf_counter()
        process = await asyncio.create_subprocess_exec(
            _sys.executable, "-X", "utf8", str(tmp_path),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(input=stdin_input.encode("utf-8")),  # 始终传 bytes，空=空输入非关闭
                timeout=EXECUTION_TIMEOUT,
            )
            timeout_triggered = False
        except asyncio.TimeoutError:
            process.kill(); await process.wait()
            stdout_bytes, stderr_bytes = b"", "[超时] 代码执行超过 10 秒，已被终止。".encode("utf-8")
            timeout_triggered = True

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        import re
        stdout = stdout_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")[:MAX_OUTPUT_SIZE]
        stderr = stderr_bytes.decode("utf-8", errors="replace").replace("\r\n", "\n")
        stderr = re.sub(r'File ".*?\\Temp\\[^"]+", line', 'File "<code>", line', stderr)[:MAX_OUTPUT_SIZE]

        return {
            "status": "timeout" if timeout_triggered else ("error" if process.returncode != 0 else "completed"),
            "exit_code": process.returncode,
            "stdout": stdout.rstrip(),  # ACM 模式去除末尾换行
            "stderr": stderr,
            "runtime_ms": round(elapsed_ms, 2),
            "memory_kb": None,
            "timeout_triggered": timeout_triggered,
        }
    except FileNotFoundError:
        return {"status": "error", "exit_code": -1, "stdout": "", "stderr": "Python 解释器未找到", "runtime_ms": 0, "memory_kb": None, "timeout_triggered": False}
    except Exception as e:
        logger.error("execution_error", error=str(e))
        return {"status": "error", "exit_code": -1, "stdout": "", "stderr": str(e), "runtime_ms": 0, "memory_kb": None, "timeout_triggered": False}
    finally:
        if tmp_path and tmp_path.exists():
            try: tmp_path.unlink()
            except OSError: pass


async def execute_python_code(code: str) -> dict:
    """
    执行 Python 代码并返回结果。

    目前使用子进程模式（subprocess）。
    Docker 模式作为后续升级。

    参数:
        code: Python 源代码

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
    # 安全检查
    from app.sandbox.security import check_code_safety

    code = code.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    is_safe, reason = check_code_safety(code)
    if not is_safe:
        logger.warning("code_blocked_by_security", reason=reason)
        return {
            "status": "blocked",
            "exit_code": None,
            "stdout": "",
            "stderr": f"[安全拦截] {reason}",
            "runtime_ms": 0,
            "memory_kb": None,
            "timeout_triggered": False,
        }

    # 创建临时文件
    tmp_path = None
    try:
        # 写入临时 .py 文件
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".py",
            prefix="ai_tutor_",
            delete=False,
            encoding="utf-8",
        ) as f:
            f.write(code)
            tmp_path = Path(f.name)

        start_time = time.perf_counter()

        # 在子进程中执行
        process = await asyncio.create_subprocess_exec(
            "python",
            str(tmp_path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=EXECUTION_TIMEOUT,
            )
            timeout_triggered = False
        except asyncio.TimeoutError:
            # 超时：强制终止进程
            process.kill()
            await process.wait()
            stdout_bytes = b""
            stderr_bytes = "[超时] 代码执行超过 10 秒，已被终止。".encode("utf-8")
            timeout_triggered = True

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # 限制输出大小
        stdout = stdout_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_SIZE]
        stderr = stderr_bytes.decode("utf-8", errors="replace")[:MAX_OUTPUT_SIZE]

        if timeout_triggered:
            status = "timeout"
        elif process.returncode != 0:
            status = "error"
        else:
            status = "completed"

        logger.info(
            "code_executed",
            status=status,
            exit_code=process.returncode,
            runtime_ms=round(elapsed_ms, 2),
            timeout=timeout_triggered,
            output_len=len(stdout) + len(stderr),
        )

        return {
            "status": status,
            "exit_code": process.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "runtime_ms": round(elapsed_ms, 2),
            "memory_kb": None,  # 子进程模式下无法精确获取
            "timeout_triggered": timeout_triggered,
        }

    except FileNotFoundError:
        logger.error("python_not_found", error="Python 解释器未找到")
        return {
            "status": "error",
            "exit_code": -1,
            "stdout": "",
            "stderr": "沙箱错误：Python 解释器未找到",
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
        # 清理临时文件
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
