"""
Prompt 模板模型（SRS FR-ADMIN-003）
==================================

版本化的 Prompt 模板管理。
支持：版本化、可审计、可回滚。
"""

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class PromptTemplate(Base, TimestampMixin):
    """
    Prompt 模板表。

    每次修改创建新版本，旧版本保留用于回滚。
    is_active=True 的版本为当前使用版本。
    """

    __tablename__ = "prompt_templates"

    name: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True, comment="模板名称（如 tutor_system_prompt）"
    )
    version: Mapped[int] = mapped_column(
        Integer, default=1, comment="版本号"
    )
    category: Mapped[str] = mapped_column(
        String(50), default="general", comment="分类：teaching | code_review | exercise | safety | general"
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Prompt 内容"
    )
    description: Mapped[str | None] = mapped_column(
        String(500), nullable=True, comment="版本变更说明"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="是否当前使用版本"
    )
    created_by: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="修改者"
    )

    def __repr__(self) -> str:
        return f"<PromptTemplate(name={self.name}, v{self.version})>"
