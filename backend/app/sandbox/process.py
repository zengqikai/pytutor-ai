"""
子进程执行辅助
==============

`asyncio.subprocess.communicate()` 会把子进程的全部输出读进内存后才返回，
学生写一个 `while True: print('x')` 就能在 10 秒超时前把服务端内存打满。

这里提供两个辅助函数：

1. `communicate_with_limit`：边读边丢弃超过上限的输出，最多只保留 limit 字节；
2. `terminate_process_tree`：超时时连同子进程树一起杀掉。Windows 上用
   `taskkill /T`，POSIX 上用进程组（调用方需传 `start_new_session=True`）。

注意：subprocess 模式本身不是安全边界（没有文件系统/网络隔离），
这里只负责"别把输出全量塞进内存"和"别留下孤儿进程"。
"""

from __future__ import annotations

import asyncio
import os
import subprocess

from app.observability.logger import get_logger

logger = get_logger(__name__)

_READ_CHUNK = 64 * 1024


async def _read_limited(
    stream: asyncio.StreamReader | None, limit: int
) -> tuple[bytes, bool]:
    """读取一个管道，最多保留 limit 字节，超出部分继续读掉但不保存。"""
    if stream is None:
        return b"", False

    kept: list[bytes] = []
    kept_size = 0
    truncated = False
    while True:
        chunk = await stream.read(_READ_CHUNK)
        if not chunk:
            break
        if kept_size < limit:
            take = chunk[: limit - kept_size]
            kept.append(take)
            kept_size += len(take)
            if len(take) < len(chunk):
                truncated = True
        else:
            truncated = True
    return b"".join(kept), truncated


async def communicate_with_limit(
    proc: asyncio.subprocess.Process,
    input_bytes: bytes | None,
    limit: int,
) -> tuple[bytes, bytes, bool]:
    """等价于 `proc.communicate(input)`，但输出最多保留 limit 字节。

    返回 (stdout, stderr, truncated)。
    """
    if input_bytes is not None and proc.stdin is not None:
        try:
            proc.stdin.write(input_bytes)
            await proc.stdin.drain()
        except (BrokenPipeError, ConnectionResetError):
            # 学生代码没读 stdin 就退出了，不是错误
            pass
        finally:
            try:
                proc.stdin.close()
            except Exception:
                pass

    stdout, out_trunc = await _read_limited(proc.stdout, limit)
    stderr, err_trunc = await _read_limited(proc.stderr, limit)
    await proc.wait()
    return stdout, stderr, out_trunc or err_trunc


def _kill_tree_windows(pid: int) -> None:
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:  # taskkill 缺失/超时
        logger.warning("taskkill_failed", pid=pid, error=str(exc)[:120])


async def terminate_process_tree(proc: asyncio.subprocess.Process) -> None:
    """终止子进程及其后代，并等待回收。"""
    if proc.returncode is not None:
        return

    if os.name == "nt":
        _kill_tree_windows(proc.pid)
    else:
        try:
            os.killpg(os.getpgid(proc.pid), 9)
        except (ProcessLookupError, PermissionError):
            pass

    try:
        proc.kill()
    except ProcessLookupError:
        pass

    try:
        await proc.wait()
    except Exception:
        pass
