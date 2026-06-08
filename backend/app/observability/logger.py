"""
预配置的 Logger 获取函数
========================

整个项目通过 get_logger(__name__) 获取 logger，而不是直接 import structlog。

用法示例：
    from app.observability.logger import get_logger

    logger = get_logger(__name__)
    logger.info("user_login", user_id="u_123", method="password")
    logger.error("db_connection_failed", db_host="localhost", error=str(e))
"""

import structlog


def get_logger(name: str | None = None):
    """
    获取一个预配置的 structlog logger。

    参数:
        name: 通常传 __name__，这样日志中会显示模块路径（如 app.services.auth_service）

    返回:
        structlog.BoundLogger: 可以 .info(), .error(), .debug() 等的日志对象

    使用示例:
        >>> logger = get_logger(__name__)
        >>> logger.info("user_registered", user_id="123", email="user@example.com")
        [2026-06-08 10:00:00] INFO    my.module    user_registered user_id=123 email=user@example.com
    """
    return structlog.get_logger(name)
