"""
练习与测试用例模型
==================

Exercise：练习题（AI 生成或教师创建）
TestCase：测试用例（每个练习有多个测试用例，含隐藏用例）
"""

from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin


class Exercise(Base, TimestampMixin):
    """
    练习题表。

    可由 AI 自动生成或教师手动创建。
    """

    __tablename__ = "exercises"

    # ==============================
    # 基本信息
    # ==============================
    title: Mapped[str] = mapped_column(String(255), nullable=False, comment="题目标题")
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="题目描述（Markdown）")
    difficulty: Mapped[int] = mapped_column(
        Integer, default=1,
        comment="难度 1-5（1=非常简单, 5=挑战）"
    )

    # ==============================
    # 知识关联
    # ==============================
    concepts: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="关联知识点，逗号分隔（如 for_loop,list）"
    )
    learning_objective: Mapped[str | None] = mapped_column(
        String(500), nullable=True,
        comment="教学目标（学生完成后应掌握什么）"
    )

    # ==============================
    # 示例
    # ==============================
    example_input: Mapped[str | None] = mapped_column(Text, nullable=True, comment="示例输入")
    example_output: Mapped[str | None] = mapped_column(Text, nullable=True, comment="示例输出")

    # ==============================
    # 参考答案（对学生隐藏）
    # ==============================
    reference_solution: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="参考解法（仅教师/AI 可见）"
    )

    # ==============================
    # 元数据
    # ==============================
    source: Mapped[str] = mapped_column(
        String(20), default="ai_generated",
        comment="来源：ai_generated | teacher_created"
    )
    is_published: Mapped[bool] = mapped_column(
        Boolean, default=True,
        comment="是否发布（草稿不可见）"
    )
    use_count: Mapped[int] = mapped_column(Integer, default=0, comment="被使用的次数")
    pass_rate: Mapped[float | None] = mapped_column(
        default=None, comment="通过率（0-1）"
    )

    # ==============================
    # 关系
    # ==============================
    test_cases: Mapped[List["TestCase"]] = relationship(
        "TestCase", back_populates="exercise",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Exercise(title={self.title}, difficulty={self.difficulty})>"


class TestCase(Base, TimestampMixin):
    """
    测试用例表。

    每个练习有多个测试用例，含隐藏用例（对学生不可见）。
    """

    __tablename__ = "test_cases"

    exercise_id: Mapped[str] = mapped_column(
        String, ForeignKey("exercises.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    input_data: Mapped[str | None] = mapped_column(Text, nullable=True, comment="标准输入")
    expected_output: Mapped[str] = mapped_column(Text, nullable=False, comment="期望输出")
    is_hidden: Mapped[bool] = mapped_column(
        Boolean, default=True,
        comment="是否隐藏（学生不可见）"
    )
    description: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
        comment="测试用例描述（如 '测试空列表'）"
    )
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # 关系
    exercise: Mapped["Exercise"] = relationship("Exercise", back_populates="test_cases")

    def __repr__(self) -> str:
        return f"<TestCase(desc={self.description}, hidden={self.is_hidden})>"
