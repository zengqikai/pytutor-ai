"""
Langfuse 可观测性配置
======================

LiteLLM + Langfuse 自动追踪：
- 每次 LLM 调用的输入/输出/Token/延迟
- Agent 工作流每个节点的耗时
- 成本统计

接入方式：LiteLLM 原生支持，设置 callback 即可。
"""

import litellm

from app.core.config import settings
from app.observability.logger import get_logger

logger = get_logger(__name__)


def setup_langfuse():
    """
    初始化 Langfuse 可观测。

    配置环境变量或在代码中设置。

    免费自托管或使用 Langfuse Cloud:
        LANGFUSE_PUBLIC_KEY=pk-xxx
        LANGFUSE_SECRET_KEY=sk-xxx
        LANGFUSE_HOST=https://cloud.langfuse.com
    """
    import os

    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "")

    if not public_key or not secret_key:
        logger.info("langfuse_skipped", reason="未配置 LANGFUSE_PUBLIC_KEY/SECRET_KEY，跳过")
        return

    # LiteLLM 原生 Langfuse callback
    litellm.success_callback = ["langfuse"]
    litellm.failure_callback = ["langfuse"]

    os.environ.setdefault("LANGFUSE_HOST", "https://cloud.langfuse.com")

    logger.info("langfuse_enabled")


def trace_agent_step(step_name: str, input_data: str = "", output_data: str = "", **kwargs):
    """
    记录 Agent 工作流节点的执行（轻量上下文管理器）。
    """
    import time as _time
    start = _time.perf_counter()
    logger.info("agent_step_start", step=step_name, **kwargs)
    return _TraceContext(step_name, start, _time)


class _TraceContext:
    def __init__(self, name, start, time_mod):
        self.name = name
        self.start = start
        self.time_mod = time_mod
        self.output = ""

    def __enter__(self):
        return self

    def __exit__(self, *args):
        elapsed = (self.time_mod.perf_counter() - self.start) * 1000
        logger.info("agent_step_complete", step=self.name, duration_ms=round(elapsed, 2), output=self.output[:200])
        return False


# 在应用启动时调用
setup_langfuse()
