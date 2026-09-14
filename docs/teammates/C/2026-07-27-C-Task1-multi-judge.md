# C 方向 Task 1：Multi-Judge 评分系统 — 实现日志

## 2026-07-27 初始实现

### 完成内容

1. **Feature Flag 添加** (`config.py`)
   - 新增 `ENABLE_MULTI_JUDGE` (默认 false)、`ENABLE_TIME_DECAY` (默认 false)、`ENABLE_CONTENT_RECOMMEND` (默认 false)
   - 遵循 MASTER-PLAN 开关隔离法，默认关互不影响

2. **Multi-Judge 核心服务** (`judge_service.py`, 320 行)
   - `_single_judge()`: 单评委评分（独立 LLM 调用）
   - `_aggregate_verdicts()`: 中位数聚合 + Fleiss' Kappa 计算
   - `multi_judge_verify()`: 公开 API，替代单评委 verify_response
   - `evaluate_judge_agreement()`: 批量评估工具
   - 3 评委配置：同一模型，temperature 0.1/0.5/0.9（避免 self-enhancement bias，同时不引入跨供应商复杂度）

3. **verify_response() 开关路由** (`pedagogy_service.py`)
   - `ENABLE_MULTI_JUDGE=true` → 走 multi_judge_verify()
   - `ENABLE_MULTI_JUDGE=false` → 走原单评委逻辑（完全不动）
   - 返回格式向后兼容（额外字段仅在多评委模式下出现）

4. **评估脚本** (`evaluation/run_judge_eval.py`, 200+ 行)
   - 内置 10 例测试用例（覆盖高质量/中等/低质量/边界 4 类）
   - 支持 `--cases` 自定义测试集
   - 输出详细 JSON + 控制台汇总

5. **实现文档** (`docs/implementation/C-Task1-multi-judge.md`)

### 设计决策记录

| 决策 | 选择 | 理由 | 文献支撑 |
|------|------|------|---------|
| 评委数 | 3 | 奇数避免平票，3 次调用可接受 | Shi 2025: 多评委提升 Kappa |
| 多样性来源 | 不同 temperature | 避免跨供应商复杂度和成本 | Zheng 2024: self-enhancement bias |
| 聚合方法 | 中位数 | 抗极端值，RoPoLL 几何中位数最优 | Acharya 2026: 1/2 breakdown |
| Rubric 维度 | 5 | 平衡区分度和标注一致性 | Pathak 2025: 详细 Rubric 是主约束 |
| 刻度 | 1-5 | 与 PyTutor 5 级提示体系对齐 | 自有设计 |
| 一致性指标 | Fleiss' Kappa | 多评委天然适合 | Rao 2026: 唯一捕获边缘偏移 |

### 已知限制

1. **同模型评委**：DeepSeek-only，未跨供应商（成本 + 延迟约束）。后续可加 Claude/GPT 轮换验证
2. **无人工标注对比**：目前仅测评委间一致性。要验证 Kappa vs 人工需要 30 例人工标注
3. **3 个评委串行**：用了 asyncio.gather，但 3 个 LLM 调用并发 → ~3× 延迟。后续可考虑批量 API

### 下一步

- Task 2 (Rubric 细化)：基于 Task 1 的分歧分析，迭代优化 Rubric 文案
- 收集 30 例人工标注 → 计算 Multi-Judge vs 人工 Kappa
- 若 Kappa < 0.60，考虑：1) 细化 Rubric 维度 2) 加入少样本示例 3) 跨模型评委
