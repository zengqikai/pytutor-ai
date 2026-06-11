"""
DashScope Embedding 服务
========================

使用阿里云百炼 DashScope text-embedding API（OpenAI 兼容）替代本地
sentence-transformers 模型。

优势：
- 无需下载模型（HuggingFace 在国内不可达）
- 延迟低（~100ms/次），精度高（SOTA 中文向量）
- 零维护，按量付费（~¥0.0007/千token）

API 格式（OpenAI 兼容）:
    POST https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings
    {"model": "text-embedding-v3", "input": ["文本1", "文本2"]}

降级策略：如果 API 调用失败，embed_async 返回 None → 上层自动回退 TF-IDF。
"""

import asyncio
import os
from pathlib import Path
from typing import Optional

import httpx

from app.observability.logger import get_logger

logger = get_logger(__name__)

# 自动加载项目根目录的 .env（确保 DASHSCOPE_API_KEY 在任意启动方式下都可用）
try:
    from dotenv import load_dotenv
    _root_env = Path(__file__).resolve().parent.parent.parent.parent / ".env"
    if _root_env.exists():
        load_dotenv(_root_env, override=False)
except Exception:
    pass

# DashScope OpenAI 兼容端点
DASHSCOPE_BASE_URL = os.environ.get(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
)

# API Key：优先系统环境变量 > 根目录 .env（由 uvicorn 启动时加载）
DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")

# 默认 embedding 模型
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-v3")

# 单次 API 调用的最大文本数（DashScope text-embedding-v3 限制为 10）
MAX_BATCH_SIZE = 10

# 全局单例
_embedding_instance: Optional["DashScopeEmbedding"] = None


class EmbeddingError(RuntimeError):
    """Embedding API 调用失败异常。"""


class DashScopeEmbedding:
    """DashScope text-embedding API 封装。

    同时支持同步和异步调用，兼容 sentence-transformers 接口风格。
    """

    def __init__(
        self,
        api_key: str = DASHSCOPE_API_KEY,
        base_url: str = DASHSCOPE_BASE_URL,
        model: str = EMBEDDING_MODEL,
    ):
        if not api_key:
            raise EmbeddingError(
                "DASHSCOPE_API_KEY 未设置，请在 .env 中配置阿里云百炼 API Key"
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def encode(self, texts: list[str]) -> list[list[float]]:
        """同步编码多条文本。

        返回:
            list[list[float]]: 每条文本对应的向量（维度由模型决定）。
        """
        all_embeddings = []
        # 分批调用（API 有单次请求的文本数限制）
        for i in range(0, len(texts), MAX_BATCH_SIZE):
            batch = texts[i : i + MAX_BATCH_SIZE]
            chunk_embeddings = self._call_api(batch)
            all_embeddings.extend(chunk_embeddings)
        return all_embeddings

    async def encode_async(self, texts: list[str]) -> Optional[list[list[float]]]:
        """异步编码多条文本。

        失败时返回 None（上层自动降级到 TF-IDF）。

        返回:
            list[list[float]] | None
        """
        all_embeddings = []
        try:
            for i in range(0, len(texts), MAX_BATCH_SIZE):
                batch = texts[i : i + MAX_BATCH_SIZE]
                chunk_embeddings = await self._call_api_async(batch)
                all_embeddings.extend(chunk_embeddings)
            return all_embeddings
        except Exception as e:
            logger.warning(
                "embedding_api_failed",
                error=str(e)[:200],
                text_count=len(texts),
            )
            return None

    def _call_api(self, texts: list[str]) -> list[list[float]]:
        """同步 API 调用。"""
        import time

        t0 = time.perf_counter()
        try:
            response = httpx.post(
                f"{self.base_url}/embeddings",
                json={
                    "model": self.model,
                    "input": texts,
                },
                headers=self._headers(),
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            elapsed = (time.perf_counter() - t0) * 1000
            logger.info(
                "embedding_api_ok",
                model=self.model,
                batch_size=len(texts),
                duration_ms=round(elapsed, 1),
            )

            # 按 index 排序返回
            items = sorted(data["data"], key=lambda x: x["index"])
            return [item["embedding"] for item in items]

        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.error(
                "embedding_api_error",
                model=self.model,
                duration_ms=round(elapsed, 1),
                error=str(e)[:200],
            )
            raise EmbeddingError(f"Embedding API 调用失败: {e}") from e

    async def _call_api_async(self, texts: list[str]) -> list[list[float]]:
        """异步 API 调用。"""
        import time

        t0 = time.perf_counter()
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/embeddings",
                json={
                    "model": self.model,
                    "input": texts,
                },
                headers=self._headers(),
            )
            response.raise_for_status()
            data = response.json()

        elapsed = (time.perf_counter() - t0) * 1000
        logger.info(
            "embedding_api_ok",
            model=self.model,
            batch_size=len(texts),
            duration_ms=round(elapsed, 1),
        )

        items = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in items]


def get_embedding() -> Optional[DashScopeEmbedding]:
    """获取全局 embedding 单例。

    如果没有配置 API Key，返回 None（上层应降级到纯 TF-IDF）。
    """
    global _embedding_instance
    if _embedding_instance is None:
        try:
            _embedding_instance = DashScopeEmbedding()
            logger.info(
                "embedding_service_ready",
                model=_embedding_instance.model,
                provider="dashscope",
            )
        except EmbeddingError as e:
            logger.warning("embedding_service_unavailable", error=str(e))
            _embedding_instance = None  # type: ignore[assignment]
    return _embedding_instance


def is_embedding_available() -> bool:
    """检查 embedding 服务是否可用。"""
    instance = get_embedding()
    return instance is not None
