"""
Alembic 迁移环境配置
===================

这个文件告诉 Alembic：
1. 从哪里获取数据库连接 URL（从我们的 config.py）
2. 哪些模型的表需要管理（所有继承 Base 的模型）
3. 如何运行迁移（在线/离线模式）

每次修改 models/ 中的模型后，运行：
    alembic revision --autogenerate -m "描述你的改动"
    alembic upgrade head
"""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# =============================================================================
# 导入我们的配置和模型
# =============================================================================
# 必须导入所有模型，这样 Alembic 的 --autogenerate 才能检测到表结构变化
from app.core.config import settings
from app.database.base import Base

# 导入所有模型（确保它们的表被 Base.metadata 注册）
from app.models.user import User  # noqa: F401
from app.models.chat import ChatSession, ChatMessage  # noqa: F401
from app.models.rag import RAGDocument, RAGChunk  # noqa: F401
from app.models.submission import CodeSubmission, ExecutionResult  # noqa: F401
from app.models.exercise import Exercise, TestCase  # noqa: F401
from app.models.profile import StudentProfile, StudentWeakness, LearningEvent  # noqa: F401

# =============================================================================
# Alembic Config 对象
# =============================================================================
config = context.config

# 设置日志（使用 alembic.ini 中的日志配置）
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# =============================================================================
# 核心配置：告诉 Alembic 要管理哪些表
# =============================================================================
# Base.metadata 包含了所有继承 Base 的模型的表定义
# Alembic 通过对比 metadata 和实际数据库来生成迁移脚本
target_metadata = Base.metadata


# =============================================================================
# 离线模式迁移（不连接数据库，生成 SQL 脚本）
# =============================================================================
def run_migrations_offline() -> None:
    """
    离线模式：只生成 SQL 语句，不实际执行。

    用途：
    - 审查即将执行的 SQL（安全检查）
    - 在无法直接连接数据库的环境中生成迁移脚本
    - export SQL 给 DBA 手动执行
    """
    context.configure(
        url=settings.database_url,
        target_metadata=target_metadata,
        literal_binds=True,          # 把 Python 值转为 SQL 字面量
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


# =============================================================================
# 在线模式迁移（连接数据库，执行迁移）
# =============================================================================
def do_run_migrations(connection):
    """
    在数据库连接上实际执行迁移。

    为什么在这里设置 context：
    - 需要传入一个真实的数据连接
    - configure 中的参数控制迁移行为
    """
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # compare_type=True: 检测列类型的变化（如 String(100) → String(200)）
        compare_type=True,
        # compare_server_default=True: 检测默认值的变化
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """
    在线模式：连接数据库并执行迁移。

    使用异步引擎（create_async_engine），因为我们的应用是异步的。
    """
    # 创建异步引擎连接到数据库
    connectable = create_async_engine(settings.database_url)

    async with connectable.connect() as connection:
        # run_sync 把异步连接转成同步（Alembic 内部是同步的）
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


# =============================================================================
# 入口
# =============================================================================
if context.is_offline_mode():
    run_migrations_offline()
else:
    # 在线模式需要异步运行
    asyncio.run(run_migrations_online())
