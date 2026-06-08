"""
重排序器
=======

对检索结果进行二次排序，选出最相关的上下文。

为什么需要重排序？
    初次检索（TF-IDF/向量）速度快但准确度有限。
    重排序用更强的模型（LLM）对 Top-K 结果做精细判断，
    最终只将最相关的 Top-N 传给生成阶段。

LLM 重排序原理：
    把"查询 + 候选文档"一起发给 LLM，问它"这个文档与查询的相关度多少？"
    LLM 可以理解语义、判断真实相关性，比纯关键词匹配准确。
"""

import json

from app.observability.logger import get_logger
from app.schemas.ai import ChatMessage as LLMMessage
from app.services.llm_service import chat_completion

logger = get_logger(__name__)

# 重排序 Prompt
RERANK_PROMPT = """你是一个搜索结果相关性评估助手。请评估以下文档片段与查询的相关性。

查询：{query}

文档片段：
{documents}

请对每个文档打分（0-10），并选出最相关的 {top_n} 个。
只返回 JSON 数组，不要其他内容。格式：
[
  {{"index": 0, "score": 8, "reason": "直接回答了查询问题"}},
  {{"index": 2, "score": 5, "reason": "部分相关但不是核心答案"}}
]

注意：
- 相关性 = 文档内容是否直接回答了查询问题
- 部分匹配但非直接答案 → 中低分
- 完全不相关 → 0 分
- 只返回 JSON，不要其他说明文字"""


async def rerank_with_llm(
    query: str,
    candidates: list[dict],
    top_n: int = 3,
) -> list[dict]:
    """
    使用 LLM 对检索候选进行重排序。

    参数:
        query: 原始查询
        candidates: 候选列表 [{chunk_id, content, score, ...}, ...]
        top_n: 最终返回的最相关结果数

    返回:
        list[dict]: 重排序后的结果（含 LLM 评分）
    """
    if len(candidates) <= top_n:
        return candidates

    # 构建文档列表字符串
    doc_texts = []
    for i, doc in enumerate(candidates):
        doc_texts.append(
            f"[{i}] 标题: {doc.get('heading', 'N/A')}\n"
            f"    内容: {doc['content'][:300]}..."  # 只取前 300 字符
        )

    documents_str = "\n\n".join(doc_texts)
    prompt = RERANK_PROMPT.format(
        query=query,
        documents=documents_str,
        top_n=top_n,
    )

    try:
        llm_response = await chat_completion(
            messages=[LLMMessage(role="user", content=prompt)],
            temperature=0.0,  # 评估任务需要确定性
            max_tokens=500,
        )

        # 解析 LLM 返回的 JSON
        content = llm_response.content.strip()
        # 移除可能的代码块标记
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if content.endswith("```"):
                content = content[:-3]

        rankings = json.loads(content)

        # 按得分排序
        rankings.sort(key=lambda x: x.get("score", 0), reverse=True)

        # 重组结果
        reranked = []
        for r in rankings[:top_n]:
            idx = r["index"]
            if 0 <= idx < len(candidates):
                candidate = candidates[idx].copy()
                candidate["rerank_score"] = r.get("score", 0)
                candidate["rerank_reason"] = r.get("reason", "")
                reranked.append(candidate)

        logger.info(
            "rerank_completed",
            candidates_in=len(candidates),
            results_out=len(reranked),
        )

        return reranked if reranked else candidates[:top_n]

    except Exception as e:
        logger.warning("rerank_failed", error=str(e))
        # 重排序失败时回退到原始排序
        return candidates[:top_n]
