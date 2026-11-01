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
import hashlib
import json
import os
import random
import statistics
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Callable, Optional

from ast_facts import extract_facts
from faithfulness_verifier import FaithfulnessVerifier, RuleBasedClaimExtractor


# =============================================================================
# LLM 接入层（真实实验替换这里）
# =============================================================================

def build_llm(model: str) -> Optional[Callable[[str, str], str]]:
    """返回一个 llm_call(prompt, system) -> str；无凭据时返回 None。

    凭据优先级：PYTUTOR_LLM_KEY > 项目 backend/.env 的 DEEPSEEK_API_KEY。
    与教学系统复用同一个 OpenAI 兼容端点，保证实验条件与线上一致。

    实验纪律：解释模型与断言抽取模型必须分离。这里只负责解释模型的调用，
    断言抽取仍走 RuleBasedClaimExtractor（确定性规则），避免同源偏置。
    """
    backend_dir = Path(__file__).resolve().parents[2] / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    # settings 是在 import 时读取 .env 的，而它的 env_file 是相对路径。
    # 从 research/faithfulness 直接运行时 cwd 不是 backend，必须先显式加载一份。
    env_file = backend_dir / ".env"
    if env_file.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_file, override=False)
        except Exception as e:
            print(f"[build_llm] 读取 {env_file} 失败：{e}")

    api_key = os.environ.get("PYTUTOR_LLM_KEY", "").strip()
    base_url = os.environ.get("PYTUTOR_LLM_BASE_URL", "").strip()
    resolved_model = model

    if not api_key:
        try:
            from app.core.config import settings
            api_key = (settings.deepseek_api_key or "").strip()
            base_url = base_url or settings.deepseek_base_url
            if model in ("", "deepseek", "default"):
                resolved_model = settings.deepseek_model
        except Exception as e:  # 没装依赖或配置缺失
            print(f"[build_llm] 读取项目配置失败：{e}")

    if not api_key or api_key.startswith("sk-placeholder"):
        return None
    if not base_url:
        base_url = "https://api.deepseek.com"
    if model in ("", "deepseek", "default"):
        resolved_model = os.environ.get("PYTUTOR_LLM_MODEL", "deepseek-chat")

    from openai import OpenAI  # 延迟导入：离线演示不需要该依赖

    client = OpenAI(api_key=api_key, base_url=base_url)
    temperature = float(os.environ.get("PYTUTOR_LLM_TEMPERATURE", "0.3"))

    def call(prompt: str, system: str = "") -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        resp = client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            temperature=temperature,
            max_tokens=int(os.environ.get("PYTUTOR_LLM_MAX_TOKENS", "600")),
        )
        # token 用量按供应商返回值累计，便于成本核算；部分兼容端点不返回 usage。
        usage = getattr(resp, "usage", None)
        call.usage["calls"] += 1                     # type: ignore[attr-defined]
        if usage is not None:
            call.usage["prompt_tokens"] += getattr(usage, "prompt_tokens", 0) or 0      # type: ignore[attr-defined]
            call.usage["completion_tokens"] += getattr(usage, "completion_tokens", 0) or 0  # type: ignore[attr-defined]
        return resp.choices[0].message.content or ""

    # 供结果文件记录实际使用的模型与参数
    call.usage = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0}  # type: ignore[attr-defined]
    call.model_name = resolved_model          # type: ignore[attr-defined]
    call.temperature = temperature            # type: ignore[attr-defined]
    return call


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

def _dataset_hash(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def _bootstrap_ci(values: list[float], n_boot: int = 2000, seed: int = 20260701) -> list[float]:
    """配对差值的 95% 置信区间（百分位 bootstrap）。零依赖、可复现。"""
    if len(values) < 2:
        return [float("nan"), float("nan")]
    rng = random.Random(seed)
    means = []
    n = len(values)
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int(0.025 * n_boot)]
    hi = means[int(0.975 * n_boot) - 1]
    return [round(lo, 3), round(hi, 3)]


def run(dataset_path: str, llm_call: Callable[[str, str], str],
        conditions=("C1", "C2"),
        resume_path: Optional[str] = None,
        out_path: Optional[str] = None) -> dict:
    with open(dataset_path, encoding="utf-8") as f:
        data = json.load(f)
    items = data["items"]
    extractor = RuleBasedClaimExtractor()

    rows: list[dict] = []
    done_ids: set[str] = set()
    if resume_path and os.path.exists(resume_path):
        try:
            prev = json.load(open(resume_path, encoding="utf-8"))
            rows = prev.get("rows", [])
            done_ids = {r["id"] for r in rows}
            print(f"[resume] 已完成 {len(done_ids)} 条，从断点继续")
        except Exception as e:
            print(f"[resume] 读取失败，重新开始：{e}")

    total = len(items)
    for idx, item in enumerate(items, 1):
        if item["id"] in done_ids:
            continue
        code = item["code"]
        verifier = FaithfulnessVerifier(code)
        row = {
            "id": item["id"],
            "category": item["category"],
            "label": item["label"],
        }
        for cond in conditions:
            prompt = make_prompt_c1(code) if cond == "C1" else make_prompt_c2(code)
            started = time.perf_counter()
            try:
                explanation = llm_call(prompt, "")
                error = None
            except Exception as e:  # 单条失败不中断整轮实验
                explanation, error = "", f"{type(e).__name__}: {str(e)[:200]}"
            latency_ms = round((time.perf_counter() - started) * 1000, 1)
            rep = verifier.verify(explanation, extractor) if explanation else None
            row[cond] = {
                "faithfulness": rep.faithfulness if rep else None,
                "hallucination_rate": rep.hallucination_rate if rep else None,
                "verifiable": rep.verifiable if rep else 0,
                "unverifiable": rep.unverifiable if rep else 0,
                "total_claims": rep.total_claims if rep else 0,
                "explanation": explanation,
                "claims": [
                    {"text": d.claim.text, "predicate": d.claim.predicate,
                     "verdict": d.verdict.value, "reason": d.reason}
                    for d in (rep.details if rep else [])
                ],
                "error": error,
                "latency_ms": latency_ms,
            }
        rows.append(row)
        print(f"[{idx}/{total}] {item['id']} 完成")
        if out_path:  # 增量落盘：长实验中断也不丢已完成样本
            json.dump({"rows": rows}, open(out_path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)

    # ---------- 聚合 ----------
    def _values(cond, field, category=None):
        out = []
        for r in rows:
            if category and r["category"] != category:
                continue
            v = r[cond].get(field)
            if v is not None:
                out.append(v)
        return out

    def agg(cond, field, category=None):
        vals = _values(cond, field, category)
        return round(statistics.mean(vals), 3) if vals else None

    summary = {}
    for cond in conditions:
        scored = [r[cond] for r in rows if r[cond]["verifiable"] > 0]
        summary[cond] = {
            "n_items": len(rows),
            "n_scored": len(scored),
            # 覆盖率：有多少条解释至少含一个可核验断言
            "claim_coverage": round(len(scored) / len(rows), 3) if rows else None,
            "faithfulness_overall": agg(cond, "faithfulness"),
            "hallucination_overall": agg(cond, "hallucination_rate"),
            "faithfulness_positive": agg(cond, "faithfulness", "positive"),
            "faithfulness_hard_negative": agg(cond, "faithfulness", "hard_negative"),
            "mean_latency_ms": round(statistics.mean(
                [r[cond]["latency_ms"] for r in rows]), 1) if rows else None,
            "errors": sum(1 for r in rows if r[cond]["error"]),
        }

    # 配对差异：只统计两个条件都有有效评分的样本
    paired = []
    if "C1" in conditions and "C2" in conditions:
        for r in rows:
            a, b = r["C1"]["faithfulness"], r["C2"]["faithfulness"]
            if a is not None and b is not None:
                paired.append(b - a)
        if paired:
            summary["paired_diff_C2_minus_C1"] = {
                "n_pairs": len(paired),
                "mean": round(statistics.mean(paired), 3),
                "median": round(statistics.median(paired), 3),
                "ci95": _bootstrap_ci(paired),
            }

    meta = {
        "dataset": os.path.basename(dataset_path),
        "dataset_sha256_16": _dataset_hash(dataset_path),
        "n_items": len(items),
        "model": getattr(llm_call, "model_name", "stub"),
        "temperature": getattr(llm_call, "temperature", None),
        "conditions": list(conditions),
        "prompt_versions": {"C1": "c1_v1", "C2": "c2_v1"},
        "claim_extractor": "RuleBasedClaimExtractor/rules_v2",
        "llm_usage": getattr(llm_call, "usage", None),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    return {"meta": meta, "summary": summary, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=os.path.join(os.path.dirname(__file__), "dataset_seed.json"))
    ap.add_argument("--demo", action="store_true", help="用桩 LLM 离线演示")
    ap.add_argument("--model", default="deepseek")
    ap.add_argument("--out", default=None)
    ap.add_argument("--resume", action="store_true", help="从 --out 已有结果断点续跑")
    args = ap.parse_args()

    if args.demo:
        llm_call = _stub_llm
        print("[demo] 使用离线桩 LLM（非真实模型），结果只能用于验证链路，不能作为研究证据。")
    else:
        llm_call = build_llm(args.model)
        if llm_call is None:
            # 真实实验模式必须明确失败：不能把桩结果悄悄当成模型结果
            print("错误：未找到 LLM 凭据（PYTUTOR_LLM_KEY 或 backend/.env 的 DEEPSEEK_API_KEY）。")
            print("如需只验证链路，请显式加 --demo。")
            sys.exit(2)

    result = run(
        args.dataset, llm_call,
        resume_path=args.out if args.resume else None,
        out_path=args.out,
    )
    print("=== 条件级聚合（忠实度越高越好，幻觉率越低越好）===")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    print("=== 实验元信息 ===")
    print(json.dumps(result["meta"], ensure_ascii=False, indent=2))

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"完整结果已写入 {args.out}")


if __name__ == "__main__":
    main()
