# PyTutor 算法优化 — 主计划

---

## 一、总览

三人协作，11 项算法优化，用开关隔离法保证独立开发互不影响。

| 角色 | 负责方向 | 项目数 |
|------|---------|--------|
| **A** | 检索与知识工程 | 4 |
| **B** | 诊断与代码分析 | 3 |
| **C** | 质量与系统优化 | 4 |

---

## 二、任务分配

### A：检索与知识工程

| # | 任务 | 核心指标 | 工作量 |
|---|------|---------|--------|
| 1 | RAG LLM 重排序接入 | Recall@K | 小 |
| 2 | 混合检索权重调优 | Recall@K | 中 |
| 3 | Semantic Chunking | 切分语义纯度 | 中 |
| 4 | 统一 Token 窗口 + 重叠 | 检索 Recall | 小 |
| 5 | HNSW 参数调优 | QPS vs Recall | 小 |
| 6 | 上下文动态截断 + RAG 压缩 | Token 效率 | 小 |

**关键文件**：`rag_service.py`, `reranker.py`, `splitter.py`, `vector_store.py`, `tutor_service.py`

### B：诊断与代码分析

| # | 任务 | 核心指标 | 工作量 |
|---|------|---------|--------|
| 1 | AST 代码分析替代纯正则 | 诊断准确率 | 中 |
| 2 | 扩展 50 例测试集，Per-class F1 | 每类 F1 | 中 |
| 3 | 每种 M 独立提示升级曲线 | 修正速度 | 小 |

**关键文件**：`misconception_service.py`, `pedagogy_service.py`（`select_strategy`）, `misconceptions.json`

### C：质量与系统优化

| # | 任务 | 核心指标 | 工作量 |
|---|------|---------|--------|
| 1 | Multi-Judge 评分 | 评分一致性 | 小 |
| 2 | Rubric 细化 | 评分方差 | 小 |
| 3 | 画像时间衰减 + 转移矩阵 | 弱项识别准确率 | 小 |
| 4 | Hint Dependency 量化 | 画像精度 | 小 |
| 5 | Content-Based 练习推荐 | 推荐完成率 | 中 |
| 6 | 多模型路由 | 成本/延迟 | 小 |

**关键文件**：`pedagogy_service.py`（`verify_response`）, `profile_service.py`, `exercise_service.py`, `llm_service.py`

---

## 三、协作方案：开关隔离法

**核心原则**：三个人写的新代码用开关包裹，默认**关**，随时合 main 互不影响。最后逐一开开关验证。

### 3.1 开关定义

在 `backend/app/core/config.py` 加三个配置：

```python
# 算法优化功能开关（默认 false，三者独立）
ENABLE_RAG_RERANK: bool = Field(default=False)         # A 负责
ENABLE_AST_DIAGNOSIS: bool = Field(default=False)       # B 负责
ENABLE_MULTI_JUDGE: bool = Field(default=False)         # C 负责
```

### 3.2 开关用法示例

**A**：
```python
if settings.ENABLE_RAG_RERANK:
    reranked = await rerank_with_llm(candidates, query)  # 新
else:
    reranked = candidates[:top_k]  # 旧
```

**B**：
```python
if settings.ENABLE_AST_DIAGNOSIS:
    result = _ast_diagnose(code, stderr)  # 新
else:
    result = _rule_diagnose(code, stderr)  # 旧
```

**C**：
```python
if settings.ENABLE_MULTI_JUDGE:
    scores = [await _judge(msg) for _ in range(3)]
    score = sorted(scores)[1]  # 新
else:
    score = await _judge(msg)  # 旧
```

### 3.3 Git 流程

```bash
# 各自拉分支
git checkout -b feat/rag-opt      # A
git checkout -b feat/diag-opt     # B
git checkout -b feat/qual-opt     # C

# 开发完成后逐个合到 main（谁先完成谁先合，开关默认关不冲突）
git checkout main && git pull && git merge feat/rag-opt && git push
git checkout main && git pull && git merge feat/diag-opt && git push
git checkout main && git pull && git merge feat/qual-opt && git push
```

---

## 四、合并规则

### 4.1 文件归属

```
backend/app/
├── rag/                          ← A 的地盘
│   ├── retriever.py, reranker.py
│   ├── splitter.py, vector_store.py
├── services/
│   ├── rag_service.py            ← A
│   ├── misconception_service.py  ← B
│   ├── pedagogy_service.py       ← B+C（B:select_strategy, C:verify_response）
│   ├── tutor_service.py          ← A（截断部分）
│   ├── llm_service.py            ← C
│   ├── profile_service.py        ← C
│   └── exercise_service.py       ← C
└── data/
    └── misconceptions.json       ← B
```

### 4.2 接口契约

| 函数 | 输入 | 输出 | 谁可以改内部 | 谁依赖它 |
|------|------|------|------------|---------|
| `retrieve_context()` | query, top_k | RAGResult[] | A | B, C |
| `diagnose()` | code, stderr | DiagnosisDict | B | A, C |
| `verify_response()` | msg, level, mc_id | VerificationDict | C | - |
| `get_profile_summary()` | db, user_id | dict | C | 前端 |

**规则**：改内部实现可以，改输入参数/返回值字段 = 必须通知所有人。

### 4.3 共享文件处理

| 文件 | 被谁共享 | 怎么分 |
|------|---------|--------|
| `pedagogy_service.py` | B + C | B 只改 `select_strategy()`，C 只改 `verify_response()` |
| `tutor_service.py` | A + B | A 改截断参数，B 改 `SYSTEM_PROMPT` 常量 |
| `v2_test_cases.json` | A + B + C | 编号分区：C01-C30 A，C31-C50 B，C51-C70 C |

**共享文件操作规则**：改前先 pull，改后立刻 push。

---

## 五、验证流程

三人都合到 main 后，逐一开开关验证：

```bash
# 1. 全关 → 旧逻辑没被破坏
ENABLE_RAG_RERANK=false
ENABLE_AST_DIAGNOSIS=false
ENABLE_MULTI_JUDGE=false
pytest tests/ -v           # 必须全过

# 2. 单开 A → 测 RAG
ENABLE_RAG_RERANK=true
python evaluation/run_rag_eval.py

# 3. 单开 B → 测诊断
ENABLE_RAG_RERANK=false
ENABLE_AST_DIAGNOSIS=true
python evaluation/run_v2_eval.py

# 4. 单开 C → 测评分
ENABLE_AST_DIAGNOSIS=false
ENABLE_MULTI_JUDGE=true
# 手动测评分一致性

# 5. 全开 → 终验
ENABLE_RAG_RERANK=true
ENABLE_AST_DIAGNOSIS=true
ENABLE_MULTI_JUDGE=true
pytest tests/ -v           # 必须全过
npm run build              # 前端必须过
# 手动走完整流程：登录→对话→练习→画像
```

---

## 六、优化指标一览

| # | 优化项 | 当前值 | 目标值 | 负责人 |
|---|--------|--------|--------|--------|
| 1 | RAG Recall@5 | 未知 | 70%+ | A |
| 2 | 诊断精确匹配率 | 55% | 85%+ | B |
| 3 | 诊断 Per-class F1 | 未测 | 80%+ | B |
| 4 | 提示修正速度 | 未测 | 提升 30% | B |
| 5 | 回复评分一致性 Kappa | 0 | >0.7 | C |
| 6 | 弱项识别准确率 | 未测 | 可测 | C |
| 7 | 推荐完成率 | 未测 | 提升可测 | C |
| 8 | 多模型成本降低 | 0 | 40% | C |
| 9 | Semantic Chunk 纯度 | 未测 | 可测 | A |
| 10 | HNSW Recall/Latency | 默认 | 找到最优 | A |
| 11 | Token 效率 | 未测 | 节省 30% | A |
