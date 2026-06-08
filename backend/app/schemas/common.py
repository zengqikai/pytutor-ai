"""
统一响应格式
============

定义整个 API 的统一响应结构。

为什么需要统一格式？
- 前端只需要处理一种响应结构，不用为每个接口单独判断
- 错误信息有固定的位置，方便统一显示
- 所有响应都遵循 { "data": ..., "message": ..., "error": ... } 的三段式结构

用法:
    # 成功响应
    return ResponseModel(data=user, message="注册成功")

    # 错误响应
    return ResponseModel(data=None, message="邮箱已被注册", error={"code": "EMAIL_EXISTS"})
"""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """统一 API 响应模型。

    属性:
        data:    实际返回的数据（可以是任何类型）
        message: 人类可读的消息（成功时是 "success"，失败时描述原因）
        error:   错误详情（仅在出错时存在）
    """

    data: Optional[T] = Field(default=None, description="响应数据")
    message: str = Field(default="success", description="响应消息")
    error: Optional[dict[str, Any]] = Field(default=None, description="错误详情")

    model_config = {"from_attributes": True}


class PaginationParams(BaseModel):
    """分页参数。

    用法:
        @router.get("/items")
        async def list_items(pagination: PaginationParams = Depends()):
            offset = (pagination.page - 1) * pagination.page_size
            return query.offset(offset).limit(pagination.page_size)
    """
    page: int = Field(default=1, ge=1, description="页码（从 1 开始）")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量（最大 100）")
