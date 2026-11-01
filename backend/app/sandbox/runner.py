"""
统一代码执行边界
================

所有"执行学生代码"的入口都必须经过这里，不能各自 import executor 或
docker_executor。入口分散的后果是：练习判题、自由编码、Agent 三条路径
用不同的隔离策略，改一处漏两处。

策略由配置决定（见 app/core/config.py）：

| sandbox_mode | Docker 可用 | isolation_required | 行为 |
| --- | --- | --- | --- |
| auto        | 是          | 任意               | Docker |
| auto        | 否          | False              | 子进程（开发降级） |
| auto        | 否          | True               | 拒绝执行 |
| docker      | 是          | 任意               | Docker |
| docker      | 否          | False              | 子进程（需显式配置才降级） |
| docker      | 否          | True               | 拒绝执行 |
| subprocess  | 任意        | False              | 子进程 |
| subprocess  | 任意        | True               | 拒绝执行 |

拒绝执行时返回 status="unavailable"，调用方按"未通过"处理，绝不能
把"没跑"当成"跑对了"。
"""

from app.core.config import settings
from app.observability.logger import get_logger
from app.sandbox.executor import execute_python_code_with_input

logger = get_logger(__name__)

UNAVAILABLE_RESULT = {
    "status": "unavailable",
    "exit_code": None,
    "stdout": "",
    "stderr": "代码执行环境不可用：服务端未运行隔离沙箱（Docker），已拒绝执行学生代码。",
    "runtime_ms": 0,
    "memory_kb": None,
    "timeout_triggered": False,
}


async def _docker_ready() -> bool:
    try:
        from app.sandbox.docker_executor import _docker_available
        return await _docker_available()
    except Exception as e:  # docker CLI 缺失、权限不足等
        logger.warning("docker_probe_failed", error=str(e)[:200])
        return False


async def execute_student_code(code: str, stdin_input: str = "") -> dict:
    """
    执行学生代码的唯一入口。

    参数:
        code: Python 源代码
        stdin_input: 标准输入（ACM 模式）

    返回:
        与 executor 一致的字典；status 可能为
        completed | error | timeout | blocked | unavailable
    """
    mode = (settings.sandbox_mode or "auto").strip().lower()
    required = settings.isolation_required

    if mode == "subprocess":
        if required:
            logger.error("subprocess_blocked_by_isolation_policy")
            return dict(UNAVAILABLE_RESULT)
        return await execute_python_code_with_input(code, stdin_input)

    if mode in ("auto", "docker"):
        if await _docker_ready():
            from app.sandbox.docker_executor import run_in_docker
            return await run_in_docker(code, stdin_input)
        if required:
            logger.error("docker_required_but_unavailable", mode=mode)
            return dict(UNAVAILABLE_RESULT)
        logger.info("sandbox_fallback_to_subprocess", mode=mode)
        return await execute_python_code_with_input(code, stdin_input)

    logger.warning("unknown_sandbox_mode", mode=mode)
    if required:
        return dict(UNAVAILABLE_RESULT)
    return await execute_python_code_with_input(code, stdin_input)


async def execute_student_code_plain(code: str) -> dict:
    """不带 stdin 的便捷入口（Agent 工具使用）。"""
    return await execute_student_code(code, "")
