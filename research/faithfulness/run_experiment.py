"""
忠实度对比实验编排器 (R2)
=========================

实验矩阵：
  C1 — 纯 LLM 解释（基线）：只给代码，让 LLM 说"有什么误区、为什么"。
  C2 — AST 证据注入解释：把 ast_facts 抽出的结构事实先注入 prompt，再让 LLM 解释。
  (可选) C3 — 换一个模型重复 C1/C2，测跨模型稳健性。

对每条样本、每个条件，用 FaithfulnessVerifier 算：忠实度、幻觉率、
不可核验占比；再在数据集上聚合，并对 positive / hard_negative 分层报告。

关键假设检验：C2 的忠实度是否显著高于 C1（证据注入的缓解效果）。
在 hard_negative 上还额外报"假阳性率"——LLM 是否在正确代码上编造误区。

运行方式
--------
  1. 离线演示（无需 API）：
        python run_experiment.py --demo
     用内置桩 LLM（stub）演示完整链路与指标计算，可复现、可进 CI。

  2. 真实实验（需注入 LLM 客户端）：
     实现一个 `llm_call(prompt: str, system: str = "") -> str`，
     在 build_llm() 里返回它（例如接 DeepSeek / 另一模型），然后：
        python run_experiment.py --model deepseek --out results.json
     注意：断言抽取模型应与被测解释模型分离，避免同源偏置。
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
from dataclasses import asdict
from typing import Callable, Optional

from ast_facts import extract_facts
from faithfulness_verifier import FaithfulnessVerifier, RuleBasedClaimExtractor


# =============================================================================
# LLM 接入层（真实实验替换这里）
# =============================================================================

def build_llm(model: str) -> Optional[Callable[[str, str], str]]:
    """返回一个 llm_call(prompt, system) -> str；无 API 时返回 None。

    真实实验请在此接入具体模型，例如：
        from openai import OpenAI
        client = OpenAI(base_url=..., api_key=...)
        def call(prompt, system=""):
            r = client.chat.completions.create(model=model, messages=[...])
            return r.choices[0].message.content
        return call
    """
    if not os.environ.get("PYTUTOR_LLM_KEY"):
        return None
    # 占位：真实接入在此实现
    raise NotImplementedError("请在 build_llm() 中接入真实 LLM 客户端")


# =============================================================================
# 桩 LLM：离线演示用，模拟"纯LLM会幻觉、注入证据后更忠实"的典型行为
# =============================================================================

def _stub_llm(prompt: str, system: str = "") -> str:
    """确定性桩：不依赖网络。根据 prompt 里是否含 AST 事实块，返回
    更忠实 / 更易幻觉的解释，用来演示指标区分度（非真实模型输出）。"""
    grounded = "【AST 结构事实】" in prompt
    code = prompt.split("【学生代码】")[-1].split("【")[0].strip() if "【学生代码】" in prompt else ""

    facts = extract_facts(code)
    lines_with_facts = sorted({f.line for f in facts})

    # 从事实里挑真断言
    real_bits = []
    for f in facts[:3]:
        real_bits.append(f.describe())

    if grounded:
        # 注入证据 → 只基于事实说话，几乎不编造
        parts = []
        for f in facts[:3]:
            parts.append(f.describe().split(": ", 1)[-1] + "。")
        parts.append("建议对照上面结构逐行检查。")
        return "".join(parts) if parts else "未发现明显结构性误区。建议补充测试。"
    else:
        # 纯 LLM → 混入一些看似合理但代码里没有的断言（幻觉）
        parts = []
        if facts:
            parts.append(facts[0].describe().split(": ", 1)[-1] + "。")
        # 编造：谈一个大概率不在代码里的东西
        parts.append("第 99 行还使用了 range 左闭右开区间可能越界。")
        parts.append("另外这里的 while 循环有无限循环风险。")
        parts.append("建议多加练习。")
        return "".join(parts)


# =============================================================================
# Prompt 构造
# =============================================================================

def make_prompt_c1(code: str) -> str:
    return (
        "你是 Python 教学助手。请指出下面学生代码里存在什么常见误区、为什么。\n\n"
        f"【学生代码】\n{code}\n"
    )


def make_prompt_c2(code: str) -> str:
    facts = extract_facts(code)
    fact_lines = "\n".join(f"- {f.describe()}" for f in facts) or "-（无可抽取结构）"
    return (
        "你是 Python 教学助手。下面给出该代码经 AST 分析得到的客观结构事实，"
        "请**只依据这些事实**解释存在什么误区、为什么，不要编造事实里没有的内容。\n\n"
        f"【AST 结构事实】\n{fact_lines}\n\n"
        f"【学生代码】\n{code}\n"
    )


# =============================================================================
# 主流程
# =============================================================================

def run(dataset_path: str, llm_call: Callable[[str, str], str],
        conditions=("C1", "C2")) -> dict:
    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"]
    extractor = RuleBasedClaimExtractor()

    rows = []
    for item in items:
        code = item["code"]
        verifier = FaithfulnessVerifier(code)
        row = {"id": item["id"], "category": item["category"], "label": item["label"]}
        for cond in conditions:
            prompt = make_prompt_c1(code) if cond == "C1" else make_prompt_c2(code)
            explanation = llm_call(prompt, "")
            rep = verifier.verify(explanation, extractor)
            row[cond] = {
                "faithfulness": rep.faithfulness,
                "hallucination_rate": rep.hallucination_rate,
                "verifiable": rep.verifiable,
                "unverifiable": rep.unverifiable,
                "explanation": explanation,
            }
        rows.append(row)

    # 聚合
    def agg(cond, field, cat=None):
        vals = [r[cond][field] for r in rows
                if (cat is None or r["category"] == cat) and r[cond]["verifiable"] > 0]
        return round(statistics.mean(vals), 3) if vals else None

    summary = {}
    for cond in conditions:
        summary[cond] = {
            "faithfulness_overall": agg(cond, "faithfulness"),
            "hallucination_overall": agg(cond, "hallucination_rate"),
            "faithfulness_positive": agg(cond, "faithfulness", "positive"),
            "faithfulness_hard_negative": agg(cond, "faithfulness", "hard_negative"),
        }
    if "C1" in summary and "C2" in summary and \
            summary["C1"]["faithfulness_overall"] and summary["C2"]["faithfulness_overall"]:
        summary["delta_C2_minus_C1"] = round(
            summary["C2"]["faithfulness_overall"] - summary["C1"]["faithfulness_overall"], 3)

    return {"summary": summary, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=os.path.join(os.path.dirname(__file__), "dataset_seed.json"))
    ap.add_argument("--demo", action="store_true", help="用桩 LLM 离线演示")
    ap.add_argument("--model", default="deepseek")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    if args.demo:
        llm_call = _stub_llm
        print("[demo] 使用离线桩 LLM（非真实模型），仅演示指标计算链路。\n")
    else:
        llm_call = build_llm(args.model)
        if llm_call is None:
            print("未检测到 LLM 凭据；退回 --demo 桩模式。用 --demo 显式声明，或设置 PYTUTOR_LLM_KEY 并在 build_llm 接入模型。\n")
            llm_call = _stub_llm

    result = run(args.dataset, llm_call)
    print("=== 条件级聚合（忠实度越高越好，幻觉率越低越好）===")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n完整结果已写入 {args.out}")


if __name__ == "__main__":
    main()
