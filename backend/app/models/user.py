"""
用户模型
=======

对应数据库中的 users 表。

字段说明：
- id: UUID 主键（比自增 ID 更安全，不暴露用户数量）
- email: 邮箱，唯一索引（用于登录）
- password_hash: bcrypt 哈希后的密码（绝不存储明文！）
- display_name: 显示名称（可包含中文、空格等）
- role: 角色（student / instructor / admin）
- is_active: 是否激活（管理员可禁用账户）
"""

from enum import Enum

from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class UserRole(str, Enum):
    """
    用户角色枚举。

    继承 str 的好处：Pydantic 可以自动序列化为 JSON 字符串，
    不需要额外配置。
    """
    STUDENT = "student"
    INSTRUCTOR = "instructor"
    ADMIN = "admin"


class User(Base, TimestampMixin):
    """
    用户表。

    SQLAlchemy 2.0 使用 Mapped[] 类型注解来声明列，
    取代了旧版的 Column() 写法。

    继承链：User → TimestampMixin + Base → 数据库表
    TimestampMixin 提供：id, created_at, updated_at
    Base 提供：ORM 映射能力
    """

    __tablename__ = "users"

    # ==============================
    # 基本信息
    # ==============================
    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,      # 邮箱唯一，防止重复注册
        index=True,       # 创建索引（登录时需要根据邮箱查找用户）
        nullable=False,
    )
    password_hash: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    # ==============================
    # 角色和状态
    # ==============================
    role: Mapped[UserRole] = mapped_column(
        default=UserRole.STUDENT,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # ==============================
    # 可选的额外信息（MVP 阶段预留）
    # ==============================
    # bio: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        """对象的字符串表示（调试用）。"""
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
