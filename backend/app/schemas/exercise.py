"""练习相关 Schema。"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_serializer


class ExerciseGenerateRequest(BaseModel):
    """AI 生成练习请求。"""
    concepts: str | None = Field(default=None, description="指定知识点（逗号分隔），不指定则自动选择")
    difficulty: int = Field(default=2, ge=1, le=5, description="难度 1-5")
    count: int = Field(default=1, ge=1, le=3, description="生成数量")


class ExercisePublishRequest(BaseModel):
    """发布/取消发布练习。"""
    is_published: bool = Field(..., description="true=发布，false=下架")


class SubmitExerciseRequest(BaseModel):
    """提交答案请求。

    只接受代码本身。提示次数和"是否看过答案"由服务端 LearningEvent 统计，
    前端传来的 used_hints / viewed_solution 一律忽略（Pydantic 默认丢弃额外字段）。
    """
    code: str = Field(..., min_length=1, max_length=20_000, description="学生的 Python 代码")


class ExerciseHintRequest(BaseModel):
    """分层提示请求。"""
    hint_level: int = Field(default=1, ge=1, le=5, description="提示等级 1-5")
    code: str = Field(default="", max_length=20_000, description="当前代码（可选）")
    failed_info: str = Field(default="", max_length=4_000, description="失败信息（可选）")


class TestCaseSchema(BaseModel):
    """测试用例。"""
    input_data: str | None = None
    expected_output: str
    is_hidden: bool = True
    description: str | None = None


class ExerciseResponse(BaseModel):
    """练习响应（含公开信息，不暴露参考答案和隐藏用例）。"""
    id: str
    title: str
    description: str
    difficulty: int
    concepts: Optional[str] = None
    learning_objective: Optional[str] = None
    example_input: Optional[str] = None
    example_output: Optional[str] = None
    source: str
    pass_rate: Optional[float] = None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_datetime(self, dt: datetime) -> str:
        return dt.isoformat()

    model_config = {"from_attributes": True}


class ExerciseDetailResponse(ExerciseResponse):
    """练习详情（教师可见参考答案和测试用例）。"""
    reference_solution: Optional[str] = None
    test_cases: list[TestCaseSchema] = []
