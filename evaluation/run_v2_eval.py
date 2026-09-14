"""
PyTutor 3.0 AST Baseline 评估脚本
===================================

对误区诊断进行评测：
- Exact Match（精确匹配率）
- Per-class Precision / Recall / F1（每类 M1-M8）
- Macro Average F1
- False Positive Rate（干净代码误报率，需 clean_code_cases.json）

支持两种模式：
- direct: 直接导入 diagnose()（无需启动服务器）
- http:   调用 HTTP API（需先启动 uvicorn）

用法:
    # 直接模式（推荐，无需服务器）
    ENABLE_AST_DIAGNOSIS=true python evaluation/run_v2_eval.py --mode direct
    ENABLE_AST_DIAGNOSIS=false python evaluation/run_v2_eval.py --mode direct

    # HTTP 模式（需要先启动服务器）
    python evaluation/run_v2_eval.py --mode http

输出:
    - evaluation/v2_eval_results.json（详细结果）
    - 控制台打印汇总指标
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# 添加 backend 到 sys.path（direct 模式需要）
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

M1_TO_M8 = [f"M{i}" for i in range(1, 9)]

MC_NAMES = {
    "M1": "赋值与比较混淆", "M2": "缩进理解错误", "M3": "append返回值误解",
    "M4": "index/value混淆", "M5": "range右边界误解", "M6": "print/return混淆",
    "M7": "类型转换错误", "M8": "while循环条件错误",
}


# =============================================================================
# 工具函数
# =============================================================================

def load_json_cases(filename: str) -> list[dict]:
    path = Path(__file__).parent / filename
    return json.loads(path.read_text(encoding="utf-8"))


def classify_prediction(predicted: str | None) -> str:
    """将预测值归一化为 M1-M8 或 None。"""
    if predicted and predicted in M1_TO_M8:
        return predicted
    return None


# =============================================================================
# Per-class 指标计算
# =============================================================================

def compute_per_class_metrics(results: list[dict]) -> dict:
    """
    对 M1-M8 每类计算 Precision / Recall / F1。

    results 每个元素：
        {"case_id": str, "expected": str, "predicted": str | None, "accurate": bool}
    """
    metrics = {}
    for mc in M1_TO_M8:
        tp = sum(1 for r in results if r["predicted"] == mc and r["expected"] == mc)
        fp = sum(1 for r in results if r["predicted"] == mc and r["expected"] != mc)
        fn = sum(1 for r in results if r["predicted"] != mc and r["expected"] == mc)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        metrics[mc] = {
            "name": MC_NAMES.get(mc, mc),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "tp": tp, "fp": fp, "fn": fn,
        }
    return metrics


def compute_macro_f1(per_class: dict) -> float:
    f1s = [per_class[mc]["f1"] for mc in M1_TO_M8]
    return round(sum(f1s) / len(f1s), 3)


def compute_false_positive_rate(clean_results: list[dict]) -> dict:
    """
    计算误报率。

    clean_results 每个元素：
        {"case_id": str, "predicted": str | None}

    误报率 = 被误诊的干净代码数 / 总干净代码数
    """
    total = len(clean_results)
    if total == 0:
        return {"total": 0, "false_positives": 0, "fpr": 0.0}
    fp = sum(1 for r in clean_results if r["predicted"] is not None)
    return {
        "total": total,
        "false_positives": fp,
        "fpr": round(fp / total, 3),
        "fp_details": [r for r in clean_results if r["predicted"] is not None],
    }


# =============================================================================
# Direct 模式：直接导入 diagnose()
# =============================================================================

async def run_direct_eval():
    """直接调用 diagnose()，无需启动 HTTP 服务器。"""
    print("=== PyTutor 3.0 AST Evaluation (Direct Mode) ===\n")
    print(f"ENABLE_AST_DIAGNOSIS = {os.environ.get('ENABLE_AST_DIAGNOSIS', 'false')}\n")

    # 延迟导入，确保环境变量先被设置
    from app.database.session import AsyncSessionFactory
    from app.services.misconception_service import diagnose

    # 加载测试用例
    cases = load_json_cases("v2_test_cases.json")
    print(f"Misconception test cases: {len(cases)}")

    # 诊断每个案例
    mc_results = []
    async with AsyncSessionFactory() as db:
        for i, case in enumerate(cases):
            predicted = None
            error = None
            start = time.perf_counter()
            try:
                result = await diagnose(
                    db,
                    code=case["code"],
                    stderr=case.get("stderr", ""),
                    exercise_context=case.get("student_question", ""),
                )
                predicted = classify_prediction(result.get("misconception_id"))
                diag_method = result.get("diagnosis_method", "unknown")
            except Exception as e:
                error = str(e)[:100]
                diag_method = "error"
            elapsed = (time.perf_counter() - start) * 1000

            expected = case.get("expected_misconception")
            accurate = predicted == expected
            mc_results.append({
                "case_id": case["case_id"],
                "expected": expected,
                "predicted": predicted,
                "accurate": accurate,
                "diagnosis_method": diag_method,
                "time_ms": round(elapsed, 2),
                "error": error,
            })

            status = "PASS" if accurate else (f"MISS (got {predicted}, expected {expected})")
            print(f"  [{i+1:2d}/{len(cases)}] {case['case_id']} {status}  [{diag_method}]")

    # 计算 Per-class 指标
    valid = [r for r in mc_results if r["error"] is None]
    per_class = compute_per_class_metrics(valid)
    macro_f1 = compute_macro_f1(per_class)
    exact_match = sum(1 for r in valid if r["accurate"]) / len(valid) if valid else 0

    print(f"\n--- Per-class Metrics ---")
    print(f"{'ID':<6} {'Name':<24} {'Precision':<10} {'Recall':<10} {'F1':<10} {'TP':<4} {'FP':<4} {'FN':<4}")
    print(f"{'-'*72}")
    for mc in M1_TO_M8:
        m = per_class[mc]
        print(f"{mc:<6} {m['name']:<24} {m['precision']:<10.3f} {m['recall']:<10.3f} {m['f1']:<10.3f} {m['tp']:<4} {m['fp']:<4} {m['fn']:<4}")
    print(f"{'-'*72}")
    print(f"{'Macro Avg F1':>62} = {macro_f1:.3f}")
    print(f"Exact Match Rate: {exact_match:.1%}")

    # ---- 误报率评测（干净代码） ----
    clean_cases_path = Path(__file__).parent / "clean_code_cases.json"
    clean_results = []
    if clean_cases_path.exists():
        clean_cases = load_json_cases("clean_code_cases.json")
        print(f"\nClean code cases: {len(clean_cases)}")
        async with AsyncSessionFactory() as db:
            for case in clean_cases:
                predicted = None
                try:
                    result = await diagnose(
                        db,
                        code=case["code"],
                        stderr="",
                        exercise_context="",
                    )
                    predicted = classify_prediction(result.get("misconception_id"))
                except Exception:
                    pass
                clean_results.append({
                    "case_id": case["case_id"],
                    "description": case.get("description", ""),
                    "predicted": predicted,
                })
                if predicted:
                    print(f"  FP {case['case_id']}: False positive -> {predicted}")
                else:
                    print(f"  OK {case['case_id']}: OK")

    fpr = compute_false_positive_rate(clean_results)
    print(f"\nFalse Positive Rate: {fpr['fpr']:.1%} ({fpr['false_positives']}/{fpr['total']})")

    # 保存结果
    output = {
        "config": {"ENABLE_AST_DIAGNOSIS": os.environ.get("ENABLE_AST_DIAGNOSIS", "false")},
        "summary": {
            "total_cases": len(cases),
            "valid_results": len(valid),
            "exact_match": round(exact_match, 3),
            "macro_f1": macro_f1,
            "false_positive_rate": fpr["fpr"],
        },
        "per_class": per_class,
        "false_positive_details": fpr.get("fp_details", []),
        "results": mc_results,
    }
    output_path = Path(__file__).parent / "v2_eval_results.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved to: {output_path}")


# =============================================================================
# HTTP 模式（需要启动服务器）
# =============================================================================

async def run_http_eval():
    import httpx

    BASE = "http://localhost:8000/api/v1"

    async def get_token():
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{BASE}/auth/login",
                json={"email": "tt@t.com", "password": "test12345"})
            return r.json()["access_token"]

    print("=== PyTutor 3.0 AST Evaluation (HTTP Mode) ===\n")

    cases = load_json_cases("v2_test_cases.json")
    print(f"Cases: {len(cases)}")

    token = await get_token()
    results = []

    async with httpx.AsyncClient(timeout=30) as client:
        h = {"Authorization": f"Bearer {token}"}
        for i, case in enumerate(cases):
            predicted = None
            error = None
            start = time.perf_counter()
            try:
                r = await client.post(f"{BASE}/misconceptions/diagnose",
                    json={"code": case["code"], "stderr": case.get("stderr", "")}, headers=h)
                data = r.json()
                predicted = classify_prediction(data.get("misconception_id"))
            except Exception as e:
                error = str(e)[:100]
            elapsed = (time.perf_counter() - start) * 1000

            expected = case.get("expected_misconception")
            accurate = predicted == expected
            results.append({
                "case_id": case["case_id"],
                "expected": expected,
                "predicted": predicted,
                "accurate": accurate,
                "time_ms": round(elapsed, 2),
                "error": error,
            })
            status = "✓" if accurate else f"✗ (got {predicted})"
            print(f"  [{i+1:2d}/{len(cases)}] {case['case_id']} {status}")

    valid = [r for r in results if r["error"] is None]
    per_class = compute_per_class_metrics(valid)
    macro_f1 = compute_macro_f1(per_class)
    exact_match = sum(1 for r in valid if r["accurate"]) / len(valid) if valid else 0

    print(f"\nMacro Avg F1: {macro_f1:.3f}")
    print(f"Exact Match:  {exact_match:.1%}")

    output_path = Path(__file__).parent / "v2_eval_results.json"
    output_path.write_text(json.dumps({
        "summary": {"total": len(cases), "exact_match": exact_match, "macro_f1": macro_f1},
        "per_class": per_class,
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved to: {output_path}")


# =============================================================================
# AST-Only 模式（无需数据库、无需 LLM、无需后端服务）
# =============================================================================

def run_ast_only_eval():
    """
    纯 AST 分析器评测。不依赖数据库 / LLM / 后端服务。

    直接调用 analyze_misconceptions() → 提取 misconception_id。
    不经过 diagnose() 的 LLM fallback。
    """
    from app.analysis.ast_analyzer import analyze_misconceptions

    print("=== PyTutor AST-Only Evaluation ===\n")

    # 加载测试用例
    cases = load_json_cases("v2_test_cases.json")
    print(f"Misconception test cases: {len(cases)}")

    mc_results = []
    for i, case in enumerate(cases):
        predicted = None
        start = time.perf_counter()
        try:
            findings = analyze_misconceptions(
                code=case["code"],
                stderr=case.get("stderr", ""),
                student_question=case.get("student_question", ""),
            )
            # 取置信度最高的命中
            if findings:
                predicted = classify_prediction(findings[0].get("misconception_id"))
        except Exception as e:
            pass
        elapsed = (time.perf_counter() - start) * 1000

        expected = case.get("expected_misconception")
        accurate = predicted == expected
        mc_results.append({
            "case_id": case["case_id"],
            "expected": expected,
            "predicted": predicted,
            "accurate": accurate,
            "time_ms": round(elapsed, 2),
        })

        status = "PASS" if accurate else (f"MISS (got {predicted}, expected {expected})")
        print(f"  [{i+1:2d}/{len(cases)}] {case['case_id']} {status}")

    # Per-class 指标
    per_class = compute_per_class_metrics(mc_results)
    macro_f1 = compute_macro_f1(per_class)
    exact_match = sum(1 for r in mc_results if r["accurate"]) / len(mc_results) if mc_results else 0

    print(f"\n--- Per-class Metrics ---")
    print(f"{'ID':<6} {'Name':<24} {'Precision':<10} {'Recall':<10} {'F1':<10} {'TP':<4} {'FP':<4} {'FN':<4}")
    print(f"{'-'*72}")
    for mc in M1_TO_M8:
        m = per_class[mc]
        print(f"{mc:<6} {m['name']:<24} {m['precision']:<10.3f} {m['recall']:<10.3f} {m['f1']:<10.3f} {m['tp']:<4} {m['fp']:<4} {m['fn']:<4}")
    print(f"{'-'*72}")
    print(f"{'Macro Avg F1':>62} = {macro_f1:.3f}")
    print(f"Exact Match Rate: {exact_match:.1%}")

    # 误报率
    clean_cases_path = Path(__file__).parent / "clean_code_cases.json"
    clean_results = []
    if clean_cases_path.exists():
        clean_cases = load_json_cases("clean_code_cases.json")
        print(f"\nClean code cases: {len(clean_cases)}")
        for case in clean_cases:
            predicted = None
            try:
                findings = analyze_misconceptions(code=case["code"], stderr="", student_question="")
                if findings:
                    predicted = classify_prediction(findings[0].get("misconception_id"))
            except Exception:
                pass
            clean_results.append({
                "case_id": case["case_id"],
                "description": case.get("description", ""),
                "predicted": predicted,
            })
            if predicted:
                print(f"  FP {case['case_id']}: False positive -> {predicted}")
            else:
                print(f"  OK {case['case_id']}: OK")

    fpr = compute_false_positive_rate(clean_results)
    print(f"\nFalse Positive Rate: {fpr['fpr']:.1%} ({fpr['false_positives']}/{fpr['total']})")

    # 未通过样例
    missed = [r for r in mc_results if not r["accurate"]]
    if missed:
        print(f"\n--- Missed Cases ({len(missed)}) ---")
        for m in missed:
            print(f"  {m['case_id']}: expected {m['expected']}, got {m['predicted']}")

    # 保存
    output = {
        "mode": "ast-only",
        "summary": {
            "total_cases": len(cases),
            "exact_match": round(exact_match, 3),
            "macro_f1": macro_f1,
            "false_positive_rate": fpr["fpr"],
            "misconception_cases": f"{sum(1 for r in mc_results if r['accurate'])}/{len(cases)}",
            "clean_code_fp": f"{fpr['false_positives']}/{fpr['total']}",
        },
        "per_class": per_class,
        "false_positive_details": fpr.get("fp_details", []),
        "results": mc_results,
    }
    output_path = Path(__file__).parent / "v2_eval_results.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved to: {output_path}")


# =============================================================================
# 主入口
# =============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="PyTutor Misconception Evaluation")
    parser.add_argument("--mode", choices=["direct", "http", "ast-only"], default="direct",
                        help="direct: import diagnose() directly; http: call API; ast-only: AST analysis only (no DB/LLM)")
    args = parser.parse_args()

    if args.mode == "http":
        asyncio.run(run_http_eval())
    elif args.mode == "ast-only":
        run_ast_only_eval()
    else:
        asyncio.run(run_direct_eval())


if __name__ == "__main__":
    main()
