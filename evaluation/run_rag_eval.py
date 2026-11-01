"""
RAG 检索评测脚本（A 方向）
=========================

三种检索路径**分别调用各自实现**，不再靠一个字符串标签区分：

    tfidf   —— app.rag.retriever（关键词，离线、确定性）
    vector  —— app.rag.vector_store.search_async（DashScope embedding + ChromaDB）
    hybrid  —— app.services.rag_service.retrieve_context（向量 + TF-IDF 融合，
               受 ENABLE_HYBRID_WEIGHTS 等开关控制）

指标定义（三者必须分开报告，不能混用）：

    Hit@K      Top-K 里至少命中一个相关 chunk 的查询比例        （粗粒度）
    Recall@K   Top-K 命中的相关 chunk 数 / 全部相关 chunk 数    （细粒度）
    MRR        第一个相关 chunk 排名的倒数平均值

相关 chunk 判定：chunk.concepts 与查询 expected_concepts 有交集。

用法:
    cd backend
    python ../evaluation/run_rag_eval.py                 # TF-IDF 基线
    python ../evaluation/run_rag_eval.py --mode vector   # 向量（需 DASHSCOPE_API_KEY）
    python ../evaluation/run_rag_eval.py --mode hybrid   # 混合（需 DASHSCOPE_API_KEY）

输出:
    - evaluation/rag_eval_results.json（含全部查询明细、跳过原因、语料覆盖率）
"""

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from sqlalchemy import select

from app.database.session import AsyncSessionFactory
from app.models.rag import RAGChunk, RAGDocument
from app.rag.retriever import retriever

GOLDEN_PATH = Path(__file__).parent / "rag_golden.json"
RESULTS_DIR = Path(__file__).parent
TOP_KS = (3, 5)


def out_path_for(mode: str) -> Path:
    """每种模式单独存一份，否则后跑的会覆盖先跑的，三种基线没法并列比较。"""
    return RESULTS_DIR / f"rag_eval_results_{mode}.json"


def load_golden() -> list[dict]:
    data = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    # 兼容 {"cases": [...]} 与直接数组两种格式
    return data["cases"] if isinstance(data, dict) else data


def concepts_overlap(chunk_concepts: str, expected: list[str]) -> bool:
    if not expected or not chunk_concepts:
        return False
    chunk_set = {c.strip() for c in chunk_concepts.split(",") if c.strip()}
    return bool(chunk_set & set(expected))


async def load_chunks(db) -> list[dict]:
    """从 DB 加载所有 chunk，并重建 TF-IDF 索引。"""
    result = await db.execute(
        select(RAGChunk, RAGDocument)
        .join(RAGDocument, RAGChunk.document_id == RAGDocument.id)
        .where(RAGDocument.is_active == True)  # noqa: E712
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


# =============================================================================
# 三种检索器：每种真正调用自己的实现
# =============================================================================

def make_tfidf_searcher():
    async def search(query: str, top_k: int) -> list[dict]:
        return retriever.search(query=query, top_k=top_k)
    return search


def make_vector_searcher():
    from app.rag.vector_store import is_model_available, search_async

    if not is_model_available():
        raise RuntimeError(
            "向量检索不可用：需要 DASHSCOPE_API_KEY 且 ChromaDB 中已有数据。"
            "请先运行 rebuild_index() 或换 --mode tfidf。"
        )

    async def search(query: str, top_k: int) -> list[dict]:
        return await search_async(query=query, top_k=top_k)
    return search


def make_hybrid_searcher(db):
    from app.schemas.rag import RAGRetrievalRequest
    from app.services.rag_service import retrieve_context

    async def search(query: str, top_k: int) -> list[dict]:
        resp = await retrieve_context(db, RAGRetrievalRequest(query=query, top_k=top_k))
        out = []
        for r in resp.results:
            # RAGRetrievalResult 对象或 dict 都要能处理
            cid = getattr(r, "chunk_id", None) or (r.get("chunk_id") if isinstance(r, dict) else None)
            heading = getattr(r, "heading", None) or (r.get("heading") if isinstance(r, dict) else None)
            score = getattr(r, "score", None)
            if score is None and isinstance(r, dict):
                score = r.get("score")
            out.append({"chunk_id": cid, "heading": heading, "score": score})
        return out
    return search


# =============================================================================
# 指标
# =============================================================================

async def check_no_answer_cases(cases: list[dict], searcher, top_k: int) -> dict:
    """
    无答案查询单独检查：理想情况下检索仍可能返回内容（检索器没有"拒答"能力），
    这里记录它返回了什么、最高分多少，供上层判断是否需要阈值。

    不计入 Hit@K / Recall@K / MRR。
    """
    if not cases:
        return {"total": 0, "returned_any": 0, "mean_top_score": None, "details": []}

    details = []
    top_scores = []
    returned_any = 0
    for case in cases:
        results = await searcher(case["query"], top_k)
        if results:
            returned_any += 1
        score = results[0].get("score") if results else None
        if isinstance(score, (int, float)):
            top_scores.append(float(score))
        details.append({
            "id": case["id"],
            "query": case["query"],
            "returned": len(results),
            "top_chunk_id": results[0].get("chunk_id") if results else None,
            "top_heading": results[0].get("heading") if results else None,
            "top_score": score,
        })

    return {
        "total": len(cases),
        "returned_any": returned_any,
        "mean_top_score": round(sum(top_scores) / len(top_scores), 3) if top_scores else None,
        "details": details,
    }


async def compute_metrics(cases: list[dict], chunks: list[dict],
                          searcher, top_k: int) -> dict:
    from app.rag.splitter import estimate_tokens

    chunk_by_id = {str(c["chunk_id"]): c for c in chunks}
    hit_count = 0
    recall_sum = 0.0
    reciprocal_ranks: list[float] = []
    evaluated = 0
    skipped: list[dict] = []
    details: list[dict] = []
    latencies: list[float] = []
    context_tokens: list[int] = []

    for case in cases:
        if case.get("no_answer_case"):
            # 无答案查询不进 Hit/Recall/MRR，单独在 no_answer_check 里看
            continue
        expected = case.get("expected_concepts", [])
        relevant_ids = {
            c["chunk_id"] for c in chunks if concepts_overlap(c["concepts"], expected)
        }
        if not relevant_ids:
            # 不静默跳过：语料里找不到相关 chunk 说明标注或语料覆盖有问题
            skipped.append({
                "id": case["id"],
                "query": case["query"],
                "reason": "no_relevant_chunk_in_corpus",
                "expected_concepts": expected,
            })
            continue
        evaluated += 1

        started = time.perf_counter()
        results = await searcher(case["query"], top_k)
        latencies.append((time.perf_counter() - started) * 1000)

        retrieved_ids = [r.get("chunk_id") for r in results]
        found = [cid for cid in retrieved_ids if cid in relevant_ids]

        # 上下文预算：Top-K 各 chunk 的估算 token 之和（估算口径见 splitter.estimate_tokens）
        context_tokens.append(sum(
            estimate_tokens(chunk_by_id[str(cid)]["content"])
            for cid in retrieved_ids if str(cid) in chunk_by_id
        ))

        first_rank = next(
            (i for i, cid in enumerate(retrieved_ids, 1) if cid in relevant_ids), None
        )
        is_hit = first_rank is not None
        if is_hit:
            hit_count += 1
        reciprocal_ranks.append(1.0 / first_rank if first_rank else 0.0)
        recall_sum += len(set(found)) / len(relevant_ids)

        details.append({
            "id": case["id"],
            "query": case["query"],
            "relevant_chunks": len(relevant_ids),
            "found_in_topk": len(set(found)),
            "hit": is_hit,
            "first_rank": first_rank,
            "top_chunk_heading": results[0].get("heading") if results else None,
            "no_answer_case": bool(case.get("no_answer")),
        })

    n = evaluated
    return {
        "evaluated": n,
        "skipped": len(skipped),
        "hit_at_k": round(hit_count / n, 3) if n else None,
        "recall_at_k": round(recall_sum / n, 3) if n else None,
        "mrr": round(sum(reciprocal_ranks) / len(reciprocal_ranks), 3) if reciprocal_ranks else None,
        "mean_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "mean_context_tokens": round(sum(context_tokens) / len(context_tokens), 1) if context_tokens else None,
        "max_context_tokens": max(context_tokens) if context_tokens else None,
        "total_context_tokens": sum(context_tokens) if context_tokens else None,
        "details": details,
        "skipped_details": skipped,
    }


async def run_async(mode: str = "tfidf"):
    golden = load_golden()
    print(f"=== RAG Evaluation | mode = {mode} ===\n")
    print(f"Golden queries: {len(golden)}")

    async with AsyncSessionFactory() as db:
        chunks = await load_chunks(db)

        if not chunks:
            print("\n错误：语料库为空（rag_chunks 无数据）。")
            print("请先导入知识库或运行 rebuild_index() 后再评测。")
            sys.exit(2)
        print(f"Corpus chunks: {len(chunks)}")

        if mode == "tfidf":
            searcher = make_tfidf_searcher()
        elif mode == "vector":
            try:
                searcher = make_vector_searcher()
            except RuntimeError as e:
                print(f"\n错误：{e}")
                sys.exit(2)
        elif mode == "hybrid":
            searcher = make_hybrid_searcher(db)
        else:
            print(f"错误：未知模式 {mode}")
            sys.exit(2)

        no_answer_cases = [c for c in golden if c.get("no_answer_case")]
        no_answer_check = await check_no_answer_cases(no_answer_cases, searcher, max(TOP_KS))
        if no_answer_cases:
            print(f"\n无答案查询：{no_answer_check['returned_any']}/{no_answer_check['total']} 条仍返回了内容"
                  f"（最高分均值 {no_answer_check['mean_top_score']}）")

        summary = {}
        details_by_k = {}
        for k in TOP_KS:
            m = await compute_metrics(golden, chunks, searcher, top_k=k)
            summary[f"top{k}"] = {
                key: m[key] for key in
                ("evaluated", "skipped", "hit_at_k", "recall_at_k", "mrr", "mean_latency_ms",
                 "mean_context_tokens", "max_context_tokens", "total_context_tokens")
            }
            details_by_k[f"top{k}"] = {
                "details": m["details"],
                "skipped_details": m["skipped_details"],
            }
            hit = "N/A" if m["hit_at_k"] is None else f"{m['hit_at_k']:.1%}"
            rec = "N/A" if m["recall_at_k"] is None else f"{m['recall_at_k']:.1%}"
            mrr = "N/A" if m["mrr"] is None else f"{m['mrr']:.3f}"
            print(f"Hit@{k}    = {hit}  ({m['evaluated']} 条已评测, {m['skipped']} 条跳过)")
            print(f"Recall@{k} = {rec}   MRR = {mrr}   平均延迟 {m['mean_latency_ms']} ms"
                  f"   上下文 token 均值 {m['mean_context_tokens']}（最大 {m['max_context_tokens']}）")

    # 分母只算"有答案"的查询；无答案查询本来就不该有相关 chunk，
    # 把它们算进来会让覆盖率看起来无缘无故变低。
    answerable = [c for c in golden if not c.get("no_answer_case")]
    coverage = summary["top5"]["evaluated"] / len(answerable) if answerable else 0.0
    print(f"\n语料覆盖率：{coverage:.0%}"
          f"（{summary['top5']['evaluated']}/{len(answerable)} 条有答案查询在语料中有相关 chunk）")

    missed = [d for d in details_by_k["top5"]["details"] if not d["hit"]]
    if missed:
        print("\n--- Missed queries ---")
        for d in missed:
            print(f"  {d['id']}: {d['query'][:40]} (top heading: {d['top_chunk_heading']})")

    out = {
        "mode": mode,
        "metric_definitions": {
            "hit_at_k": "Top-K 至少命中一个相关 chunk 的查询比例",
            "recall_at_k": "Top-K 命中的相关 chunk 数 / 全部相关 chunk 数的平均",
            "mrr": "第一个相关 chunk 排名的倒数平均",
            "mean_context_tokens": "Top-K 各 chunk 的估算 token 之和的平均（splitter.estimate_tokens，CJK 按 1 字 1 token、其余 4 字符 1 token；非分词器精确值）",
        },
        "golden_queries": len(golden),
        "corpus_chunks": len(chunks),
        "corpus_coverage": round(coverage, 3),
        "no_answer_check": no_answer_check,
        "summary": summary,
        "details": details_by_k,
    }
    out_path = out_path_for(mode)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved to: {out_path}")
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["tfidf", "vector", "hybrid"], default="tfidf")
    parser.add_argument("--hybrid", action="store_true",
                        help="兼容旧参数，等价于 --mode hybrid")
    args = parser.parse_args()
    asyncio.run(run_async(mode="hybrid" if args.hybrid else args.mode))


if __name__ == "__main__":
    main()
