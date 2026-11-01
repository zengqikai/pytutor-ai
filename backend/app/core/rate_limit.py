"""
进程内限流中间件
================

按客户端 IP 做 60 秒滑动窗口计数，重点保护注册/登录（防密码爆破）和
其余 API（防单客户端刷爆 LLM 费用）。

边界：
- 只在**当前进程**内计数。多 worker / 多实例部署时每人一份计数，
  真实上限是配置值 × 进程数；生产应换成 Redis 或网关层限流。
- `X-Forwarded-For` 默认**不采信**（`TRUST_PROXY_HEADERS=False`）：直连部署下
  客户端能随便伪造，每个请求换个假 IP 就绕过了登录限流。只有前面确实有可信
  反向代理并会覆写该头时才打开。
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.observability.logger import get_logger

logger = get_logger(__name__)

AUTH_PATHS = {"/api/v1/auth/login", "/api/v1/auth/register"}
SKIP_PREFIXES = ("/api/v1/health", "/docs", "/openapi.json", "/redoc")


def client_key(request: Request) -> str:
    """客户端标识。

    只有 TRUST_PROXY_HEADERS=True 时才读 `X-Forwarded-For`：直连部署下
    任何人都能加这个头，每次换一个假 IP 就等于没有限流。
    """
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._requests = 0

    def _limit_for(self, path: str) -> tuple[str, int] | None:
        if path in AUTH_PATHS:
            return "auth", settings.AUTH_RATE_LIMIT_PER_MINUTE
        if path.startswith("/api/"):
            return "api", settings.RATE_LIMIT_PER_MINUTE
        return None

    async def dispatch(self, request: Request, call_next):
        if not settings.RATE_LIMIT_ENABLED or request.method == "OPTIONS":
            return await call_next(request)

        path = request.url.path
        if path.startswith(SKIP_PREFIXES):
            return await call_next(request)

        rule = self._limit_for(path)
        if rule is None:
            return await call_next(request)

        scope, limit = rule
        key = (scope, client_key(request))
        now = time.monotonic()
        window = self._hits[key]
        while window and now - window[0] >= 60:
            window.popleft()

        if len(window) >= limit:
            retry_after = max(1, int(60 - (now - window[0])) + 1)
            logger.warning("rate_limited", scope=scope, client=key[1], path=path)
            return JSONResponse(
                status_code=429,
                content={"detail": "请求过于频繁，请稍后再试"},
                headers={"Retry-After": str(retry_after)},
            )

        window.append(now)
        self._requests += 1
        if self._requests % 1000 == 0:
            self._prune(now)
        return await call_next(request)

    def _prune(self, now: float) -> None:
        stale = [k for k, q in self._hits.items() if not q or now - q[-1] >= 60]
        for k in stale:
            self._hits.pop(k, None)
