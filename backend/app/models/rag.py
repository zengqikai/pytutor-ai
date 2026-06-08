"""
RAG 知识库模型
==============

RAGDocument：知识文档（如一篇完整的 Python 教程）
RAGChunk：文档切分后的片段（检索的基本单位）

关系：
    一篇 RAGDocument 包含多个 RAGChunk
    每个 Chunk 是一个独立的检索单元

知识库来源（SRS FR-RAG-001）：
    - Python 基础概念
    - 课程大纲
    - 示例代码
    - 常见错误
    - 练习题模板
"""

from typing import TYPE_CHECKING, List

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base, TimestampMixin

if TYPE_CHECKING:
    pass


class RAGDocument(Base, TimestampMixin):
    """
    知识文档表。

    每行代表一篇完整的教学文档（如 "Python 变量与数据类型"）。
    """

    __tablename__ = "rag_documents"

    # ==============================
    # 基本信息
    # ==============================
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="文档标题",
    )
    source_type: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        comment="来源类型：manual | uploaded | generated",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="文档原始内容（Markdown 格式）",
    )

    # ==============================
    # 元数据
    # ==============================
    difficulty: Mapped[str] = mapped_column(
        String(20),
        default="beginner",
        comment="难度：beginner | intermediate | advanced",
    )
    concepts: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="关联知识点，逗号分隔（如 variables,data_types）",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        comment="是否启用（禁用后不再参与检索）",
    )

    # ==============================
    # 关系
    # ==============================
    chunks: Mapped[List["RAGChunk"]] = relationship(
        "RAGChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<RAGDocument(title={self.title}, chunks={len(self.chunks)})>"


class RAGChunk(Base, TimestampMixin):
    """
    文档片段表。

    每个 chunk 是检索的基本单元。
    包含原始文本和用于 TF-IDF 关键词匹配的 tokens。
    """

    __tablename__ = "rag_chunks"

    # ==============================
    # 关联
    # ==============================
    document_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("rag_documents.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
        comment="所属文档 ID",
    )

    # ==============================
    # 内容
    # ==============================
    chunk_index: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="在文档中的顺序索引",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="片段文本内容",
    )
    heading: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="所属章节标题（如 '## 列表的基本操作'）",
    )

    # ==============================
    # 检索相关
    # ==============================
    tokens: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="分词后的 tokens（空格分隔），用于关键词检索",
    )
    difficulty: Mapped[str] = mapped_column(
        String(20),
        default="beginner",
        comment="难度级别",
    )
    concepts: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="关联知识点标签",
    )

    # ==============================
    # 使用统计
    # ==============================
    retrieval_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="被检索到的次数",
    )
    use_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        comment="被实际用于生成回答的次数",
    )

    # ==============================
    # 关系
    # ==============================
    document: Mapped["RAGDocument"] = relationship(
        "RAGDocument",
        back_populates="chunks",
    )

    def __repr__(self) -> str:
        preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<RAGChunk(idx={self.chunk_index}, heading={self.heading})>"
