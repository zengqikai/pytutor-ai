"""
LLM 服务层 (LiteLLM Gateway)
=============================

通过 LiteLLM 统一网关调用所有 LLM：
- 多供应商切换（DeepSeek/OpenAI/Qwen/Claude 一个接口）
- 自动 fallback + 重试
- Token 消耗追踪
- 成本估算

升级前：裸调 OpenAI SDK → DeepSeek
升级后：LiteLLM 网关 → 任意供应商，一行配置切换
"""

import time
from typing import Optional

try:
    import litellm
    from litellm import acompletion, completion_cost
    HAS_LITELLM = True
except ImportError:
    litellm = None  # type: ignore
    acompletion = None  # type: ignore
    completion_cost = None  # type: ignore
    HAS_LITELLM = False

from app.core.config import settings
from app.core.exceptions import LLMException
from app.observability.logger import get_logger
from app.schemas.ai import ChatMessage, LLMRequest, LLMResponse, TokenUsage

logger = get_logger(__name__)

# LiteLLM 全局配置
if HAS_LITELLM:
    litellm.drop_params = True
    litellm.telemetry = False
    litellm.set_verbose = settings.debug

# 供应商路由配置
LLM_ROUTER = {
    "deepseek": {
        "model": f"deepseek/{settings.deepseek_model}",
        "api_key": settings.deepseek_api_key,
        "api_base": settings.deepseek_base_url,
    },
    # 后续扩展：
    # "qwen": {
    #     "model": "dashscope/qwen-plus",
    #     "api_key": settings.qwen_api_key,
    # },
    # "openai": {
    #     "model": "openai/gpt-4o-mini",
    #     "api_key": settings.openai_api_key,
    # },
}

# 默认供应商
DEFAULT_PROVIDER = "deepseek"


async def chat_completion(
    messages: list[ChatMessage],
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    provider: str = DEFAULT_PROVIDER,
) -> LLMResponse:
    """
    LiteLLM 统一调用接口。

    参数:
        messages: 对话消息
        model: 模型名（nil = 用配置默认）
        temperature: nil = 用配置
        max_tokens: nil = 用配置
        provider: 供应商（deepseek/qwen/openai）

    返回:
        LLMResponse
    """
    temp = temperature if temperature is not None else settings.llm_temperature
    max_tok = max_tokens or settings.llm_max_tokens

    # 获取供应商配置
    provider_cfg = LLM_ROUTER.get(provider, LLM_ROUTER[DEFAULT_PROVIDER])
    litellm_model = model or provider_cfg["model"]

    api_messages = [{"role": m.role, "content": m.content} for m in messages]
    start_time = time.perf_counter()

    try:
        if not HAS_LITELLM:
            # Fallback: 直接使用 OpenAI SDK (DeepSeek 兼容)
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=provider_cfg.get("api_key", settings.deepseek_api_key),
                base_url=provider_cfg.get("api_base", settings.deepseek_base_url),
                timeout=settings.llm_timeout,
            )
            response = await client.chat.completions.create(
                model=litellm_model.replace("deepseek/", ""),
                messages=api_messages,
                temperature=temp,
                max_tokens=max_tok,
            )
        else:
            response = await acompletion(
                model=litellm_model,
                messages=api_messages,
                temperature=temp,
                max_tokens=max_tok,
                api_key=provider_cfg.get("api_key"),
                api_base=provider_cfg.get("api_base"),
                timeout=settings.llm_timeout,
                num_retries=1,
                fallbacks=[settings.deepseek_fallback_model] if settings.deepseek_fallback_model else None,
            )
    except Exception as e:
        logger.error("llm_call_failed", provider=provider, model=litellm_model, error=str(e))
        raise LLMException(detail="AI 服务暂时不可用", internal_detail=str(e))

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    # 提取响应
    choice = response.choices[0]
    content = choice.message.content or ""

    # Token 用量
    usage = TokenUsage(
        prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
        completion_tokens=response.usage.completion_tokens if response.usage else 0,
        total_tokens=response.usage.total_tokens if response.usage else 0,
    )

    # 成本估算
    try:
        cost = completion_cost(completion_response=response)
    except Exception:
        cost = 0.0

    logger.info(
        "llm_call_completed",
        provider=provider,
        model=litellm_model,
        duration_ms=round(elapsed_ms, 2),
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        cost_usd=round(cost, 6),
        finish_reason=choice.finish_reason,
        content_preview=content[:100].encode("ascii", errors="replace").decode("ascii"),
    )

    return LLMResponse(
        content=content,
        model=litellm_model,
        usage=usage,
        finish_reason=choice.finish_reason,
    )
