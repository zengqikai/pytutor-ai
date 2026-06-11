"""
PyTutor 2.0 Baseline 对比评估
==============================

对 20 个 Python 初学者错误案例对比评估：
- PyTutor（误区诊断 + 教学策略）
- Baseline（普通 Chat API）
"""

import asyncio
import json
import time
from pathlib import Path

import httpx

BASE = "http://localhost:8000/api/v1"

# 误区编号名称映射
MC_NAMES = {
    "M1": "赋值与比较混淆", "M2": "缩进理解错误", "M3": "append返回值误解",
    "M4": "index/value混淆", "M5": "range右边界误解", "M6": "print/return混淆",
    "M7": "类型转换错误", "M8": "while循环条件错误",
}


async def get_token():
    async with httpx.AsyncClient(timeout=30) as c:
        r = await c.post(f"{BASE}/auth/login", json={"email": "tt@t.com", "password": "test12345"})
        return r.json()["access_token"]


async def run_pytutor_diagnosis(token: str, case: dict) -> dict:
    """PyTutor 误区诊断。"""
    async with httpx.AsyncClient(timeout=30) as c:
        h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        r = await c.post(f"{BASE}/misconceptions/diagnose",
            json={"code": case["code"], "stderr": case.get("stderr", "")}, headers=h)
        return r.json()


async def run_baseline_chat(case: dict) -> dict:
    """Baseline：直接用 DeepSeek 问。"""
    from app.services.llm_service import chat_completion
    from app.schemas.ai import ChatMessage

    prompt = f"""学生写了这段 Python 代码：
```python
{case['code']}
```
错误信息：{case.get('stderr', '')}
学生问题：{case.get('student_question', '')}

请指出问题并给出修改建议。"""

    resp = await chat_completion(
        messages=[ChatMessage(role="user", content=prompt)],
        temperature=0.3, max_tokens=300,
    )
    return {"response": resp.content[:400]}


def judge_pytutor_score(case: dict, diagnosis: dict) -> dict:
    """人工 rubric 评分（模拟）。"""
    scores = {"diagnosis_accuracy": 0, "hint_appropriate": 0, "no_premature_answer": 0}
    reasons = []

    # 诊断准确率
    if diagnosis.get("has_misconception"):
        if diagnosis.get("misconception_id") == case.get("expected_misconception"):
            scores["diagnosis_accuracy"] = 1
            reasons.append("误区诊断正确")
        else:
            scores["diagnosis_accuracy"] = 0.5
            reasons.append(f"诊断出 {diagnosis.get('misconception_id')}，期望 {case.get('expected_misconception')}")
    elif case.get("expected_misconception"):
        scores["diagnosis_accuracy"] = 0
        reasons.append("未诊断出应有误区")

    # 提示等级合适度
    hit_level = diagnosis.get("hint_level", 0) or 0
    expected = case.get("expected_hint_level", 1)
    scores["hint_appropriate"] = 1 if hit_level <= expected + 1 else 0.5

    # 不直接给答案（通过 confidence 间接判断）
    if hit_level <= 3:
        scores["no_premature_answer"] = 1
        reasons.append("未直接给答案")

    return {
        "scores": scores,
        "total": round(sum(scores.values()) / len(scores), 2),
        "reasons": reasons,
    }


async def main():
    # 加载测试用例
    cases_path = Path(__file__).parent / "v2_test_cases.json"
    cases = json.loads(cases_path.read_text(encoding="utf-8"))

    print(f"=== PyTutor 2.0 Baseline Evaluation ===\n")
    print(f"Cases: {len(cases)}")
    print(f"Metrics: Misconception Diagnosis Accuracy | Hint-Level Appropriateness | No Premature Answer\n")

    token = await get_token()

    pytutor_results = []
    baseline_results = []

    for i, case in enumerate(cases):
        print(f"[{i+1:2d}/{len(cases)}] {case['case_id']} ...", end=" ", flush=True)
        try:
            # PyTutor diagnosis
            start = time.perf_counter()
            diag = await run_pytutor_diagnosis(token, case)
            pytutor_time = (time.perf_counter() - start) * 1000

            # Judge
            judge = judge_pytutor_score(case, diag)
            pytutor_results.append({
                "case_id": case["case_id"],
                "expected": case.get("expected_misconception"),
                "diagnosed": diag.get("misconception_id"),
                "accurate": diag.get("misconception_id") == case.get("expected_misconception"),
                "scores": judge["scores"],
                "total": judge["total"],
                "time_ms": round(pytutor_time),
            })
            ok = "PASS" if judge['total'] >= 0.6 else "WARN"
            print(f"{ok} {judge['total']:.0%}")

        except Exception as e:
            print(f"FAIL {str(e)[:50]}")
            pytutor_results.append({"case_id": case["case_id"], "error": str(e)[:100]})

        # Baseline (every 5th to save API cost)
        if i % 5 == 0 and i < 15:
            try:
                baseline = await run_baseline_chat(case)
                baseline_results.append({
                    "case_id": case["case_id"],
                    "response": baseline["response"][:200],
                })
            except Exception:
                pass

    # Summary
    valid = [r for r in pytutor_results if "total" in r]
    if valid:
        avg_total = sum(r["total"] for r in valid) / len(valid)
        accuracy = sum(1 for r in valid if r.get("accurate")) / len(valid)

        print(f"\n=== Summary ===")
        print(f"Total cases:          {len(cases)}")
        print(f"Valid results:        {len(valid)}")
        print(f"Diagnosis Accuracy:   {accuracy:.1%}")
        print(f"Avg Score (3D):       {avg_total:.1%}")
        print(f"Avg Diagnosis Acc:    {sum(r['scores']['diagnosis_accuracy'] for r in valid)/len(valid):.1%}")
        print(f"Avg Hint Appropriate: {sum(r['scores']['hint_appropriate'] for r in valid)/len(valid):.1%}")
        print(f"Avg No Premature Ans: {sum(r['scores']['no_premature_answer'] for r in valid)/len(valid):.1%}")

    # Save results
    output_path = Path(__file__).parent / "v2_eval_results.json"
    output_path.write_text(json.dumps({
        "pytutor": pytutor_results,
        "baseline": baseline_results,
        "summary": {
            "total": len(cases),
            "accuracy": accuracy if valid else 0,
            "avg_score": avg_total if valid else 0,
        }
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(main())
