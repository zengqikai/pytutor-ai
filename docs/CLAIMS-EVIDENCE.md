# 创新主张 → 实现 → 界面 → 证据

> 对应完善任务清单 **16** 的验收项："每条创新主张对应算法、实际界面及实验结果"。
> 用途：答辩、论文和评审时逐条对照。**只引用本条的证据，不跨条外推**。
> 状态词按 [`REPRODUCIBILITY.md §7`](REPRODUCIBILITY.md) 区分：已实现 / 已启用 / 已验证。

## 1. 四条主贡献（对应 PPT P16）

| # | 主张 | 算法实现 | 用户可见位置 | 证据 | 不能宣称 |
|---|------|----------|--------------|------|----------|
| 01 | **可解释诊断**<br>Interpretable diagnosis | 正则 → AST → LLM 三层；证据与置信度见 [`analysis/`](../backend/app/analysis/)、[`misconception_service.py`](../backend/app/services/misconception_service.py) | 练习提交后的「误区诊断」卡片（名称 + 依据 + 相关概念）；对话消息上的误区/置信度/依据 | 同集：47/47 exact、macro-F1 1.000、干净代码 0/22 误报；单作者留出集：25/30（0.833）、macro-F1 0.883、0/15 误报（M5 recall 0.25、M6 0.50）；[`v2_eval_results.json`](../evaluation/v2_eval_results.json)、[`v2_holdout_results.json`](../evaluation/v2_holdout_results.json) | 双人标注的留出集准确率、置信度已校准 |
| 02 | **教学控制**<br>Pedagogical control | 7 种策略 + 5 级提示；转移图在 [`pedagogy/steering.py`](../backend/app/services/pedagogy/steering.py)，默认关 | 提示按钮的 L1–L5 标签；消息 metadata 里的 `strategy` / `strategy_source`；教师端策略说明 | [`test_e_direction.py`](../backend/tests/test_e_direction.py)、[`test_pedagogy.py`](../backend/tests/test_pedagogy.py)、[`test_tutor_review.py`](../backend/tests/test_tutor_review.py) | 转移图优于规则（未评测）、学习增益 |
| 03 | **学习者适配**<br>Learner adaptation | 画像字段 + 时间衰减 + 误区历史；[`profile_service.py`](../backend/app/services/profile_service.py)、[`profile_decay_service.py`](../backend/app/services/profile_decay_service.py) | 个人画像页、教师看板、入门诊断结果、`hint_dependency` 分布 | [`test_onboarding_profile.py`](../backend/tests/test_onboarding_profile.py)、[`test_learning_loop.py`](../backend/tests/test_learning_loop.py)、[`test_profile_decay.py`](../backend/tests/test_profile_decay.py) | 掌握度/能力值有效、成绩提升 |
| 04 | **可验证工程**<br>Verifiable engineering | 统一沙箱边界 [`sandbox/runner.py`](../backend/app/sandbox/runner.py)；10 个 feature flag；离线评测脚本；CI | 沙箱不可用时显示"未判定"且不发奖励；降级标记；质量分仅在审核后显示 | 后端 **251 passed, 12 deselected**；前端 build 通过；[`results_summary.csv`](../evaluation/results_summary.csv)；[`REPRODUCIBILITY.md`](REPRODUCIBILITY.md) | 生产级安全、跨平台沙箱等价、长期稳定性 |

## 2. 支撑性主张（不在 P16 四条里，但论文会写）

| 主张 | 实现 | 界面 | 证据 | 不能宣称 |
|------|------|------|------|----------|
| **检索增强**（RAG） | DashScope `text-embedding-v3` + Chroma + TF-IDF + 合并；[`rag_service.py`](../backend/app/services/rag_service.py) | 对话基于知识库回答；知识库为空时自动导入 | 30 条可答查询：TF-IDF Hit@5 90.0% → 向量 93.3%；Recall@5 40.7% → 50.1%；MRR 0.900 → 0.890；Top-5 上下文 251 → 315 token（估算）。Hybrid 与向量相同（flag 关） | 融合有效、更大规模查询上的泛化、拒答能力（5 条无答案查询都返回了结果） |
| **Multi-Judge 评分** | 3 评委 Rubric V2；[`judge_service.py`](../backend/app/services/judge_service.py) | 质量分徽章（仅在审核成功时显示） | 10 案例均分 2.4、修订率 9/10、Fleiss κ 0.405；失败返回 `score=0, review_available=False` | 与人工评分一致、教学质量提升 |
| **忠实度核验** | 规则断言抽取（`rules_v2`，已剔除 Markdown 噪声）+ 作用域/类型判定；[`research/faithfulness/`](../research/faithfulness/) | 研究脚本，不进入产品界面 | 真实 `deepseek-chat` 两次运行：C1/C2 为 0.683/0.647、0.667/0.650，配对差均为负且 CI 含 0；详见 [RESULTS.md](../research/faithfulness/RESULTS.md) | AST 证据注入提升忠实度 |

## 3. 答辩时的最小引用集

1. "诊断在同集上 47/47、干净代码 0/22 误报，但这是同集验证；另写的留出集是 25/30（0.833）、干净代码 0/15 误报，缺口在 M5/M6，且留出集只有单作者标注。"
2. "检索在 30 条查询上，向量的 Hit@5/Recall@5 高于 TF-IDF，但 MRR 略低；Hybrid 与向量相同是因为权重融合开关没开。"
3. "评测、沙箱边界和奖励幂等都有离线测试与结果文件；学习增益和人工教学质量还没测。"

这三句分别对应 §1 的 01、§2 的 RAG、§1 的 04；不要在回答里把三者混成"系统整体有效"。
