"""
代码提交模型
============

CodeSubmission：学生提交的代码
ExecutionResult：单次执行的结果（一次提交可能执行多次）
"""

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin


class CodeSubmission(Base, TimestampMixin):
    """
    代码提交表。

    记录学生提交的 Python 代码及其关联信息。
    """

    __tablename__ = "code_submissions"

    # ==============================
    # 关联
    # ==============================
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="提交者 ID",
    )
    session_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("chat_sessions.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联的聊天会话 ID（可选）",
    )
    exercise_id: Mapped[str | None] = mapped_column(
        String,
        nullable=True,
        comment="关联的练习 ID（可选）",
    )

    # ==============================
    # 代码内容
    # ==============================
    code: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="提交的 Python 代码",
    )
    language: Mapped[str] = mapped_column(
        String(20),
        default="python",
        comment="编程语言",
    )

    # ==============================
    # 状态
    # ==============================
    status: Mapped[str] = mapped_column(
        String(30),
        default="pending",
        comment="执行状态：pending | running | completed | timeout | error | blocked",
    )

    def __repr__(self) -> str:
        preview = self.code[:50].replace("\n", " ")
        return f"<CodeSubmission(status={self.status}, code={preview}...)>"


class ExecutionResult(Base, TimestampMixin):
    """
    代码执行结果表。

    每次代码执行产生一条记录。
    """

    __tablename__ = "execution_results"

    # ==============================
    # 关联
    # ==============================
    submission_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("code_submissions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="关联的提交 ID",
    )

    # ==============================
    # 执行结果
    # ==============================
    exit_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="程序退出码（0=正常，非0=异常）",
    )
    stdout: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="标准输出",
    )
    stderr: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="标准错误输出",
    )
    status: Mapped[str] = mapped_column(
        String(30),
        default="completed",
        comment="执行状态：completed | timeout | memory_exceeded | blocked | error",
    )

    # ==============================
    # 性能指标
    # ==============================
    runtime_ms: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        comment="实际运行时间（毫秒）",
    )
    memory_kb: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="最大内存使用（KB）",
    )
    timeout_triggered: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        comment="是否触发了超时限制",
    )

    # ==============================
    # 测试结果（关联练习时）
    # ==============================
    test_results_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="测试用例执行结果（JSON 数组）",
    )

    def __repr__(self) -> str:
        return f"<ExecutionResult(status={self.status}, exit={self.exit_code})>"
