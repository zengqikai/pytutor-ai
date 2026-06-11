"""
Python 初学者误区模型
=====================

Misconception：8 类常见 Python 初学者误区定义
MisconceptionEvent：用户出现误区的诊断记录
"""

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class Misconception(Base, TimestampMixin):
    """Python 初学者常见误区定义。"""

    __tablename__ = "misconceptions"

    code: Mapped[str] = mapped_column(
        String(10), unique=True, index=True, comment="误区编号 M1-M8"
    )
    name: Mapped[str] = mapped_column(String(100), comment="误区名称")
    description: Mapped[str] = mapped_column(Text, comment="误区详细描述")
    typical_patterns: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="典型代码模式（JSON 数组，用于规则匹配）"
    )
    related_concepts: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="关联知识点，逗号分隔"
    )
    recommended_strategy: Mapped[str] = mapped_column(
        String(50), default="progressive_hint", comment="推荐教学策略"
    )

    def __repr__(self) -> str:
        return f"<Misconception({self.code}: {self.name})>"


class MisconceptionEvent(Base, TimestampMixin):
    """用户误区诊断记录。"""

    __tablename__ = "misconception_events"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    misconception_id: Mapped[str] = mapped_column(
        String, ForeignKey("misconceptions.id", ondelete="SET NULL"), nullable=True
    )
    submission_id: Mapped[str | None] = mapped_column(String, nullable=True)
    exercise_id: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, comment="诊断置信度 0-1")
    evidence: Mapped[str | None] = mapped_column(Text, nullable=True, comment="诊断依据")
    code_snippet: Mapped[str | None] = mapped_column(Text, nullable=True)

    def __repr__(self) -> str:
        return f"<MisconceptionEvent(user={self.user_id}, confidence={self.confidence})>"
