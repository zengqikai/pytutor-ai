"""
FastAPI 应用入口
===============

这是整个后端的启动文件。采用"应用工厂"模式：
- create_app() 函数负责创建和配置 FastAPI 实例
- 这样做的好处是测试时可以创建独立的 app 实例，互不干扰

启动命令：
    uvicorn app.main:app --reload

然后访问：
    - API 文档：http://localhost:8000/docs
    - 健康检查：http://localhost:8000/api/v1/health
"""

from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sqlalchemy import text

from app.core.config import settings
from app.core.logging_config import setup_logging
from app.observability.langfuse_setup import setup_langfuse  # noqa: F401
from app.observability.otel_setup import setup_opentelemetry  # noqa: F401
from app.database.session import AsyncSessionFactory, engine
from app.observability.logger import get_logger
from app.observability.middleware import RequestLoggingMiddleware
from app.api.router import api_v1_router

# 在模块加载时初始化日志系统（在创建 app 之前）
# 因为后续所有模块都会 import get_logger，必须确保日志系统先就绪
setup_logging()

logger = get_logger(__name__)


# =============================================================================
# 应用生命周期管理（Lifespan）
# =============================================================================
# @asynccontextmanager 是 Python 的异步上下文管理器装饰器。
# yield 之前的代码在应用启动时执行，yield 之后的代码在应用关闭时执行。
# 这替代了旧版 FastAPI 的 @app.on_event("startup/shutdown") 装饰器。
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    管理 FastAPI 应用的完整生命周期。

    启动时：初始化数据库连接池、Redis 连接等。
    关闭时：优雅地释放所有资源（断开数据库连接、关闭 Redis 等）。
    """
    # ========== 启动逻辑 ==========
    logger.info(
        "app_starting",
        app_name=settings.app_name,
        env=settings.app_env,
        host=settings.host,
        port=settings.port,
        database_type="SQLite" if settings.is_sqlite else "PostgreSQL",
    )

    # 重建 RAG 检索索引（从数据库加载所有 chunk 到内存）
    try:
        from app.database.session import AsyncSessionFactory
        from app.services.rag_service import rebuild_index

        async with AsyncSessionFactory() as session:
            chunk_count = await rebuild_index(session)
            logger.info("rag_index_rebuilt_on_startup", chunk_count=chunk_count)
    except Exception as e:
        logger.warning("rag_index_rebuild_failed", error=str(e))

    yield  # <-- 应用运行期间停在这里

    # ========== 关闭逻辑 ==========
    logger.info("app_shutting_down")
    # 释放数据库引擎（关闭所有连接池中的连接）
    await engine.dispose()
    logger.info("app_shutdown_complete")


# =============================================================================
# 应用工厂函数
# =============================================================================

def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用实例。

    采用工厂函数而不是全局 app = FastAPI() 的原因：
    1. 测试时可以创建多个独立的 app 实例
    2. 不同的部署环境可以用不同的配置
    3. 避免模块级别的副作用
    """
    app = FastAPI(
        # Swagger 文档标题
        title=settings.app_name,
        # API 版本
        version="0.1.0",
        # 描述
        description="AI 驱动的个性化 Python 编程学习平台",
        # API 文档 URL（设为 None 可以在生产环境禁用文档）
        docs_url="/docs" if settings.debug else None,
        # OpenAPI Schema URL
        openapi_url="/openapi.json" if settings.debug else None,
        # 生命周期管理
        lifespan=lifespan,
    )

    # ==============================
    # 中间件注册（顺序很重要！后注册的先执行）
    # ==============================

    # 1. 请求日志中间件 —— 记录每个请求的方法、路径、状态码、耗时
    app.add_middleware(RequestLoggingMiddleware)

    # 2. CORS 中间件 —— 允许前端跨域访问
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ==============================
    # 注册路由
    # ==============================
    # 将 v1 所有子路由注册到 /api/v1 路径下
    app.include_router(api_v1_router, prefix="/api/v1")

    # ==============================
    # 异常处理器
    # ==============================

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """
        全局异常处理器 —— 兜底所有未被特定处理器捕获的异常。

        现在使用 structlog 记录异常，相比 print 的好处：
        - 自动附带时间戳、日志级别、模块路径
        - 生产环境输出 JSON 格式，方便搜索和分析
        - 可以绑定额外的上下文（如 request_id）
        """
        # 从 request.state 获取 request_id（由中间件设置的）
        request_id = getattr(request.state, "request_id", "unknown")

        logger.error(
            "unhandled_exception",
            request_id=request_id,
            path=request.url.path,
            method=request.method,
            error_type=type(exc).__name__,
            error_detail=str(exc),
            exc_info=True,  # 记录完整堆栈信息
        )

        return JSONResponse(
            status_code=500,
            content={
                "data": None,
                "message": "服务器内部错误" if not settings.debug else str(exc),
                "error": {
                    "type": type(exc).__name__,
                    "detail": str(exc) if settings.debug else "请联系管理员",
                },
            },
        )

    # ==============================
    # 健康检查接口（直接注册，不走路由模块）
    # ==============================
    @app.get("/api/v1/health", tags=["系统"])
    async def health_check():
        """
        健康检查接口。

        实际检测数据库连接（执行 SELECT 1 查询）。
        如果数据库不可用，api 状态仍为 healthy，但 database 会显示 unhealthy。
        """
        db_status = "healthy"
        db_error = None

        try:
            # 执行最简单的 SQL 查询来验证数据库连接
            async with AsyncSessionFactory() as session:
                await session.execute(text("SELECT 1"))
        except Exception as e:
            db_status = "unhealthy"
            db_error = str(e)
            logger.error("health_check_db_failed", error=db_error)

        overall_status = "ok" if db_status == "healthy" else "degraded"

        return {
            "status": overall_status,
            "app_name": settings.app_name,
            "version": "0.1.0",
            "environment": settings.app_env,
            "components": {
                "api": "healthy",
                "database": db_status,
            },
            "error": db_error,
            "timestamp": datetime.utcnow().isoformat(),
        }

    return app


# =============================================================================
# 创建全局 app 实例
# =============================================================================
app = create_app()
