"""
HTTP 请求日志中间件
==================

自动记录每个 HTTP 请求的关键信息：
- 请求方法（GET, POST, PUT...）
- 请求路径
- 响应状态码
- 处理耗时

原理：
- FastAPI 的中间件机制类似"洋葱模型"：
  请求进入 → 中间件(前) → 实际处理函数 → 中间件(后) → 响应返回
- 中间件在"后"阶段记录日志，此时已知状态码和耗时
"""

import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.observability.logger import get_logger

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    请求日志中间件

    功能：
    1. 为每个请求生成唯一的 request_id（用于追踪完整调用链）
    2. 记录请求方法、路径、状态码、耗时
    3. 将 request_id 添加到响应头（方便前端报错时附带 ID 来排查）
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        """
        处理每个 HTTP 请求。

        参数:
            request: FastAPI/Starlette 的请求对象
            call_next: 调用下一个中间件或实际处理函数的回调

        返回:
            Response: HTTP 响应对象
        """

        # ========== 请求进入（前置处理）==========

        # 生成唯一请求 ID
        # uuid4 生成类似 a1b2c3d4-e5f6-7890-abcd-ef1234567890 的随机标识符
        request_id = str(uuid.uuid4())

        # 将 request_id 存入 request.state，后续代码可以通过 request.state.request_id 获取
        request.state.request_id = request_id

        # 记录开始时间（用于计算耗时）
        start_time = time.perf_counter()

        # ========== 调用实际处理函数 ==========
        # 这期间会执行路由匹配、参数解析、业务逻辑等
        response = await call_next(request)

        # ========== 响应返回（后置处理）==========

        # 计算处理耗时（毫秒）
        duration_ms = (time.perf_counter() - start_time) * 1000

        # 将 request_id 添加到响应头
        # X-Request-ID 是一种约定俗成的 HTTP 头命名方式
        response.headers["X-Request-ID"] = request_id

        # 记录请求日志
        # 使用 structlog 的 key=value 格式，方便后续查询和聚合
        log_method = logger.info if response.status_code < 400 else logger.warning

        log_method(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
            client_ip=request.client.host if request.client else "unknown",
        )

        return response
