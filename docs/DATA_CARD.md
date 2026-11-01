# 数据卡（Dataset Card）

> 覆盖仓库内用于评测与实验的数据文件。**所有数据集目前都是项目自建**，
> 没有第三方许可约束，但也没有经过双人标注或外部验证。

## 1. 总览

| 数据集 | 文件 | 规模 | 用途 | 标注状态 |
|--------|------|------|------|----------|
| 误区诊断测试集 | `evaluation/v2_test_cases.json` | 47 正例（覆盖 M1–M8） | AST/规则诊断评估 | 单作者，与规则开发同源 |
| 干净代码集 | `evaluation/clean_code_cases.json` | 22 | 误报率（false positive） | 单作者 |
| 误区诊断留出集 | `evaluation/v2_holdout_cases.json` | 30 正例（每类 3–4 条） | 留出集诊断评估 | 单作者，评测前新写、未据此调规则 |
| 留出集干净代码 | `evaluation/holdout_clean_cases.json` | 15 | 留出集误报率 | 单作者 |
| RAG 相关性标注 | `evaluation/rag_golden.json` | 30 可答 + 5 无答案查询 | Hit@K / Recall@K / MRR + 无答案行为 | 单作者，粒度到 concept→chunk |
| RAG 语料 | `backend/app/rag/seed_data.py` | 10 篇 / 41 chunk | 检索知识库 | 项目自写教程内容 |
| 忠实度种子集 | `research/faithfulness/dataset_seed.json` | 10（5 正例 + 5 硬负例） | C1/C2 对比实验 | 单作者，含 1 条 intent_dependent |
| 早期回复评测集 | `evaluation/golden_dataset.json` | 10 | 早期裁判/回复质量 | 单作者，已被 v2 取代 |

## 2. 字段结构

### 2.1 `v2_test_cases.json`

```json
{
  "id": "M3-01",
  "code": "items = []\nnew = items.append(5)",
  "expected": "M3",
  "note": "append 返回值被赋给变量"
}
```

- `expected` 为空或 `"clean"` 表示不应诊断出误区。
- 正例覆盖 8 类误区；干净代码单独放在 `clean_code_cases.json`。

### 2.2 `rag_golden.json`

```json
{
  "id": "g002",
  "query": "for 循环怎么用？写一个例子",
  "relevant_chunk_ids": ["..."],
  "no_answer_case": false
}
```

- `relevant_chunk_ids` 是**全部**相关 chunk，Recall@K 的分母就是它。
- `no_answer_case` 为 true 的查询在检索评估中单独统计，不混入 Hit@K。

### 2.3 `dataset_seed.json`（忠实度）

```json
{
  "id": "P04",
  "category": "hard_negative",
  "label": "clean",
  "code": "name = 'Alice'\nprint('hello ' + name * 3)",
  "gold_issue": null,
  "source": "self-authored",
  "known_issues_fixed_in_0_2": "原标注为类型错误，实为合法的 str*int"
}
```

- `category`：`positive` / `hard_negative` / `intent_dependent`。
- `intent_dependent` 表示"是否有问题取决于题目意图"，判定时不计入正负例任一方向。

## 3. 已知问题与限制

1. **规模小**：RAG 只有 30 条查询，忠实度只有 10 条样本；任何百分比都应视为 smoke 结果。
2. **单人标注**：没有双人标注与分歧处理（任务清单要求至少 20% 双标）。
3. **同源污染**：47 + 22 条是照着规则开发的，只能报"同集结果"；30 + 15 条留出集在评测前新写、未据此调规则，但仍是同一作者编写，不能替代双人标注。
4. **留出集只用过一次**：`v2_holdout_results.json` 是首次也是目前唯一一次结果；如果之后修规则，需要另写新留出集，不能复用这 30 条。
5. **标注口径**：RAG 相关性是二值（相关/不相关），没有分级相关性。
6. **许可**：数据为项目自建，可随仓库分发；知识库内容为项目自写教程，不含第三方教材原文。

## 4. 版本与哈希

见 [REPRODUCIBILITY.md §5](REPRODUCIBILITY.md)。修改任一 JSON 后请重算 sha256 并更新该表，
否则论文/PPT 里的数字无法对应到具体数据版本。

## 5. 扩展计划（尚未执行）

| 目标 | 数量 | 阻塞点 |
|------|------|--------|
| 误区诊断留出集 | 当前 30 正例 + 15 干净；目标 60（30 + 30） | 需第二人独立标注 |
| RAG 查询 | 当前 30 条；需第二人复核 | 相关 chunk 目前是单作者标注 |
| 忠实度数据集 | 170（100 正例 / 40 硬负例 / 30 clean） | 需人工编写与双人核验 |

在这些数据完成前，报告里只能写"小样本试跑"，不能写"达到 X% 准确率"。
