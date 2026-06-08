"""
学习画像模型
============

StudentProfile：学生的学习画像，追踪知识掌握情况。
StudentWeakness：薄弱知识点记录。
LearningEvent：学习行为事件（用于分析）。
"""

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class StudentProfile(Base, TimestampMixin):
    """
    学生学习画像。

    每个学生有且仅有一个画像记录。
    记录整体学习状态和能力等级。
    """

    __tablename__ = "student_profiles"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, index=True, nullable=False,
    )

    # 能力等级 1-10
    level: Mapped[int] = mapped_column(Integer, default=1, comment="当前学习等级 1-10")

    # 统计
    total_exercises_completed: Mapped[int] = mapped_column(Integer, default=0)
    total_exercises_passed: Mapped[int] = mapped_column(Integer, default=0)
    total_code_submissions: Mapped[int] = mapped_column(Integer, default=0)
    total_chat_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_hints_used: Mapped[int] = mapped_column(Integer, default=0)

    # 知识点掌握（JSON 格式：{"variables": 0.8, "for_loop": 0.3, ...}）
    concept_mastery_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    # 推荐下一课
    recommended_concept: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="推荐的下一知识点"
    )

    def __repr__(self) -> str:
        return f"<StudentProfile(user={self.user_id}, level={self.level})>"


class StudentWeakness(Base, TimestampMixin):
    """
    薄弱知识点记录。

    当学生在某知识点上反复出错时记录。
    持续追踪，一旦掌握自动标记为 resolved。
    """

    __tablename__ = "student_weaknesses"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    concept: Mapped[str] = mapped_column(String(100), nullable=False, comment="知识点标识")
    fail_count: Mapped[int] = mapped_column(Integer, default=1, comment="连续失败次数")
    last_error_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="最后一次的错误类型"
    )
    severity: Mapped[int] = mapped_column(
        Integer, default=1, comment="严重程度 1-5（5=最薄弱）"
    )
    is_resolved: Mapped[bool] = mapped_column(
        default=False, comment="是否已解决"
    )

    def __repr__(self) -> str:
        return f"<Weakness(concept={self.concept}, fail={self.fail_count})>"


class LearningEvent(Base, TimestampMixin):
    """
    学习行为事件。

    记录学生每一次学习行为，用于后续分析。
    """

    __tablename__ = "learning_events"

    user_id: Mapped[str] = mapped_column(
        String, ForeignKey("users.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="事件类型：question_asked | code_submitted | exercise_passed | "
                "exercise_failed | hint_requested | concept_viewed | syntax_error | runtime_error"
    )
    concept: Mapped[str | None] = mapped_column(
        String(100), nullable=True, comment="关联知识点"
    )
    detail_json: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="事件详情（JSON）"
    )
