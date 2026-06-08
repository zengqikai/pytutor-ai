"""
日志系统配置
============

使用 structlog（结构化日志）+ 标准 logging 的组合：

架构说明：
---------
用户代码 → structlog（生成结构化事件）→ 标准 logging（传输到控制台/文件）

为什么不用 print？
- print 输出没有时间戳、没有级别、没有来源文件位置
- 生产环境中需要 JSON 格式的日志，方便 ELK/Loki 等日志收集系统解析
- structlog 可以"绑定上下文"——比如给每个日志自动加上 user_id、request_id

日志级别（从低到高）：
- DEBUG:   详细的调试信息（开发时使用）
- INFO:    常规运行信息（用户登录、请求处理等）
- WARNING: 警告信息（接近限流阈值、配置不推荐等）
- ERROR:   错误信息（某次请求失败、数据库连接断开等）
- CRITICAL: 严重错误（应用无法启动、数据丢失等）
"""

import io
import logging
import sys
from typing import Any

import structlog

from app.core.config import settings


def setup_logging() -> None:
    """
    初始化全局日志系统。

    这个函数应在应用启动时调用一次（在 create_app 之前或 lifespan 启动阶段）。

    做了什么：
    1. 配置标准 logging 的输出格式和级别
    2. 配置 structlog 的处理器链（Processor Chain）
    3. 根据环境（开发/生产）切换输出格式
    """

    # ==============================
    # 第〇步：修复 Windows 控制台编码问题
    # ==============================
    # Windows 中文版终端默认使用 GBK 编码，无法输出 emoji 和部分 Unicode 字符。
    # 用 UTF-8 wrapper 替换 stdout，解决日志输出时的 UnicodeEncodeError。
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(
            sys.stdout.buffer,
            encoding="utf-8",
            errors="replace",  # 不可编码的字符用 ? 替代，不抛异常
        )

    # ==============================
    # 第一步：配置标准 logging（底层传输）
    # ==============================
    log_level = getattr(logging, settings.log_level.upper(), logging.DEBUG)

    if settings.log_format == "json":
        # 生产环境：JSON 格式输出到 stdout
        # 每条日志是一行 JSON，方便 Logstash/Fluentd/Loki 解析
        logging.basicConfig(
            format="%(message)s",  # 只输出消息本身（消息已经是 JSON）
            stream=sys.stdout,
            level=log_level,
        )
    else:
        # 开发环境：带时间戳和级别的可读格式
        # 格式：[2026-06-08 10:00:00] INFO    module.name  message
        logging.basicConfig(
            format="[%(asctime)s] %(levelname)-7s %(name)-25s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            stream=sys.stdout,
            level=log_level,
        )

    # ==============================
    # 第二步：配置 structlog（上层结构化处理）
    # ==============================

    # structlog 的处理器链（Processor Chain）：
    # 每个日志事件依次经过以下处理器，就像流水线一样：
    #
    # raw event → add_log_level → add_timestamp → filter_by_level → format → output
    #

    shared_processors: list[Any] = [
        # 1. 添加日志级别名称（INFO, ERROR 等）
        structlog.stdlib.add_log_level,
        # 2. 添加时间戳（ISO 8601 格式）
        structlog.processors.TimeStamper(fmt="iso"),
        # 3. 添加调用位置（文件名:行号）——开发时很有用
        structlog.stdlib.PositionalArgumentsFormatter(),
        # 4. 添加堆栈信息（仅用于异常日志）
        structlog.processors.StackInfoRenderer(),
        # 5. 格式化异常对象为可读字符串
        structlog.processors.format_exc_info,
        # 6. 添加进程 ID（生产环境排查问题时有用）
        structlog.processors.add_log_level,
    ]

    # 根据环境选择最终输出格式
    if settings.log_format == "json":
        # 生产环境：序列化为 JSON
        renderer = structlog.processors.JSONRenderer()
    else:
        # 开发环境：彩色控制台输出（不同级别用不同颜色）
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            pad_event=25,  # 事件名称补齐到 25 个字符，对齐显示
        )

    structlog.configure(
        processors=shared_processors + [
            # 最后一步：将 structlog 事件转给标准 logging 输出
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        # 使用标准 logging 作为输出后端
        logger_factory=structlog.stdlib.LoggerFactory(),
        # 不使用缓存（避免不同模块的 logger 互相影响）
        cache_logger_on_first_use=False,
    )

    # ==============================
    # 第三步：设置第三方库的日志级别
    # ==============================
    # 避免第三方库的 DEBUG 日志刷屏
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    # uvicorn 的访问日志保持 INFO（每个请求一行，监控需要）
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)

    # ==============================
    # 完成
    # ==============================
    # 用 print 而不是 logger——因为此时日志系统刚初始化，用 logger 反而会循环
    print(f"[日志] 日志系统初始化完成 (级别={settings.log_level}, 格式={settings.log_format})")
