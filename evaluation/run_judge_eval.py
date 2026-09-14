"""
Multi-Judge 评分系统评估脚本 (C 方向 Task 1 + Task 2)
=======================================================

评估维度：
1. 评委间一致性 (Inter-Judge Agreement): Fleiss' Kappa
2. 单评委 vs 多评委对比：评分方差、revision 率
3. Task 2 专属: Rubric V2 方差 vs V1 基线方差对比
4. Task 2 专属: CANNOT_ASSESS 使用率分析
5. 评分分布分析：各维度 median/min/max/range/valid_count

用法:
    # 多评委模式 (使用 V2 Rubric)
    ENABLE_MULTI_JUDGE=true python evaluation/run_judge_eval.py

    # 单评委基线 (使用旧 Rubric)
    ENABLE_MULTI_JUDGE=false python evaluation/run_judge_eval.py

    # 指定测试文件
    python evaluation/run_judge_eval.py --cases evaluation/judge_test_cases.json

输出:
    - evaluation/judge_eval_results.json（详细结果）
    - 控制台打印汇总指标
"""

import asyncio
import json
import os
import sys
import time
from pathlib import Path

# 添加 backend 到路径
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))


# =============================================================================
# 默认测试用例：模拟不同质量的 AI 回复
# =============================================================================

DEFAULT_TEST_CASES = [
    # === 高质量回复 ===
    {
        "case_id": "J01",
        "ai_message": "你的代码思路是对的！不过在第 3 行，你有没有注意到 `list.append()` 这个方法有点特别？它直接修改原列表，但返回值不是你想的那样。试试把 `new = numbers.append(4)` 拆成两行：先 append，再 print(numbers)。看看结果有什么不同？",
        "expected_hint_level": 2,
        "misconception_id": "M3",
        "description": "方向提示 + 引导思考 (M3 append)，应得高分",
    },
    {
        "case_id": "J02",
        "ai_message": "你在 for 循环中用了 `range(1, 5)`，Python 的 range 函数有个约定：它包含左边界 1，但不包含右边界 5。可以这样理解：range(start, stop) 相当于「从 start 开始，到 stop 之前停止」。试试把 5 改成 6 看看？",
        "expected_hint_level": 2,
        "misconception_id": "M5",
        "description": "概念解释 + 方向提示 (M5 range)，应得高分",
    },
    {
        "case_id": "J03",
        "ai_message": "你的函数定义得很清晰！我注意到你在函数里用了 `print()` 来显示结果，这个没问题。但如果你想让这个结果在函数外面也能被使用，需要加一行 `return`。对比一下：`print(a+b)` 只是显示在屏幕上，`return a+b` 则把结果「交出去」给调用者。调试时你可以试试在调用处 `print(add(3,4))` 看有什么不同。",
        "expected_hint_level": 2,
        "misconception_id": "M6",
        "description": "概念对比 + 调试建议 (M6 print/return)，应得高分",
    },

    # === 中等质量回复 ===
    {
        "case_id": "J04",
        "ai_message": "你的代码有个问题。`if x = 3:` 这里应该用 `==` 而不是 `=`。在 Python 里，单个等号是赋值，双等号才是比较。改一下就好了。",
        "expected_hint_level": 1,
        "misconception_id": "M1",
        "description": "Level 1 直接给答案 (M1 赋值=比较)，应扣分",
    },
    {
        "case_id": "J05",
        "ai_message": "你的缩进不对。在 Python 中，for 循环后面的代码需要缩进 4 个空格。正确的写法是：\n```python\nfor i in range(3):\n    print(i)\n```\n这样 i 的值才会被依次打印。",
        "expected_hint_level": 2,
        "misconception_id": "M2",
        "description": "Level 2 给了完整代码 (M2 缩进)，应扣 D3 分",
    },
    {
        "case_id": "J06",
        "ai_message": "输入 `input()` 返回的是字符串，你需要用 `int()` 转换成数字才能做数学运算。改成 `x = int(input('num: '))`。",
        "expected_hint_level": 1,
        "misconception_id": "M7",
        "description": "Level 1 直接给解决方案，应扣 D1/D3 分",
    },

    # === 低质量回复 ===
    {
        "case_id": "J07",
        "ai_message": "你的代码有问题。去查一下 Python 的 while 循环文档。",
        "expected_hint_level": 2,
        "misconception_id": "M8",
        "description": "敷衍回复，应得低分",
    },
    {
        "case_id": "J08",
        "ai_message": "在 Python 中，`list.sort()` 方法会直接对列表进行排序，返回 None。你可以这样修改：\n```python\nlst = [1,2,3]\nlst.sort()  # 直接修改 lst\nprint(lst)  # [1, 2, 3]\n```\n这样就能看到排序后的结果了。记住，sort() 是就地排序，sorted() 返回新列表。",
        "expected_hint_level": 1,
        "misconception_id": "M3",
        "description": "Level 1 给了完整代码 + 概念解释（严重越级），应得很低分",
    },

    # === 边界情况 ===
    {
        "case_id": "J09",
        "ai_message": "你好！Python 的缩进很重要哦。记得在需要缩进的地方按 Tab 键或者空格键。",
        "expected_hint_level": 1,
        "misconception_id": "M2",
        "description": "泛泛而谈（M2 缩进），勉强合格",
    },
    {
        "case_id": "J10",
        "ai_message": "好的，我来帮你分析。你的 while 循环没有改变循环条件，所以条件永远为真，导致无限循环。你需要在循环体里加上对计数变量的修改。比如：\n```python\nn = 0\nwhile n < 5:\n    print(n)\n    n += 1  # 关键：每次循环 n 加 1\n```\n这样 n 最终会达到 5，条件变为假，循环就结束了。这个模式叫「循环计数器」，是编程中很常见的。",
        "expected_hint_level": 3,
        "misconception_id": "M8",
        "description": "Level 3 给了完整代码（稍有越级但解释详尽），中高分",
    },
]


# =============================================================================
# 评估主逻辑
# =============================================================================

def compute_kappa_between_runs(runs: list[dict]) -> dict:
    """对比多次跑同一个 case 的评分一致性。"""
    if not runs or len(runs) < 2:
        return {"kappa": None, "note": "需要至少 2 次跑分"}

    # 提取每次的 overall score
    scores_by_run = []
    for run in runs:
        scores_by_run.append(run.get("score", 3))

    # 方差
    import statistics
    variance = statistics.variance(scores_by_run) if len(scores_by_run) >= 2 else 0.0
    mean_score = statistics.mean(scores_by_run)

    return {
        "runs": len(runs),
        "scores": scores_by_run,
        "mean": round(mean_score, 2),
        "variance": round(variance, 4),
        "stable": variance < 0.5,
    }


async def run_evaluation(test_cases: list[dict]) -> dict:
    """跑完整评估。"""
    from app.services.pedagogy_service import verify_response

    use_multi = os.environ.get("ENABLE_MULTI_JUDGE", "false").lower() == "true"
    print(f"\n{'='*60}")
    print(f"Multi-Judge 评估模式: {'ON ✅' if use_multi else 'OFF (单评委基线)'}")
    print(f"测试用例数: {len(test_cases)}")
    print(f"{'='*60}\n")

    results = []
    kappas = []
    scores = []
    revision_count = 0

    start_total = time.perf_counter()

    for i, case in enumerate(test_cases):
        print(f"[{i+1}/{len(test_cases)}] {case['case_id']}: {case.get('description', '')[:60]}")

        start = time.perf_counter()
        try:
            result = await verify_response(
                case["ai_message"],
                case.get("expected_hint_level", 1),
                case.get("misconception_id"),
            )
        except Exception as e:
            result = {"is_valid": True, "score": 3, "issues": [str(e)], "needs_revision": False}

        elapsed = (time.perf_counter() - start) * 1000

        score = result.get("score", 3)
        scores.append(score)
        if result.get("needs_revision"):
            revision_count += 1

        case_result = {
            "case_id": case["case_id"],
            "description": case.get("description", ""),
            "score": score,
            "is_valid": result.get("is_valid", True),
            "needs_revision": result.get("needs_revision", False),
            "issues": result.get("issues", []),
            "latency_ms": round(elapsed, 0),
        }

        # Multi-Judge 特有的字段 (V2 增强)
        if use_multi:
            kappa = result.get("kappa", None)
            if kappa is not None:
                kappas.append(kappa)
            ca_dims = result.get("cannot_assess_dims", [])
            case_result.update({
                "judge_count": result.get("judge_count", 0),
                "kappa": kappa,
                "agreement": result.get("agreement", "N/A"),
                "flagged": result.get("flagged", False),
                "scores_detail": result.get("scores_detail", {}),
                "cannot_assess_dims": ca_dims,  # V2
            })
            status_parts = [f"score={score}"]
            if kappa is not None:
                status_parts.append(f"kappa={kappa:.3f}")
            status_parts.append(f"{result.get('agreement','')}")
            if result.get("flagged"):
                status_parts.append("FLAGGED")
            if ca_dims:
                status_parts.append(f"CA:{','.join(ca_dims)}")
            status = "  " + " ".join(status_parts)
        else:
            status = f"  score={score} revision={result.get('needs_revision', False)}"

        print(f"{status}  ({elapsed:.0f}ms)")

        results.append(case_result)

    total_elapsed = (time.perf_counter() - start_total) * 1000

    # 汇总统计
    import statistics
    mean_score = statistics.mean(scores) if scores else 0
    mean_kappa = statistics.mean(kappas) if kappas else None

    # V2: 维度级方差分析
    dim_variance: dict[str, float] = {}
    ca_usage = 0  # CANNOT_ASSESS 使用次数
    if use_multi:
        for dim in ["D1_hint_adherence", "D2_beginner_appropriate",
                     "D3_no_leakage", "D4_misconception_target", "D5_actionability"]:
            dim_ranges = []
            for r in results:
                detail = r.get("scores_detail", {}).get(dim, {})
                if detail:
                    dim_ranges.append(detail.get("range", 0))
            if dim_ranges:
                dim_variance[dim] = round(statistics.mean(dim_ranges), 2)
        ca_usage = sum(1 for r in results if r.get("cannot_assess_dims"))

    summary = {
        "total_cases": len(test_cases),
        "multi_judge_enabled": use_multi,
        "rubric_version": "V2" if use_multi else "V1",
        "mean_score": round(mean_score, 2),
        "score_std": round(statistics.stdev(scores), 2) if len(scores) >= 2 else 0,
        "score_range": f"{min(scores)}-{max(scores)}" if scores else "N/A",
        "revision_rate": f"{revision_count}/{len(test_cases)} ({revision_count/len(test_cases)*100:.0f}%)" if test_cases else "N/A",
        "mean_kappa": round(mean_kappa, 4) if mean_kappa is not None else None,
        "dim_mean_range": dim_variance,  # V2: 每维平均分歧度
        "cannot_assess_cases": f"{ca_usage}/{len(test_cases)}",  # V2: CANNOT_ASSESS 使用率
        "total_latency_ms": round(total_elapsed, 0),
        "avg_latency_ms": round(total_elapsed / len(test_cases), 0) if test_cases else 0,
    }

    output = {
        "summary": summary,
        "results": results,
    }

    # 写到文件
    output_path = Path(__file__).parent / "judge_eval_results.json"
    output_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 打印汇总
    print(f"\n{'='*60}")
    print("评估汇总")
    print(f"{'='*60}")
    print(f"模式:        {'Multi-Judge V2 (行为锚定 Rubric)' if use_multi else '单评委 V1 基线'}")
    print(f"平均分:      {summary['mean_score']} (sigma={summary['score_std']})")
    print(f"分数范围:    {summary['score_range']}")
    print(f"修正率:      {summary['revision_rate']}")
    if summary['mean_kappa'] is not None:
        kappa_str = f"{summary['mean_kappa']:.4f}"
        if summary['mean_kappa'] >= 0.75:
            kappa_str += " [strong]"
        elif summary['mean_kappa'] >= 0.60:
            kappa_str += " [substantial]"
        elif summary['mean_kappa'] >= 0.40:
            kappa_str += " [moderate]"
        else:
            kappa_str += " [low]"
        print(f"评委间 Kappa:{kappa_str}")
    if summary["dim_mean_range"]:
        print(f"维度分歧度:  {summary['dim_mean_range']}")
        avg_range = sum(summary['dim_mean_range'].values()) / len(summary['dim_mean_range'])
        print(f"平均维度分歧:{avg_range:.2f} (目标 < 0.5)")
    if use_multi:
        print(f"CA 使用率:   {summary['cannot_assess_cases']}")
    print(f"总耗时:      {summary['total_latency_ms']:.0f}ms ({summary['avg_latency_ms']:.0f}ms/case)")
    print(f"\n详细结果: {output_path}")
    print(f"{'='*60}\n")

    return output


# =============================================================================
# CLI 入口
# =============================================================================

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Multi-Judge 评分评估")
    parser.add_argument("--cases", type=str, default=None,
                        help="测试用例 JSON 文件路径 (默认使用内置 10 例)")
    args = parser.parse_args()

    if args.cases:
        cases_path = Path(args.cases)
        if not cases_path.exists():
            print(f"错误：文件不存在 {cases_path}")
            sys.exit(1)
        test_cases = json.loads(cases_path.read_text(encoding="utf-8"))
    else:
        test_cases = DEFAULT_TEST_CASES

    await run_evaluation(test_cases)


if __name__ == "__main__":
    asyncio.run(main())
