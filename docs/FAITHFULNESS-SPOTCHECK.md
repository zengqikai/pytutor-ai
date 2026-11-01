# 忠实度人工抽查表（待填写）

> 对应完善任务清单 **10** 的验收项："抽取与判定各 ≥30 例人工核对"。
> 表已经抽好，但**没有填写任何人工结果**——这里不能由代码替代。

## 1. 已生成的文件

[evaluation/faithfulness_spotcheck.csv](../evaluation/faithfulness_spotcheck.csv)：

- 30 条断言，来自 `results_real_deepseek_v2_run1.json`（真实 `deepseek-chat`）
- 每个「判定 × 条件」桶各 5 条：`supported` / `unsupported` / `unverifiable` × C1 / C2
  （C1 的 `unsupported` 池只有 5 条，全部取）
- 按题目轮转抽样，30 条覆盖全部 9 个有断言的样例题，positive / hard_negative /
  intent_dependent 三类都有
- 重新生成（确定性，固定 seed，不调模型）：

  ```bash
  python evaluation/build_spotcheck.py
  ```

| 列 | 含义 |
|----|------|
| `claim_text` | 规则抽取器认为的"断言" |
| `auto_predicate` | 规则分类的断言类型 |
| `auto_verdict` / `auto_reason` | 核验器给出的判定与理由 |
| `human_extraction_ok` | **待填**：这句话是否真的是一条可核验的断言？`y` / `n` |
| `human_verdict` | **待填**：人工判定 `supported` / `contradicted` / `unverifiable` |
| `notes` | **待填**：分歧原因 |

用 Excel 直接打开（UTF-8 BOM，中文不乱码）。

## 2. 填写规则

1. **抽取正确**（`human_extraction_ok=y`）：这句话对代码行为做出了可判断真假的陈述。
   建议、提问、纯格式文本填 `n`。
2. **判定正确**：人工判定与 `auto_verdict` 一致才算对；不一致时在 `notes` 写依据
   （引用代码行或报错）。
3. 不要参考 `auto_reason` 之外的信息去"猜"模型意图；只看代码与断言本身。

## 3. 汇总（填完后更新）

| 指标 | 结果 |
|------|------|
| 抽取正确率 | 待填（目标：记录，不设及格线） |
| 判定一致率 | 待填 |
| `supported` 被判成 `unverifiable` | 待填 |
| `unverifiable` 被判成断言 | 待填 |
| 主要分歧类型 | 待填 |

## 4. 填完后要同步的位置

- 本文 §3 汇总表
- [research/faithfulness/RESULTS.md](../research/faithfulness/RESULTS.md) §4"人工抽查缺失"
- [docs/TASK-STATUS.md](TASK-STATUS.md) 任务 10 的状态
- [docs/CLAIMS-EVIDENCE.md](CLAIMS-EVIDENCE.md) 忠实度一行的"证据/不能宣称"
- `evaluation/results_summary.csv`（如果新增了指标）
- PPT P14 的忠实度行（如果结论发生变化）

## 5. 为什么没有自动填

规则抽取器与核验器都是确定性代码；用同一个程序去"核对"自己的输出，只能证明
代码自洽，不能证明判定符合人的理解。这一步必须由人完成，否则任何"一致率"都是伪造。
