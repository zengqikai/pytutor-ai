"""构建忠实度人工抽查表（任务 10 的工具部分）。

从真实模型结果中**分层**抽取 30 条断言，供人工填写判定列：
    supported    : 5 条 C1 + 5 条 C2
    unsupported  : 5 条 C1 + 5 条 C2（C1 池只有 5 条，全部取）
    unverifiable : 5 条 C1 + 5 条 C2

设计约束：
- 只读 `results_real_deepseek_v2_run1.json`，不调用模型；
- 抽样确定性（固定 seed），同一份结果文件永远生成同一张表；
- 同一 (condition, verdict) 桶内尽量分散到不同样例题，避免一条题占满；
- 人工列（human_extraction_ok / human_verdict / notes）留空。

用法（仓库根目录）：
    python evaluation/build_spotcheck.py
"""

from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "research" / "faithfulness" / "results_real_deepseek_v2_run1.json"
OUTPUT = ROOT / "faithfulness_spotcheck.csv"

PER_VERDICT_PER_CONDITION = 5
SEED = 20261101


def _pick(pool: list[dict], n: int) -> list[dict]:
    """按 item 轮转抽取，保证同桶内不同题目尽量均匀。"""
    by_item: dict[str, list[dict]] = defaultdict(list)
    for row in pool:
        by_item[row["item_id"]].append(row)
    items = sorted(by_item)
    rng = random.Random(SEED)
    rng.shuffle(items)
    for claims in by_item.values():
        rng.shuffle(claims)

    picked: list[dict] = []
    while len(picked) < n and items:
        still = []
        for item in items:
            if by_item[item] and len(picked) < n:
                picked.append(by_item[item].pop())
                if by_item[item]:
                    still.append(item)
        items = still
    return picked


def main() -> None:
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    buckets: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in data["rows"]:
        for condition in ("C1", "C2"):
            for claim in row.get(condition, {}).get("claims", []):
                buckets[(condition, claim.get("verdict", ""))].append(
                    {
                        "item_id": row["id"],
                        "category": row.get("category", ""),
                        "condition": condition,
                        "claim_text": claim.get("text", ""),
                        "auto_predicate": claim.get("predicate", ""),
                        "auto_verdict": claim.get("verdict", ""),
                        "auto_reason": claim.get("reason", ""),
                    }
                )

    # 优先级：先满足每个（verdict, condition）桶，再按 supported→unsupported→unverifiable 排列。
    verdict_order = ["supported", "unsupported", "unverifiable"]
    selected: list[dict] = []
    shortages: list[str] = []
    for verdict in verdict_order:
        for condition in ("C1", "C2"):
            pool = buckets[(condition, verdict)]
            need = PER_VERDICT_PER_CONDITION
            got = _pick(pool, need)
            if len(got) < need:
                shortages.append(f"{condition}/{verdict}: {len(got)}/{need}")
            selected.extend(got)

    selected.sort(key=lambda r: (verdict_order.index(r["auto_verdict"]), r["condition"], r["item_id"]))
    for i, row in enumerate(selected, 1):
        row["sample_id"] = f"S{i:02d}"

    fields = [
        "sample_id",
        "item_id",
        "category",
        "condition",
        "claim_text",
        "auto_predicate",
        "auto_verdict",
        "auto_reason",
        "human_extraction_ok",
        "human_verdict",
        "notes",
    ]
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in selected:
            writer.writerow({k: row.get(k, "") for k in fields})

    print(f"wrote {len(selected)} rows -> {OUTPUT}")
    counts: dict[tuple[str, str], int] = defaultdict(int)
    for row in selected:
        counts[(row["condition"], row["auto_verdict"])] += 1
    for key in sorted(counts):
        print(f"  {key[0]} / {key[1]}: {counts[key]}")
    if shortages:
        print("short buckets (pool smaller than target):")
        for s in shortages:
            print("  " + s)


if __name__ == "__main__":
    main()
