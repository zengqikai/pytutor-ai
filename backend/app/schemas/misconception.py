"""
误区诊断相关 Schema
===================
"""

from pydantic import BaseModel, Field


class DiagnoseRequest(BaseModel):
    """误区诊断请求。

    `code` / `stderr` 都会进入规则匹配和 LLM 辅助判定，必须限长；
    未限长时一个请求就能把整套源码塞进来。
    """
    code: str = Field(default="", max_length=20_000, description="待诊断代码")
    stderr: str = Field(default="", max_length=5_000, description="执行报错信息")
    exercise_id: str = Field(default="", max_length=64, description="关联练习 ID")
