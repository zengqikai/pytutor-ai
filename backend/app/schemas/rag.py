"""
RAG 相关 Schemas
================
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_serializer


# =============================================================================
# 文档管理 Schema
# =============================================================================

class RAGDocumentCreate(BaseModel):
    """创建知识文档请求。"""
    title: str = Field(..., min_length=1, max_length=255)
    content: str = Field(..., min_length=1, description="Markdown 格式的文档内容")
    difficulty: str = Field(default="beginner")
    concepts: str | None = Field(default=None, description="逗号分隔的知识点标签")
    source_type: str = Field(default="manual")


class RAGDocumentResponse(BaseModel):
    """文档响应。"""
    id: str
    title: str
    source_type: str
    difficulty: str
    concepts: Optional[str] = None
    is_active: bool
    chunk_count: int = Field(default=0)
    created_at: datetime

    @field_serializer("created_at")
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat()

    model_config = {"from_attributes": True}


class RAGChunkResponse(BaseModel):
    """片段响应。"""
    id: str
    document_id: str
    chunk_index: int
    content: str
    heading: Optional[str] = None
    difficulty: str
    concepts: Optional[str] = None
    retrieval_count: int
    created_at: datetime

    @field_serializer("created_at")
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat()

    model_config = {"from_attributes": True}


# =============================================================================
# 检索 Schema
# =============================================================================

class RAGRetrievalRequest(BaseModel):
    """检索请求。"""
    query: str = Field(..., min_length=1, description="检索查询")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数")
    difficulty_filter: str | None = Field(default=None, description="按难度过滤")
    concept_filter: str | None = Field(default=None, description="按知识点过滤")


class RAGRetrievalResult(BaseModel):
    """单条检索结果。"""
    chunk_id: str
    document_title: str
    heading: Optional[str] = None
    content: str
    score: float = Field(description="相关性得分（0-1）")
    difficulty: str
    concepts: Optional[str] = None


class RAGRetrievalResponse(BaseModel):
    """检索响应。"""
    query: str
    results: list[RAGRetrievalResult]
    total_hits: int
    retrieval_time_ms: float
