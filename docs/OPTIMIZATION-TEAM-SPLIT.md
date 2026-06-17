# 算法优化三人分工

## 分工总览

| | 负责人 | 方向 | 项目数 | 总工作量 |
|---|--------|------|--------|---------|
| A | **检索与知识工程** | RAG 召回+切分+HNSW+窗口 | 4 | 中 |
| B | **诊断与代码分析** | 误区诊断+AST+提示决策 | 3 | 中 |
| C | **质量与系统优化** | 回复评分+画像+推荐+路由 | 4 | 中 |

---

## A：检索与知识工程（RAG 全线优化）

| # | 任务 | 说明 | 工作量 |
|---|------|------|--------|
| 1 | RAG 检索 Recall | 接入 `reranker.py` LLM 重排序 + 混合检索权重调优 | 中 |
| 3 | Chunk 切分质量 | Semantic Chunking + 统一 Token 窗口（256/512）+ 重叠窗口 | 中 |
| 4 | HNSW 参数调优 | Grid Search (M, ef_search)，画 Recall vs Latency 曲线 | 小 |
| 9 | 上下文窗口管理 | 动态截断+RAG 压缩为摘要+Token 统计 | 小 |

**核心交付**：RAG Recall@5 从未知→70%+，构建 30 题 Ground Truth

**关键文件**：`rag_service.py`, `reranker.py`, `splitter.py`, `vector_store.py`, `tutor_service.py`

---

## B：诊断与代码分析（核心算法深化）

| # | 任务 | 说明 | 工作量 |
|---|------|------|--------|
| 2 | 误区诊断准确率 | 扩展 50 例测试集，Per-class F1 统计 | 中 |
| 10 | AST 代码分析 | `ast.parse()` 替代纯正则+类型推断+正则+AST 双通道 | 中 |
| 5 | 提示升级决策 | 每种 M 独立升级曲线+修正速度信号+行为 Decision Tree | 中 |

**核心交付**：诊断精确匹配率 55%→85%+，50 例测试集

**关键文件**：`misconception_service.py`, `pedagogy_service.py`, `misconceptions.json`, `v2_test_cases.json`

---

## C：质量与系统优化（LLM 工程+画像）

| # | 任务 | 说明 | 工作量 |
|---|------|------|--------|
| 6 | 回复评分一致性 | Multi-Judge（3 次评分取中位数）+细化 rubric+30 例人工 Anchor | 小 |
| 7 | 画像预测能力 | 时间衰减+误区转移矩阵+Hint Dependency 量化 | 小 |
| 8 | 练习推荐 | Content-Based 向量推荐+难度匹配 | 中 |
| 11 | 多模型路由 | flash→简单问答, pro→复杂诊断+代码生成，50 例对比测试 | 小 |

**核心交付**：评分一致性 Kappa>0.7，推荐完成率提升可测，成本降低 40%

**关键文件**：`pedagogy_service.py`, `profile_service.py`, `exercise_service.py`, `llm_service.py`

---

## 协作接口（避免冲突）

| 接口 | A→B | B→C | A→C |
|------|-----|-----|------|
| 共享文件 | `tutor_service.py` | `pedagogy_service.py` | 无直接冲突 |
| 协调点 | A 改 Prompt 长度→通知 C 测 Token 效率 | B 改策略→通知 C 调评分 rubric | A 的 RAG 输出→C 的推荐输入 |

**规则**：改同一个文件前在群说一声，优先改自己负责的部分，跨模块调用只加参数不改签名。
