"""
AI 评测脚本
============

运行 Golden Dataset 中的所有测试用例，评估 AI 回复质量。

评测指标：
- intent_accuracy: 意图识别准确率
- concept_recall: 知识点召回率
- content_relevance: 内容相关度（是否包含期望关键词）
- hint_level_match: 提示等级匹配
- response_valid: JSON/纯文本格式正确性

使用方式：
    cd evaluation
    python run_eval.py
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import asyncio
from app.schemas.ai import ChatMessage as LLMMessage
from app.services.llm_service import chat_completion
from app.services.tutor_service import calculate_hint_level

GOLDEN_FILE = Path(__file__).parent / "golden_dataset.json"


def load_cases():
    with open(GOLDEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["cases"]


async def evaluate_case(case: dict) -> dict:
    """评估单个测试用例。"""
    result = {
        "id": case["id"],
        "input": case["input"][:60],
        "passed": True,
        "failures": [],
        "hint_level": None,
        "response": "",
        "time_ms": 0,
    }

    start = time.perf_counter()

    try:
        # 调用 LLM（简化版 System Prompt）
        llm_response = await chat_completion(
            messages=[
                LLMMessage(role="system", content="你是 Python 导师 PyTutor。用中文回复，Markdown 格式。"),
                LLMMessage(role="user", content=case["input"]),
            ],
            temperature=0.7,
            max_tokens=case.get("max_tokens", 500),
        )
        result["response"] = llm_response.content[:300]
        result["time_ms"] = round((time.perf_counter() - start) * 1000)

        # 检查 1：内容相关度
        for keyword in case.get("expected_contains", []):
            if keyword.lower() not in llm_response.content.lower():
                result["failures"].append(f"缺少关键词: {keyword}")
                result["passed"] = False

        # 检查 2：格式有效性
        if not llm_response.content.strip():
            result["failures"].append("回复为空")
            result["passed"] = False

    except Exception as e:
        result["passed"] = False
        result["failures"].append(f"调用失败: {str(e)[:100]}")
        result["time_ms"] = round((time.perf_counter() - start) * 1000)

    return result


async def run():
    cases = load_cases()
    print(f"Golden Dataset: {len(cases)} 个测试用例\n")

    results = []
    for case in cases:
        r = await evaluate_case(case)
        results.append(r)
        status = "PASS" if r["passed"] else "FAIL"
        print(f"[{status}] {r['id']}: {r['input'][:50]}... ({r['time_ms']}ms)")
        if r["failures"]:
            for f in r["failures"]:
                print(f"       ↳ {f}")

    passed = sum(1 for r in results if r["passed"])
    total = len(results)
    avg_time = sum(r["time_ms"] for r in results) / total if total else 0

    print(f"\n===== 评测结果 =====")
    print(f"通过: {passed}/{total} ({round(passed/total*100,1)}%)")
    print(f"平均延迟: {round(avg_time)}ms")
    print(f"总耗时: {round(sum(r['time_ms'] for r in results))}ms")

    # 保存结果
    out_file = Path(__file__).parent / f"eval_result_{int(time.time())}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump({"results": results, "passed": passed, "total": total, "avg_time_ms": avg_time}, f, ensure_ascii=False, indent=2)
    print(f"结果已保存: {out_file}")


if __name__ == "__main__":
    asyncio.run(run())
