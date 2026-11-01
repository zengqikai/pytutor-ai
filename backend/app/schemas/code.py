"""
代码相关 Schemas
================
"""

from datetime import datetime

from pydantic import BaseModel, Field, field_serializer


class CodeSubmitRequest(BaseModel):
    """代码提交请求。"""
    code: str = Field(..., min_length=1, max_length=50000, description="Python 代码")
    exercise_id: str | None = Field(default=None, description="关联的练习 ID")
    session_id: str | None = Field(default=None, description="关联的聊天会话 ID")
    stdin: str = Field(default="", description="标准输入数据（模拟 input()）")


class AnalyzeErrorRequest(BaseModel):
    """独立错误分析请求。

    限长是必需的：分析结果会拼进 LLM prompt，未限长时可被塞进整本文件
    （也会绕过沙箱直接让服务端着 LLM 生成一次）。
    """
    code: str = Field(default="", max_length=50_000, description="学生代码")
    stderr: str = Field(default="", max_length=10_000, description="执行 stderr")


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


class ErrorAnalysis(BaseModel):
    """错误分析。"""
    explanation: str = ""
    concepts: list[str] = []

class CodeSubmitResponse(BaseModel):
    """代码提交响应。"""
    submission_id: str
    status: str
    result: ExecutionResultResponse | None = None
    message: str = ""
    error_analysis: ErrorAnalysis | None = None
