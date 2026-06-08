"""
AI 相关 Schemas
===============

定义 AI 请求和响应的数据结构。

为后续 LangGraph Agent 和结构化输出做准备。
目前主要用于 LLM 服务封装。
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    """
    聊天消息。

    对应 OpenAI Chat Completion API 的 message 格式。
    """
    role: str = Field(..., description="角色：system | user | assistant")
    content: str = Field(..., description="消息内容")


class LLMRequest(BaseModel):
    """
    LLM 调用请求。

    封装了调用 LLM 所需的核心参数。
    后续 Agent 工作流会使用这个结构。
    """
    messages: list[ChatMessage] = Field(..., description="对话消息列表")
    model: Optional[str] = Field(default=None, description="模型名称，默认使用配置中的模型")
    temperature: Optional[float] = Field(default=None, ge=0, le=2, description="生成温度")
    max_tokens: Optional[int] = Field(default=None, ge=1, description="最大输出 token 数")


class TokenUsage(BaseModel):
    """Token 用量统计。"""
    prompt_tokens: int = Field(default=0, description="输入 token 数")
    completion_tokens: int = Field(default=0, description="输出 token 数")
    total_tokens: int = Field(default=0, description="总 token 数")


class LLMResponse(BaseModel):
    """
    LLM 调用响应。

    统一封装 LLM 的返回内容、Token 用量和模型信息。
    """
    content: str = Field(..., description="LLM 返回的文本内容")
    model: str = Field(..., description="实际使用的模型名称")
    usage: TokenUsage = Field(default_factory=TokenUsage, description="Token 用量")
    finish_reason: Optional[str] = Field(default=None, description="结束原因：stop | length | content_filter")
