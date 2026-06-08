"""
LLM 服务模块
===========

封装 DeepSeek API 调用。DeepSeek 兼容 OpenAI API 格式，
所以可以直接使用 OpenAI Python SDK。

核心概念：
---------
Temperature（温度）：控制输出的随机性。
    0.0 → 非常确定（适合代码生成、数学计算）
    1.0 → 平衡
    2.0 → 非常随机（适合创意写作）

Token：LLM 处理文本的基本单位。
    - 1 个中文字 ≈ 1-2 个 token
    - 1 个英文单词 ≈ 1-3 个 token
    - 输入 token + 输出 token = 总费用

Fallback Model（备用模型）：
    当主模型不可用时自动切换到备用模型，提高系统可用性。
"""

import time
from typing import Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.core.config import settings
from app.core.exceptions import LLMException
from app.observability.logger import get_logger
from app.schemas.ai import ChatMessage, LLMRequest, LLMResponse, TokenUsage

logger = get_logger(__name__)

# =============================================================================
# 创建 AsyncOpenAI 客户端
# =============================================================================
# AsyncOpenAI 是 openai 库的异步客户端。
# base_url 指向 DeepSeek 的 API 地址。
# api_key 从配置中读取（DeepSeek 的 API Key）。
# =============================================================================
client = AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
    timeout=settings.llm_timeout,
)


# =============================================================================
# LLM 调用
# =============================================================================

async def chat_completion(
    messages: list[ChatMessage],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> LLMResponse:
    """
    调用 LLM 进行对话补全。

    参数:
        messages: 对话消息列表（含 system prompt + 用户历史）
        model: 使用的模型（默认用配置中的 deepseek_model）
        temperature: 温度参数（默认用配置中的 llm_temperature）
        max_tokens: 最大 token（默认用配置中的 llm_max_tokens）

    返回:
        LLMResponse: 含回复内容、token 用量、使用模型

    异常:
        LLMException: 当所有模型（含 fallback）都调用失败时抛出

    用法:
        response = await chat_completion(
            messages=[
                ChatMessage(role="system", content="你是一个 Python 导师"),
                ChatMessage(role="user", content="什么是 for 循环？"),
            ],
        )
        print(response.content)  # LLM 的回复
        print(response.usage.total_tokens)  # 消耗的 token 数
    """
    # 确定使用的模型和参数
    selected_model = model or settings.deepseek_model
    selected_temperature = temperature if temperature is not None else settings.llm_temperature
    selected_max_tokens = max_tokens or settings.llm_max_tokens

    # 转换消息格式（Pydantic schema → OpenAI SDK 格式）
    api_messages: list[ChatCompletionMessageParam] = [
        {"role": msg.role, "content": msg.content}
        for msg in messages
    ]

    # 尝试调用主模型
    try:
        return await _call_llm(
            model=selected_model,
            messages=api_messages,
            temperature=selected_temperature,
            max_tokens=selected_max_tokens,
        )
    except Exception as primary_error:
        logger.warning(
            "llm_primary_model_failed",
            model=selected_model,
            error=str(primary_error),
        )

        # 如果有备用模型，尝试切换
        if settings.deepseek_fallback_model:
            logger.info(
                "llm_fallback_attempt",
                fallback_model=settings.deepseek_fallback_model,
            )
            try:
                return await _call_llm(
                    model=settings.deepseek_fallback_model,
                    messages=api_messages,
                    temperature=selected_temperature,
                    max_tokens=selected_max_tokens,
                )
            except Exception as fallback_error:
                logger.error(
                    "llm_fallback_model_failed",
                    fallback_model=settings.deepseek_fallback_model,
                    error=str(fallback_error),
                )
                raise LLMException(
                    detail="AI 服务暂时不可用，请稍后重试",
                    internal_detail=f"主模型 {selected_model} 和备用模型均调用失败",
                ) from fallback_error
        else:
            raise LLMException(
                detail="AI 服务暂时不可用，请稍后重试",
                internal_detail=str(primary_error),
            ) from primary_error


async def _call_llm(
    model: str,
    messages: list[ChatCompletionMessageParam],
    temperature: float,
    max_tokens: int,
) -> LLMResponse:
    """
    实际执行 LLM API 调用。

    这个函数被 chat_completion 内部使用，不直接对外暴露。
    分离出来是为了复用（主模型和 fallback 模型共用）。
    """
    start_time = time.perf_counter()

    # 调用 OpenAI 兼容的 Chat Completion API
    completion = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # 提取响应内容
    choice = completion.choices[0]
    content = choice.message.content or ""

    # 提取 token 用量
    usage = TokenUsage(
        prompt_tokens=completion.usage.prompt_tokens if completion.usage else 0,
        completion_tokens=completion.usage.completion_tokens if completion.usage else 0,
        total_tokens=completion.usage.total_tokens if completion.usage else 0,
    )

    # 记录 AI 调用日志（可观测性）
    # 清理 content_preview：移除 emoji 和不可打印字符，避免 Windows GBK 编码问题
    safe_preview = content[:100].encode("ascii", errors="replace").decode("ascii")
    logger.info(
        "llm_call_completed",
        model=model,
        duration_ms=round(elapsed_ms, 2),
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        finish_reason=choice.finish_reason,
        content_preview=safe_preview,
    )

    return LLMResponse(
        content=content,
        model=model,
        usage=usage,
        finish_reason=choice.finish_reason,
    )
