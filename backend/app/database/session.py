"""
数据库引擎与会话管理
====================

管理数据库连接的生命周期。

核心概念：
---------
Engine（引擎）：数据库连接的"池子"。创建一次，全局复用。
                管理着多个底层 TCP 连接到数据库。
Session（会话）：一次"数据库对话"。每个 HTTP 请求创建自己的会话，
                请求结束后归还。确保不同请求之间数据隔离。

异步 vs 同步：
    同步：db.query(User).all()        → 阻塞当前线程直到数据库返回
    异步：await db.execute(stmt)       → 不阻塞，等待期间可以处理其他请求

为什么异步很重要：
    FastAPI 是异步框架，主线程只有一个事件循环。
    如果数据库查询是同步（阻塞）的，整个服务在处理一个请求时无法响应其他请求。
    异步查询让"等待数据库返回"的时间可以用于处理其他请求。
"""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# =============================================================================
# 创建异步数据库引擎
# =============================================================================
# create_async_engine 创建一个异步引擎实例。
# - echo=False: 不打印每一条 SQL 语句（调试时可以设为 True）
# - pool_size: 连接池大小（SQLite 不支持连接池，所以设为 1）
# - connect_args: 传给数据库驱动的额外参数
#   - SQLite: check_same_thread=False（允许跨线程使用同一连接）
#   - PostgreSQL: 不需要特殊参数
# =============================================================================

if settings.is_sqlite:
    # SQLite 不支持连接池，所以 pool_size=1
    # check_same_thread=False: 允许不同线程使用同一个 SQLite 连接
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,  # 开发模式打印 SQL
        pool_size=1,          # SQLite 每次只能一个连接写入
        connect_args={"check_same_thread": False},
    )
else:
    # PostgreSQL 支持连接池，能够高效处理并发请求
    engine = create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_size=20,               # 连接池保留 20 个连接
        max_overflow=10,            # 高峰时额外创建最多 10 个
        pool_pre_ping=True,         # 使用前检查连接是否有效
        pool_recycle=3600,          # 每小时回收旧连接（防止数据库端断开）
    )

# =============================================================================
# 创建会话工厂
# =============================================================================
# async_sessionmaker 是一个"会话工厂"——每次调用创建一个新的 AsyncSession。
# expire_on_commit=False:
#   提交事务后不"过期"对象属性。设为 False 是因为在 FastAPI 中，
#   我们可能在提交后还需要读取对象的属性（如返回给前端）。
# =============================================================================
AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# =============================================================================
# 获取数据库会话的依赖注入函数
# =============================================================================
# 这个函数会被 FastAPI 的 Depends() 使用。
# 每个 HTTP 请求都会调用一次，生成独立的数据库会话。
# 请求结束后自动 close() 归还连接。

# 使用方式：
#     @router.get("/users/me")
#     async def get_me(db: AsyncSession = Depends(get_db)):
#         result = await db.execute(select(User).where(...))
#         return result.scalar()
# =============================================================================

async def get_db():
    """
    FastAPI 依赖注入：为每个请求创建独立的数据库会话。

    工作流程：
    1. 请求进入 → 创建一个新的 AsyncSession
    2. 业务代码使用这个 session 查询/修改数据
    3. 请求结束 → 关闭 session，归还连接到池中
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session          # 交给 FastAPI 和业务代码
            await session.commit() # 如果没有任何异常，自动提交
        except Exception:
            await session.rollback()  # 有异常则回滚，保证数据一致性
            raise                     # 重新抛出异常，让上层处理
        finally:
            await session.close()    # 无论如何都关闭会话
