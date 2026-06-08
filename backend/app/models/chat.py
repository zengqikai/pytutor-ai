"""
聊天模型
=======

ChatSession（会话）和 ChatMessage（消息）模型。

关系：
    一个学生（User）可以有多个 ChatSession
    一个 ChatSession 包含多条 ChatMessage
    用户与消息之间通过 session 间接关联

设计说明：
    hint_level 记录在消息中，便于分析"什么时候给了什么级别的提示"。
    response_type 区分 AI 回复的类型（概念解释、代码反馈、练习等）。
"""

from datetime import datetime
from typing import TYPE_CHECKING, List

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ChatSession(Base, TimestampMixin):
    """
    聊天会话表。

    每个会话属于一个学生，包含该学生与 AI 导师的对话历史。
    title 是会话标题（可自动生成或学生自定义）。
    """

    __tablename__ = "chat_sessions"

    # ==============================
    # 关联
    # ==============================
    student_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属学生 ID",
    )

    # ==============================
    # 基本字段
    # ==============================
    title: Mapped[str] = mapped_column(
        String(255),
        default="新的对话",
        nullable=False,
        comment="会话标题",
    )
    is_active: Mapped[bool] = mapped_column(
        default=True,
        comment="会话是否活跃（学生可手动关闭）",
    )

    # ==============================
    # 关系（ORM 层面，不是数据库列）
    # ==============================
    # back_populates 告诉 SQLAlchemy：ChatMessage.session 和 ChatSession.messages 互为反向关系
    # cascade="all, delete-orphan"：删除会话时自动删除所有关联消息
    messages: Mapped[List["ChatMessage"]] = relationship(
        "ChatMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, title={self.title})>"


class ChatMessage(Base, TimestampMixin):
    """
    聊天消息表。

    每条消息属于一个会话，可以是：
    - role="user"：学生发送的消息
    - role="assistant"：AI 导师的回复
    - role="system"：系统注入的上下文（如 RAG 检索结果）

    hint_level 仅对 assistant 消息有意义（1-5），其他角色为 NULL。
    """

    __tablename__ = "chat_messages"

    # ==============================
    # 关联
    # ==============================
    session_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属会话 ID",
    )

    # ==============================
    # 消息内容
    # ==============================
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="消息角色：user | assistant | system",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="消息内容（文本或 JSON 字符串）",
    )

    # ==============================
    # AI 回复特有字段（role=assistant 时填充）
    # ==============================
    response_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="AI 回复类型：concept_explanation | code_feedback | hint | exercise | general",
    )
    hint_level: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="提示等级 1-5（仅 assistant 消息）",
    )
    related_concepts: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="关联知识点，逗号分隔",
    )
    next_action: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="建议下一步：try_exercise | read_concept | ask_question | try_again",
    )

    # ==============================
    # 元数据
    # ==============================
    token_count: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="本次消息消耗的 token 数（仅 assistant）",
    )
    metadata_json: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="额外元数据（JSON）：如引用的 RAG chunk IDs、使用的 Prompt 版本等",
    )

    # ==============================
    # 关系
    # ==============================
    session: Mapped["ChatSession"] = relationship(
        "ChatSession",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<ChatMessage(role={self.role}, content={preview})>"
