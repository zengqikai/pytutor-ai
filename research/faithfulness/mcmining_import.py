"""
McMining 基准导入 —— SRS 3.2 补充 §2 的落地实现（纯离线）

它做三件事
----------
1. 把 McMining 的样本归一化成本项目的 EvalSample；
2. 把它的误区类目映射到 M1–M8，映射不上的落 beyond-M（这是**特性不是缺陷**）；
3. 逐条留存许可证，发布前用 license_gate 机械筛除不可再分发的样本。

关于"我没见过它的真实数据格式"
------------------------------
本文件是在**无法访问 taisazero/mcminer 仓库**的条件下写的。因此所有对外部
格式的假设都被收拢进 `McMinerLoader` 这一个类，而不是散落各处。你在本地
拿到仓库后，只需改 `McMinerLoader._parse_record()` 一个方法，其余全部不动。

`--dry-run` 会打印它**实际看到**的字段名和类目分布，用它来对齐，不要猜。

关于类别映射
------------
MCMINING_TO_M 是**人工判断**，不是机械转换。每一条都应经过评审，因为：
  - 外部类目的粒度可能与 M 不同（一对多、多对一）；
  - 同名不同义是常态（它的 "off_by_one" 未必等于我们 M5 的 range 半开区间）。
映射决策连同 origin_label 一起留存，任何人都能回头审计某条样本为什么被打成 M5。

**映射不上不是失败。** beyond-M 桶的规模直接回答"M1–M8 覆盖了初学者误区的
多少"，这是论文动机里最有价值的一个数字，不要为了好看硬凑映射。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from research.faithfulness.eval_sample import (  # noqa: E402
    BEYOND_M, Category, EvalSample, Source,
    coverage_report, dedup, license_gate, save_jsonl,
)


# =============================================================================
# 1. 类别映射（人工建立，须评审 —— 每条都写明理由）
# =============================================================================

# key 为 McMining 侧类目名（小写下划线归一化后），value 为本项目 M 编号。
# 注意：下面的 key 是**占位示例**，取自 SRS 3.2 补充 §2.1 给出的样例，
# 必须用 --dry-run 打印出的真实类目名替换。
MCMINING_TO_M: dict[str, str] = {
    # 理由：把 in-place 方法的返回值当成新对象 —— 与 M3 同根因
    "append_returns_none": "M3",
    # 理由：函数只输出不返回 —— 与 M6 同根因
    "print_vs_return": "M6",
    # 理由：range 半开区间误解导致的边界错 —— 与 M5 同根因
    "range_off_by_one": "M5",
    # 理由：= 与 == 混淆 —— 与 M1 同根因
    "assign_equality_confusion": "M1",
    # 理由：遍历得到的是元素而非索引 —— 与 M4 同根因
    "value_as_index": "M4",
    # 理由：input() 返回字符串未转换 —— 与 M7 同根因
    "input_string_not_int": "M7",
}

# 已评审确认"故意不映射"的类目（与其硬凑，不如进 beyond-M）。
# 写在这里是为了让审计者看到这是决策，不是遗漏。
DELIBERATELY_BEYOND_M: set[str] = {
    # 例：作用域/闭包类误区，M1–M8 完全没覆盖
    "closure_late_binding",
    "mutable_default_argument",
}


def map_or_beyond(category: str) -> str:
    """外部类目 → M 编号；映射不上一律 beyond-M。"""
    key = (category or "").strip().lower().replace("-", "_").replace(" ", "_")
    return MCMINING_TO_M.get(key, BEYOND_M)


# =============================================================================
# 2. Loader —— 唯一与外部格式耦合的地方
# =============================================================================

@dataclass
class McMinerRecord:
    """归一化后的外部记录。字段名是**我们的**，不是它的。"""
    code: str
    misconception: str
    language: str = "python"
    license: str = "unknown"
    record_id: str = ""
    is_correct_code: bool = False   # McMining 含正确代码样本 → 可作 hard negative
    raw: dict[str, Any] | None = None


class McMinerLoader:
    """读 McMining 官方基准。

    ！！本地对齐点 ！！
    `_parse_record` 里的字段名是**猜的**。拿到仓库后：
        python mcmining_import.py --raw-dir <path> --dry-run
    它会打印实际的顶层键与类目分布，据此改这一个方法即可。
    """

    # 容忍常见的字段命名变体，减少你手改的概率
    _CODE_KEYS = ("code", "source", "src", "program", "submission")
    _MC_KEYS = ("misconception", "label", "category", "mc", "misconception_type")
    _LANG_KEYS = ("language", "lang")
    _LICENSE_KEYS = ("license", "licence", "spdx")
    _ID_KEYS = ("id", "sample_id", "uid")
    _CORRECT_KEYS = ("is_correct", "correct", "no_misconception")

    def __init__(self, raw_dir: str | Path, default_license: str = "unknown"):
        self.raw_dir = Path(raw_dir)
        self.default_license = default_license

    # -- 文件发现 --------------------------------------------------------

    def _iter_raw(self) -> Iterator[dict[str, Any]]:
        if not self.raw_dir.exists():
            raise FileNotFoundError(f"raw-dir 不存在：{self.raw_dir}")

        files = sorted(
            [p for p in self.raw_dir.rglob("*") if p.suffix in {".json", ".jsonl"}]
        )
        if not files:
            raise FileNotFoundError(
                f"{self.raw_dir} 下没有 .json/.jsonl。McMining 若用别的格式"
                f"（csv/parquet），请在此扩展 _iter_raw()。"
            )

        for p in files:
            if p.suffix == ".jsonl":
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            yield json.loads(line)
            else:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    yield from data
                elif isinstance(data, dict):
                    # 常见形态：{"samples": [...]} 或 {"data": [...]}
                    for k in ("samples", "data", "items", "records"):
                        if isinstance(data.get(k), list):
                            yield from data[k]
                            break
                    else:
                        yield data

    @staticmethod
    def _first(d: dict[str, Any], keys: tuple[str, ...], default: Any = None) -> Any:
        for k in keys:
            if k in d and d[k] is not None:
                return d[k]
        return default

    def _parse_record(self, d: dict[str, Any]) -> McMinerRecord | None:
        """>>> 本地对齐点：拿到真实格式后主要改这里 <<<"""
        code = self._first(d, self._CODE_KEYS)
        if not code or not str(code).strip():
            return None
        mc = self._first(d, self._MC_KEYS, default="")
        correct = bool(self._first(d, self._CORRECT_KEYS, default=False))
        return McMinerRecord(
            code=str(code),
            misconception=str(mc),
            language=str(self._first(d, self._LANG_KEYS, "python")).lower(),
            license=str(self._first(d, self._LICENSE_KEYS, self.default_license)),
            record_id=str(self._first(d, self._ID_KEYS, "")),
            is_correct_code=correct,
            raw=d,
        )

    def load(self) -> list[McMinerRecord]:
        out = []
        for d in self._iter_raw():
            if not isinstance(d, dict):
                continue
            rec = self._parse_record(d)
            if rec:
                out.append(rec)
        return out

    def inspect(self, limit: int = 400) -> dict[str, Any]:
        """--dry-run 用：报告实际字段名与类目分布，供你对齐映射表。"""
        keys: dict[str, int] = {}
        cats: dict[str, int] = {}
        langs: dict[str, int] = {}
        n = 0
        for d in self._iter_raw():
            if not isinstance(d, dict):
                continue
            n += 1
            for k in d:
                keys[k] = keys.get(k, 0) + 1
            rec = self._parse_record(d)
            if rec:
                cats[rec.misconception] = cats.get(rec.misconception, 0) + 1
                langs[rec.language] = langs.get(rec.language, 0) + 1
            if n >= limit:
                break
        unmapped = {c: v for c, v in cats.items() if map_or_beyond(c) == BEYOND_M}
        return {
            "records_scanned": n,
            "top_level_keys": dict(sorted(keys.items(), key=lambda kv: -kv[1])),
            "languages": langs,
            "categories": dict(sorted(cats.items(), key=lambda kv: -kv[1])),
            "unmapped_categories": dict(sorted(unmapped.items(), key=lambda kv: -kv[1])),
            "mapped_ratio": round(1 - len(unmapped) / len(cats), 4) if cats else None,
        }


# =============================================================================
# 3. 导入主流程
# =============================================================================

def import_mcminer(
    raw_dir: str | Path,
    extract_ast_evidence: Callable[[str], list[str]] | None = None,
    keep_beyond_m: bool = True,
) -> tuple[list[EvalSample], list[str]]:
    """返回 (样本列表, 问题报告)。

    extract_ast_evidence: 注入 B 方向的 visitor 证据抽取器。不注入时留空列表，
    便于在没有 app 包的环境里单独跑导入（证据可后补）。
    """
    loader = McMinerLoader(raw_dir)
    records = loader.load()

    samples: list[EvalSample] = []
    problems: list[str] = []

    for rec in records:
        if rec.language != "python":
            continue  # 语言过滤：非 Python 直接丢弃，避免污染 M1–M8 语义

        label = map_or_beyond(rec.misconception)
        if label == BEYOND_M and not keep_beyond_m:
            continue

        if rec.is_correct_code:
            # McMining 里的正确代码样本 → 我们的 hard_negative，
            # 这正是本项目最缺、且外部基准罕有提供的那一半。
            category, labels = Category.HARD_NEGATIVE.value, []
        else:
            category, labels = Category.POSITIVE.value, [label]

        s = EvalSample(
            code=rec.code,
            language="python",
            mc_labels=labels,
            category=category,
            ast_evidence=extract_ast_evidence(rec.code) if extract_ast_evidence else [],
            source=Source.MCMINER.value,
            license=rec.license,
            sample_id=f"mcminer::{rec.record_id or len(samples)}",
            origin_label=rec.misconception,
        )
        errs = s.validate()
        if errs:
            problems.append(f"{s.sample_id}: {'; '.join(errs)}")
            continue
        samples.append(s)

    return dedup(samples), problems


def main() -> int:
    ap = argparse.ArgumentParser(description="McMining → EvalSample 导入")
    ap.add_argument("--raw-dir", required=True, help="McMining 基准数据目录")
    ap.add_argument("--out", default="mcminer_samples.jsonl")
    ap.add_argument("--dry-run", action="store_true",
                    help="只探查格式与类目分布，不写文件（首次务必先跑这个）")
    ap.add_argument("--drop-beyond-m", action="store_true",
                    help="丢弃映射不上的样本（默认保留，用于覆盖面统计）")
    args = ap.parse_args()

    if args.dry_run:
        info = McMinerLoader(args.raw_dir).inspect()
        print(json.dumps(info, ensure_ascii=False, indent=2))
        print("\n>>> 用上面的 categories 替换 MCMINING_TO_M 的 key，再正式导入。")
        return 0

    samples, problems = import_mcminer(args.raw_dir, keep_beyond_m=not args.drop_beyond_m)
    public, local_only = license_gate(samples)

    print(f"导入 {len(samples)} 条（去重后）")
    print(f"许可证闸门：可公开 {len(public)} / 仅本地 {len(local_only)}")
    if problems:
        print(f"\n校验失败 {len(problems)} 条（已跳过）：")
        for p in problems[:10]:
            print("  ✗", p)

    print("\n=== 覆盖面对照（M1–M8 覆盖了多少）===")
    print(json.dumps(coverage_report(samples), ensure_ascii=False, indent=2))

    n = save_jsonl(samples, args.out)
    print(f"\n已写入 {n} 条 → {args.out}")
    if local_only:
        save_jsonl(local_only, args.out.replace(".jsonl", ".local_only.jsonl"))
        print("不可再分发样本已单独存放，请勿并入公开发布集。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
