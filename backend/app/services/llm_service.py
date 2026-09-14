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

import re
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
    response_format: Optional[dict] = None,
) -> LLMResponse:
    """
    LiteLLM 统一调用接口。

    参数:
        messages: 对话消息
        model: 模型名（nil = 用配置默认）
        temperature: nil = 用配置
        max_tokens: nil = 用配置
        provider: 供应商（deepseek/qwen/openai）
        response_format: 结构化输出（如 {"type": "json_object"}），nil = 默认

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
                response_format=response_format,
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
                response_format=response_format,
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


# =============================================================================
# 多模型路由 (C 方向 Task 6)
# =============================================================================
# 文献依据：简单问题走 flash (便宜)、复杂问题走 pro (强推理)
# 目标: API 成本降低 ≥ 50%

# 复杂度关键词（命中任一视为复杂问题）
COMPLEX_KEYWORDS = [
    "为什么", "解释", "分析", "区别", "对比", "区别是什么",
    "原理", "底层", "机制", "源码", "算法",
    "递归", "装饰器", "闭包", "生成器", "迭代器",
    "面向对象", "继承", "多态", "元类", "描述符",
    "线程", "进程", "协程", "异步", "并发",
    "内存", "垃圾回收", "GIL", "性能", "优化",
    "帮我写", "实现一个", "设计", "架构",
]

# 简单关键词（命中视为简单问题，优先级高于复杂关键词）
SIMPLE_KEYWORDS = [
    "什么是", "怎么用", "示例", "例子", "语法",
    "print", "变量", "列表", "字符串", "字典",
    "if", "for", "while", "函数", "input",
]


def classify_question_complexity(user_message: str) -> dict:
    """
    基于关键词 + 长度启发式对问题复杂度分类。

    返回:
        {"level": "simple"|"complex", "reason": str, "routed_model": str}
    """
    msg_lower = user_message.lower().strip()
    msg_len = len(user_message)

    # 代码块检测（仅用可靠信号，避免 "def"→"define" / "import"→"important" 误判）
    has_code_block = "```" in user_message
    has_def = bool(re.search(r'\bdef\s+\w+\s*\(', user_message))   # "def foo("
    has_import = bool(re.search(r'(?:^|\n)\s*(?:from\s+\S+\s+)?import\s+\S+', user_message))
    has_code = has_code_block or has_def or has_import

    # 简单启发式规则
    simple_hits = [kw for kw in SIMPLE_KEYWORDS if kw in msg_lower]
    complex_hits = [kw for kw in COMPLEX_KEYWORDS if kw in msg_lower]

    # 判定逻辑
    if has_code and not complex_hits:
        # 有代码但无复杂问题 → simple
        level = "simple"
        reason = f"代码相关咨询（{len(user_message)}字符）"
    elif simple_hits and not complex_hits:
        level = "simple"
        reason = f"命中简单关键词: {simple_hits[:3]}"
    elif complex_hits:
        level = "complex"
        reason = f"命中复杂关键词: {complex_hits[:3]}"
    elif msg_len > 200:
        # 长文本 → 可能是复杂问题
        level = "complex"
        reason = f"长文本 ({msg_len} 字符)，可能是复杂问题"
    else:
        # 默认简单
        level = "simple"
        reason = f"短文本 ({msg_len} 字符)，默认简单路由"

    # 路由到的模型
    if level == "simple":
        routed_model = "deepseek-chat"  # 更便宜
    else:
        routed_model = "deepseek-v4-pro"  # 更强大

    return {"level": level, "reason": reason, "routed_model": routed_model}


async def chat_completion_routed(
    messages: list["ChatMessage"],
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> "LLMResponse":
    """
    多模型路由版 chat_completion (C 方向 Task 6)。

    根据消息复杂度自动选择模型:
    - simple → deepseek-chat (便宜 ~70% 成本)
    - complex → deepseek-v4-pro (强推理)

    目标成本降低 ≥ 50%（假设 70% 的请求是 simple）。
    """
    from app.core.config import settings

    # 提取最后一条用户消息用于分类
    user_msg = ""
    for m in reversed(messages):
        if m.role == "user":
            user_msg = m.content
            break

    classification = classify_question_complexity(user_msg)
    routed_model = classification["routed_model"]

    logger.info("model_routing",
                level=classification["level"],
                reason=classification["reason"],
                model=routed_model,
                msg_preview=user_msg[:80])

    # 调用实际 LLM
    return await chat_completion(
        messages=messages,
        model=routed_model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
