"""把各结果 JSON 汇总成 evaluation/results_summary.csv。

只读取已有结果文件，不重新跑实验；数字口径与 docs/REPRODUCIBILITY.md §6 一致。
运行：python evaluation/build_results_summary.py
"""

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EVAL = ROOT / "evaluation"
RESEARCH = ROOT / "research" / "faithfulness"
OUT = EVAL / "results_summary.csv"

FIELDS = ["experiment", "dataset", "condition", "metric", "n", "value", "caveat"]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    rows = []

    def add(experiment, dataset, condition, metric, n, value, caveat):
        rows.append(
            {
                "experiment": experiment,
                "dataset": dataset,
                "condition": condition,
                "metric": metric,
                "n": n,
                "value": value,
                "caveat": caveat,
            }
        )

    # 误区诊断
    ast = load(EVAL / "v2_eval_results.json")
    s = ast["summary"]
    same_set = "same-set validation; rules and cases were developed together"
    add("ast_diagnosis", "v2_test_cases", "ast-only", "exact_match", s["total_cases"], f"{s['exact_match']:.3f}", same_set)
    add("ast_diagnosis", "v2_test_cases", "ast-only", "macro_f1", s["total_cases"], f"{s['macro_f1']:.3f}", same_set)
    add("ast_diagnosis", "clean_code_cases", "ast-only", "false_positive_rate", 22, f"{s['false_positive_rate']:.3f}", same_set)
    latencies = [r["time_ms"] for r in ast["results"]]
    add("ast_diagnosis", "v2_test_cases", "ast-only", "mean_latency_ms", len(latencies), f"{sum(latencies)/len(latencies):.2f}", f"max {max(latencies):.2f} ms")

    # 误区诊断 · 留出集（新写、未据此调规则）
    holdout = load(EVAL / "v2_holdout_results.json")
    hs = holdout["summary"]
    holdout_caveat = "held-out set written separately; rules were not tuned on it; single author"
    add("ast_diagnosis_holdout", "v2_holdout_cases", "ast-only", "exact_match", hs["total_cases"], f"{hs['exact_match']:.3f}", holdout_caveat)
    add("ast_diagnosis_holdout", "v2_holdout_cases", "ast-only", "macro_f1", hs["total_cases"], f"{hs['macro_f1']:.3f}", holdout_caveat)
    add("ast_diagnosis_holdout", "holdout_clean_cases", "ast-only", "false_positive_rate", 15, f"{hs['false_positive_rate']:.3f}", holdout_caveat)
    h_lat = [r["time_ms"] for r in holdout["results"]]
    add("ast_diagnosis_holdout", "v2_holdout_cases", "ast-only", "mean_latency_ms", len(h_lat), f"{sum(h_lat)/len(h_lat):.2f}", f"max {max(h_lat):.2f} ms")
    for mid in ("M5", "M6"):
        pc = holdout["per_class"][mid]
        add("ast_diagnosis_holdout", "v2_holdout_cases", mid, "recall", pc["tp"] + pc["fn"], f"{pc['recall']:.3f}", f"{pc['tp']}/{pc['tp'] + pc['fn']}; main residual gap")

    # RAG 检索
    for mode in ("tfidf", "vector", "hybrid"):
        rag = load(EVAL / f"rag_eval_results_{mode}.json")
        top5 = rag["summary"]["top5"]
        n = top5["evaluated"]
        caveat = f"{n} answerable queries; smoke baseline"
        if mode == "hybrid":
            caveat += "; identical to vector while ENABLE_HYBRID_WEIGHTS is off"
        for metric in ("hit_at_k", "recall_at_k", "mrr"):
            add("rag_retrieval", "rag_golden", mode, f"{metric}@5", n, f"{top5[metric]:.3f}", caveat)
        add("rag_retrieval", "rag_golden", mode, "mean_latency_ms", n, f"{top5['mean_latency_ms']:.1f}", caveat)
        add("rag_retrieval", "rag_golden", mode, "mean_context_tokens", n,
            f"{top5['mean_context_tokens']:.1f}",
            f"{caveat}; estimated by splitter.estimate_tokens, max {top5['max_context_tokens']}")
        na = rag["no_answer_check"]
        add("rag_retrieval", "rag_golden_no_answer", mode, "returned_any", na["total"], f"{na['returned_any']}/{na['total']}", "retriever cannot abstain")
        add("rag_retrieval", "rag_golden_no_answer", mode, "mean_top_score", na["total"], f"{na['mean_top_score']:.3f}", "score is not calibrated")

    # Multi-Judge
    judge = load(EVAL / "judge_eval_results.json")["summary"]
    jc = "no human reference; kappa is inter-judge only"
    add("multi_judge", "judge_eval", "3 judges", "mean_score", judge["total_cases"], f"{judge['mean_score']:.2f}", jc)
    add("multi_judge", "judge_eval", "3 judges", "revision_rate", judge["total_cases"], f"{judge['revision_rate']}", jc)
    add("multi_judge", "judge_eval", "3 judges", "mean_kappa", judge["total_cases"], f"{judge['mean_kappa']:.3f}", jc)

    # 忠实度：v2（rules_v2 抽取器）为主结果，v1 只作历史对照，不进汇总
    v2_runs = sorted(RESEARCH.glob("results_real_deepseek_v2_run*.json"))
    for run, path in enumerate(v2_runs, start=1):
        d = load(path)
        n = d["meta"]["n_items"]
        for cond in ("C1", "C2"):
            add(
                "faithfulness",
                "dataset_seed",
                f"{cond} (run{run})",
                "faithfulness_overall",
                d["summary"][cond]["n_scored"],
                f"{d['summary'][cond]['faithfulness_overall']:.3f}",
                "10 seed items; rules_v2 extractor; C2 not better on either run",
            )
        diff = d["summary"]["paired_diff_C2_minus_C1"]
        add(
            "faithfulness",
            "dataset_seed",
            f"C2-C1 (run{run})",
            "paired_mean_diff",
            diff["n_pairs"],
            f"{diff['mean']:.3f}",
            f"95% CI [{diff['ci95'][0]:.2f}, {diff['ci95'][1]:.2f}]; crosses zero",
        )

    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {OUT.relative_to(ROOT)} ({len(rows)} rows)")


if __name__ == "__main__":
    main()
