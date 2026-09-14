"""
RAG 检索评测脚本（A 方向：Recall@K / MRR）
========================================

对 RAG 检索质量做离线评测（不依赖向量 API / LLM）：

- Recall@K：Top-K 检索结果中命中至少一个相关 chunk 的查询占比（K=3,5）
- MRR：第一个相关 chunk 排名的倒数平均（Mean Reciprocal Rank）

相关 chunk 判定：chunk 的 concepts 与查询的 expected_concepts 有交集。

用法:
    # TF-IDF 基线（默认，离线、确定性）
    python evaluation/run_rag_eval.py

    # 混合检索（需 DASHSCOPE_API_KEY）
    ENABLE_HYBRID_WEIGHTS=true python evaluation/run_rag_eval.py --hybrid

输出:
    - evaluation/rag_eval_results.json
    - 控制台打印汇总
"""

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select

from app.database.session import AsyncSessionFactory
from app.models.rag import RAGChunk, RAGDocument
from app.rag.retriever import retriever


def load_golden() -> list[dict]:
    path = Path(__file__).parent / "rag_golden.json"
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def concepts_overlap(chunk_concepts: str, expected: list[str]) -> bool:
    """chunk 的 concepts（逗号分隔）与预期知识点是否有交集。"""
    if not expected or not chunk_concepts:
        return False
    chunk_set = {c.strip() for c in chunk_concepts.split(",") if c.strip()}
    return bool(chunk_set & set(expected))


async def load_chunks(db) -> list[dict]:
    """从 DB 加载所有 chunk（含 concepts / document_title），并重建 TF-IDF 索引。"""
    result = await db.execute(
        select(RAGChunk, RAGDocument)
        .join(RAGDocument, RAGChunk.document_id == RAGDocument.id)
        .where(RAGDocument.is_active == True)
    )
    rows = result.all()

    retriever.clear()
    chunks = []
    for chunk, doc in rows:
        chunks.append({
            "chunk_id": chunk.id,
            "content": chunk.content,
            "heading": chunk.heading,
            "concepts": chunk.concepts or "",
            "document_title": doc.title,
        })
        retriever.add_chunk(
            chunk_id=chunk.id,
            content=chunk.content,
            heading=chunk.heading,
            concepts=chunk.concepts,
            difficulty=chunk.difficulty,
            document_title=doc.title,
            tokens=chunk.tokens or "",
        )
    return chunks


def compute_metrics(cases: list[dict], chunks: list[dict], top_k: int) -> dict:
    """对每个查询检索 top_k，计算 Recall@K 和 MRR。"""
    hits = 0
    reciprocal_ranks = []
    total = 0
    details = []

    for case in cases:
        expected = case.get("expected_concepts", [])
        relevant_ids = {
            c["chunk_id"] for c in chunks
            if concepts_overlap(c["concepts"], expected)
        }
        if not relevant_ids:
            # 无相关 chunk 的查询（如 g007 prompt injection）跳过
            continue
        total += 1

        results = retriever.search(query=case["query"], top_k=top_k)
        retrieved_ids = [r["chunk_id"] for r in results]

        first_rank = None
        for i, cid in enumerate(retrieved_ids, 1):
            if cid in relevant_ids:
                first_rank = i
                break

        is_hit = first_rank is not None
        if is_hit:
            hits += 1
            reciprocal_ranks.append(1.0 / first_rank)
        else:
            reciprocal_ranks.append(0.0)

        details.append({
            "id": case["id"],
            "query": case["query"],
            "relevant_chunks": len(relevant_ids),
            "hit": is_hit,
            "first_rank": first_rank,
            "top_chunk_heading": results[0]["heading"] if results else None,
        })

    recall = hits / total if total else 0.0
    mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
    return {"recall": recall, "mrr": mrr, "total": total, "hits": hits, "details": details}


async def run_async(hybrid: bool = False):
    golden = load_golden()
    print(f"=== RAG Evaluation ({'hybrid' if hybrid else 'TF-IDF'} mode) ===\n")
    print(f"Golden queries: {len(golden)}")

    async with AsyncSessionFactory() as db:
        chunks = await load_chunks(db)
        print(f"Corpus chunks: {len(chunks)}")

    # 若 hybrid 模式，需要走 retrieve_context（含向量 + 权重融合）
    # 这里保持 TF-IDF 基线为主；hybrid 通过 flag 在 retrieve_context 内部生效。
    # 为离线可复现，本脚本默认只评测 TF-IDF 检索器。
    results = {}
    for k in (3, 5):
        m = compute_metrics(golden, chunks, top_k=k)
        results[f"top{k}"] = {
            "recall": round(m["recall"], 3),
            "mrr": round(m["mrr"], 3),
            "hits": m["hits"],
            "total": m["total"],
        }
        print(f"Recall@{k} = {m['recall']:.1%}  ({m['hits']}/{m['total']})")
        print(f"MRR@{k}    = {m['mrr']:.3f}")

    # 打印 miss 详情
    missed = [d for d in compute_metrics(golden, chunks, top_k=5)["details"] if not d["hit"]]
    if missed:
        print(f"\n--- Missed queries ---")
        for d in missed:
            print(f"  {d['id']}: {d['query'][:40]} (top heading: {d['top_chunk_heading']})")

    # 保存结果
    out = {
        "mode": "hybrid" if hybrid else "tfidf",
        "summary": results,
        "details": compute_metrics(golden, chunks, top_k=5)["details"],
    }
    path = Path(__file__).parent / "rag_eval_results.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved to: {path}")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--hybrid", action="store_true", help="标记为混合检索模式（预留）")
    args = parser.parse_args()
    asyncio.run(run_async(hybrid=args.hybrid))


if __name__ == "__main__":
    main()
