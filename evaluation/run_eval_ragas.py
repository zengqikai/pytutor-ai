"""
Ragas 评测脚本
==============

评估 RAG 系统的四个维度：
- Faithfulness: 回答是否基于检索内容
- Context Relevance: 检索内容与问题是否相关
- Answer Relevance: 回答是否切题
- Context Recall: 检索是否覆盖了需要的信息

运行: python evaluation/run_eval_ragas.py
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

import asyncio
from datasets import Dataset
from ragas import evaluate
from ragas.metrics import faithfulness, context_relevancy, answer_relevancy, context_recall

from app.services.llm_service import chat_completion
from app.schemas.ai import ChatMessage

GOLDEN_FILE = Path(__file__).parent / "golden_dataset.json"


def load_cases():
    with open(GOLDEN_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["cases"]


async def run_ragas_eval():
    cases = load_cases()
    print(f"Ragas 评测: {len(cases)} 个测试用例\n")

    data = {"question": [], "answer": [], "contexts": [], "ground_truth": []}

    for case in cases:
        # 生成回答（模拟 RAG）
        response = await chat_completion(
            messages=[
                ChatMessage(role="system", content="你是 Python 导师，用中文回复。"),
                ChatMessage(role="user", content=case["input"]),
            ],
            max_tokens=300,
        )

        data["question"].append(case["input"])
        data["answer"].append(response.content)
        data["contexts"].append(["Python 教学知识库相关内容"])  # 实际应查 RAG
        data["ground_truth"].append(", ".join(case.get("expected_contains", [])))

        print(f"  [{case['id']}] {case['input'][:40]}... ✓")

    # Ragas 评测
    dataset = Dataset.from_dict(data)
    result = evaluate(
        dataset,
        metrics=[faithfulness, context_relevancy, answer_relevancy, context_recall],
    )

    print("\n===== Ragas 评测结果 =====")
    for k, v in result.items():
        print(f"  {k}: {v:.3f}")

    # 保存
    out = Path(__file__).parent / f"ragas_result_{int(time.time())}.json"
    result.save(out)
    print(f"\n结果已保存: {out}")


if __name__ == "__main__":
    asyncio.run(run_ragas_eval())
