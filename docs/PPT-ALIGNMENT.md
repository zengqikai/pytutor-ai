# PPT 与当前结果对齐检查

> 对象：`PyTutor_3.0_Academic_Presentation.pptx`（18 页）。
> 方法：逐页提取文字，对照 `docs/TASK-STATUS.md` 的已验证数字。
> 结论：整体口径是诚实的（已写明"不是完整系统已解决""置信度不是校准概率"）。
> 2026-10-22 已把下面 4 处直接改入 PPTX；改动只涉及文字，没有改版式。

## 已应用的修改（2026-10-22）

### P12「Experimental setup」

原写 `20-case teaching benchmark`，但 Multi-Judge 评测集只有 **10 例**
（`evaluation/judge_eval_results.json`，`total_cases: 10`），20 例找不到对应文件。

已改为 `10-case teaching benchmark`，并在 Metrics 列末行加：

```
RAG: Hit@K / Recall@K / MRR
```

### P14「Experiment design and measured results」

原先把 Baseline / Ablation / Comparison 全写成计划，低估了已完成的工作。
标题已改为 `Experiment design and measured results`，四个流程卡片下方新增实测区：

| 已有结果 | 页面文字 |
|----------|----------|
| AST 诊断 | 47/47 exact、0/22 误报（same-set） |
| RAG TF-IDF → 向量 | Hit@5 90.0% → 93.3%；Recall@5 40.7% → 50.1%；MRR 0.900 → 0.890 |
| 忠实度 C1/C2 | 0.683/0.647（run 1）、0.667/0.650（run 2），C2 两次都未更优、CI 含 0 |

底部色带仍留给 `Planned`：扩标注数据、校准置信度、与通用编程助手对比。

### P15「Interpretable confidence and its boundary」

页面底部新增一行边界说明：

```
Boundary: weights are still heuristic; no Brier score or ECE is reported
until at least 200 independently labelled examples exist.
```

### P17「Compact demo route」

在 `Next` 一行上方新增负面分支提示：

```
Negative branches: no-misconception code → no label (not a false positive);
sandbox unavailable → not judged, no reward.
```

## 可直接引用的结果图

需要把结果放进论文或额外页面时，用 [`docs/figures/results-overview.svg`](figures/results-overview.svg)
（深色版 `results-overview-dark.svg`；PNG 导出方法见 [`docs/figures/README.md`](figures/README.md)）。
图中数字与 P13/P14 一致，并显式标注了"Hybrid = Vector"和"same-set"两个限制。

## 已核对无误的页面

| 页 | 内容 | 核对结果 |
|----|------|----------|
| P9 | 三层诊断：Regex → AST → LLM | 与 `app/analysis/` + `misconception_service` 一致 |
| P10 | 5 级提示 + 画像字段 | 与 `profile_service` / `tutor_service` 一致 |
| P11 | 沙箱 / 检索 / Agent / flags | 与 `sandbox/runner.py`、`rag_service`、10 个 flag 一致 |
| P12 | 47 + 22 数据集、脚本名 | 文件与脚本都存在 |
| P13 | 47/47、1.000、0%、<1.2ms | 与 `v2_eval_results.json` 一致（注意是**同集**结果，页上已限定 "local"） |
| P14 | holdout 25/30、RAG 90.0→93.3 / 40.7→50.1 / 0.900→0.890、忠实度两轮 | 与 `v2_holdout_results.json` 及三路 RAG 结果一致 |
| P16 | 四项贡献 | 均有代码与测试支撑；"verifiable engineering" 现在多了 CI 全量测试 |

## 答辩口头补充（页面上不必改）

- 后端离线测试 **251 passed**，前端构建通过。
- 沙箱边界统一：生产环境 Docker 不可用 → 拒绝执行，不降级到宿主进程。
- 判题奖励幂等、提示/看答案行为由服务端事件统计。
- 忠实度实验已用真实 `deepseek-chat` 跑过两轮；**不能**说证据注入更忠实。

## 不建议写进 PPT 的内容

| 说法 | 原因 |
|------|------|
| "AST 诊断准确率 100%" | 与规则同集，不是留出集；留出集是 25/30（83.3%），且为单作者标注 |
| "混合检索优于向量检索" | `ENABLE_HYBRID_WEIGHTS=false` 时结果完全相同 |
| "证据注入提升忠实度" | 两次运行方向相反，CI 跨 0 |
| "提升学习成绩" | 无参与者前后测 |
| "置信度已校准" | 仍是启发式分数（P15 已经写明，保持） |
