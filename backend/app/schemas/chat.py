"""
聊天相关 Schemas
================

定义聊天 API 的请求和响应数据结构。

结构化 AI 响应的核心设计：
    每个 AI 回复都包含 type + message + hint_level + concepts + next_action，
    前端根据这些字段渲染不同的 UI（如概念卡片、提示等级徽章、推荐按钮）。
"""

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_serializer, field_validator


# =============================================================================
# 请求 Schema
# =============================================================================

class CreateSessionRequest(BaseModel):
    """创建会话请求。"""
    title: str = Field(
        default="新的对话",
        min_length=1,
        max_length=255,
        description="会话标题",
    )


class SendMessageRequest(BaseModel):
    """
    发送消息请求。

    content 可以是纯文本，也可以是包含代码块的文本。
    如果 content 中包含 ```python ... ``` 代码块，AI 会自动识别为代码调试请求。
    """
    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="消息内容（纯文本或含代码块）",
    )
    model: str | None = Field(default=None, description="模型选择：默认 deepseek-chat，可选 deepseek-v4-pro")


# =============================================================================
# 响应 Schema
# =============================================================================

class AIResponse(BaseModel):
    """
    AI 结构化响应。

    这是 AI 导师回复的核心数据结构。每个 AI 回复都遵循这个结构，
    前端可以根据 response_type 和 hint_level 渲染不同的 UI。

    示例（概念解释）：
    {
        "response_type": "concept_explanation",
        "message": "for 循环用于重复执行一段代码...",
        "hint_level": 1,
        "related_concepts": ["for_loop", "range", "iteration"],
        "next_action": "try_exercise",
        "code_blocks": [{"language": "python", "code": "for i in range(5):\n    print(i)"}],
        "suggested_exercise_id": null
    }
    """
    response_type: str = Field(
        ...,
        description="回复类型：concept_explanation | code_feedback | hint | exercise | general"
    )
    message: str = Field(..., description="AI 回复的主要内容（Markdown 格式）")
    hint_level: int = Field(
        default=1,
        ge=1,
        le=5,
        description="提示等级 1-5（1=概念提示，5=完整答案）"
    )
    related_concepts: list[str] = Field(
        default_factory=list,
        description="关联的知识点列表"
    )
    next_action: str = Field(
        default="ask_question",
        description="建议下一步：try_exercise | read_concept | ask_question | try_again"
    )
    code_blocks: list[dict[str, str]] = Field(
        default_factory=list,
        description="代码块列表 [{'language': 'python', 'code': '...'}]"
    )
    suggested_exercise_id: Optional[str] = Field(
        default=None,
        description="推荐的练习题 ID（如有）"
    )
    # 2.0 新增字段
    misconception_id: Optional[str] = Field(
        default=None,
        description="诊断出的误区 ID（M1-M8）"
    )
    pedagogical_strategy: Optional[str] = Field(
        default=None,
        description="教学策略：progressive_hint | concept_explanation | ..."
    )
    reflection_question: Optional[str] = Field(
        default=None,
        description="引导学生反思的问题"
    )


class MessageResponse(BaseModel):
    """
    消息响应。

    将数据库中的 ChatMessage 转为 API 返回格式。
    对 assistant 消息会尝试解析 content 中的 JSON 获得结构化字段。
    """
    id: str
    session_id: str
    role: str
    content: str
    response_type: Optional[str] = None
    hint_level: Optional[int] = None
    related_concepts: Optional[list[str]] = None
    next_action: Optional[str] = None
    code_blocks: Optional[list[dict[str, str]]] = None
    token_count: Optional[int] = None
    created_at: datetime

    @field_validator("related_concepts", mode="before")
    @classmethod
    def parse_related_concepts(cls, v: Any) -> Optional[list[str]]:
        """兼容数据库中的逗号分隔字符串和 JSON 列表两种格式。"""
        if v is None:
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            if v.startswith("["):
                # JSON 格式: ["a", "b"]
                return json.loads(v)
            # 逗号分隔: "a,b,c"
            return [item.strip() for item in v.split(",") if item.strip()]
        return None

    @field_serializer("created_at")
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat()

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    """会话响应（含消息列表）。"""
    id: str
    title: str
    is_active: bool
    messages: list[MessageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat()

    model_config = {"from_attributes": True}


class SessionListItem(BaseModel):
    """会话列表项（不含消息内容，轻量）。"""
    id: str
    title: str
    is_active: bool
    message_count: int = Field(default=0, description="消息数量")
    last_message_preview: Optional[str] = Field(default=None, description="最后一条消息的预览")
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat()

    model_config = {"from_attributes": True}
