"""
SQLAlchemy 声明基类和通用 Mixin
===============================

所有数据库模型的基类都继承自 Base。
TimestampMixin 提供通用的时间戳字段。

UUID 主键 vs 自增 ID：
    UUID 的好处：
    1. 在分布式系统中不会冲突（不同服务器生成的 ID 都是唯一的）
    2. 不暴露数据量（自增 ID 会让外部猜到有多少用户/订单）
    3. 前端可以提前生成 ID，不用等数据库返回

    UUID 的代价：
    - 字符串比整数大（32 字符 vs 4 字节）
    - 索引效率略低（但对本项目规模无影响）
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """
    SQLAlchemy 2.0 的声明式基类。

    所有数据库模型都继承这个类。
    继承它之后，SQLAlchemy 会自动把 Python 类映射为数据库表。
    """
    pass


class TimestampMixin:
    """
    时间戳 Mixin —— 给模型自动加上 id、created_at、updated_at 三个字段。

    Mixin 是一种"混入"模式：把这个类作为父类之一继承，
    子类自动获得这些字段，不需要在每个模型中重复定义。

    用法：
        class User(Base, TimestampMixin):
            __tablename__ = "users"
            email: Mapped[str] = mapped_column(unique=True)
    """

    # UUID 主键
    # server_default=func.uuid4() 表示由数据库生成 UUID
    # 而不是 Python 端生成，确保不同实例创建的记录不会冲突
    id: Mapped[str] = mapped_column(
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        index=True,
    )

    # 创建时间
    # server_default=func.now() 表示由数据库服务器填充当前时间
    # 比 Python 端填充更可靠（不受应用服务器时钟偏移影响）
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 更新时间
    # onupdate=func.now() 表示每次更新记录时自动更新为当前时间
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
