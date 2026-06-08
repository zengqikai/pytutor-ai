"""
代码相关 Schemas
================
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_serializer


class CodeSubmitRequest(BaseModel):
    """代码提交请求。"""
    code: str = Field(..., min_length=1, max_length=50000, description="Python 代码")
    exercise_id: str | None = Field(default=None, description="关联的练习 ID")
    session_id: str | None = Field(default=None, description="关联的聊天会话 ID")


class ExecutionResultResponse(BaseModel):
    """执行结果响应。"""
    submission_id: str
    status: str = Field(description="completed | timeout | memory_exceeded | blocked | error")
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    runtime_ms: float | None = None
    memory_kb: int | None = None
    timeout_triggered: bool = False
    created_at: datetime

    @field_serializer("created_at")
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat()

    model_config = {"from_attributes": True}


class CodeSubmitResponse(BaseModel):
    """代码提交响应。"""
    submission_id: str
    status: str
    result: ExecutionResultResponse | None = None
    message: str = ""
