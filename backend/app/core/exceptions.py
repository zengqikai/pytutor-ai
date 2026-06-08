"""
自定义异常类
===========

定义项目中使用的业务异常。

为什么需要自定义异常？
1. 区分"系统异常"（数据库连接失败、网络超时）和"业务异常"（用户不存在、权限不足）
2. 在全局异常处理器中可以对不同类型做不同处理
3. 让错误信息对用户友好，同时保留调试信息
"""


class AppException(Exception):
    """
    应用基础异常。

    所有业务异常都继承这个类。
    包含 HTTP 状态码，方便全局异常处理器统一返回。

    属性:
        status_code: HTTP 状态码
        detail: 用户可见的错误描述
        internal_detail: 内部调试信息（不暴露给前端）
    """

    def __init__(
        self,
        status_code: int = 500,
        detail: str = "服务器内部错误",
        internal_detail: str | None = None,
    ):
        self.status_code = status_code
        self.detail = detail
        self.internal_detail = internal_detail
        super().__init__(detail)


class LLMException(AppException):
    """
    LLM 调用异常。

    当 DeepSeek API 调用失败时抛出。
    可能原因：API Key 无效、网络超时、模型不可用、限流等。
    """

    def __init__(self, detail: str = "AI 服务暂时不可用", internal_detail: str | None = None):
        super().__init__(
            status_code=503,  # Service Unavailable
            detail=detail,
            internal_detail=internal_detail,
        )


class NotFoundException(AppException):
    """资源不存在异常。"""

    def __init__(self, detail: str = "请求的资源不存在"):
        super().__init__(status_code=404, detail=detail)


class ForbiddenException(AppException):
    """权限不足异常。"""

    def __init__(self, detail: str = "权限不足"):
        super().__init__(status_code=403, detail=detail)


class UnauthorizedException(AppException):
    """未认证异常。"""

    def __init__(self, detail: str = "请先登录"):
        super().__init__(status_code=401, detail=detail)


class ValidationException(AppException):
    """数据校验异常。"""

    def __init__(self, detail: str = "数据格式不正确"):
        super().__init__(status_code=422, detail=detail)
