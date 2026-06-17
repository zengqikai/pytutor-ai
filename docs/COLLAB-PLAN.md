# 三人独立开发 + 一次合并方案

## 核心思路：开关隔离

每个人加一个**功能开关**（Feature Flag）。改完代码后，开关默认**关**，三个人的代码可以同时合进 main 互不影响。最后一起打开开关，跑测试验证。

---

## 第一步：三个人同时开工

### Git 操作

```bash
# 三个人各自从 main 拉自己的分支
git checkout main && git pull

# A
git checkout -b feat/rag-opt
# B  
git checkout -b feat/diag-opt
# C
git checkout -b feat/qual-opt
```

### 开关定义

在 `backend/app/core/config.py` 加三个配置：

```python
# 算法优化功能开关（默认关闭，三者独立）
ENABLE_RAG_RERANK: bool = Field(default=False)         # A 负责
ENABLE_AST_DIAGNOSIS: bool = Field(default=False)       # B 负责
ENABLE_MULTI_JUDGE: bool = Field(default=False)         # C 负责
```

每个人在自己的代码里用 `if settings.ENABLE_XXX:` 包裹新逻辑，**旧逻辑保留不动**。

---

## 第二步：各自开发

### A（检索优化）的开关用法

```python
# rag_service.py:retrieve_context()

if settings.ENABLE_RAG_RERANK:
    # A 的新代码：LLM 重排序
    reranked = await rerank_with_llm(candidates, query)
else:
    # 旧代码：直接截断
    reranked = candidates[:top_k]
```

### B（诊断优化）的开关用法

```python
# misconception_service.py:diagnose()

if settings.ENABLE_AST_DIAGNOSIS:
    # B 的新代码：AST 分析
    result = _ast_diagnose(code, stderr)
else:
    # 旧代码：正则匹配
    result = _rule_diagnose(code, stderr)
```

### C（评分优化）的开关用法

```python
# pedagogy_service.py:verify_response()

if settings.ENABLE_MULTI_JUDGE:
    # C 的新代码：3 次评分取中位数
    scores = [await _judge(msg) for _ in range(3)]
    score = sorted(scores)[1]
else:
    # 旧代码：单次评分
    score = await _judge(msg)
```

---

## 第三步：各自合并到 main

三个分支都可以直接合到 main——因为开关默认**关**，新代码在 main 上不会执行。

```bash
# A 先合
git checkout main && git merge feat/rag-opt && git push
# B 再合（可能有冲突，但只改自己那部分代码）
git checkout main && git pull && git merge feat/diag-opt && git push
# C 最后合
git checkout main && git pull && git merge feat/qual-opt && git push
```

每个人的改动互不影响：
- A 只改了 `rag_service.py`, `reranker.py`, `vector_store.py`
- B 只改了 `misconception_service.py`, `misconceptions.json`, `pedagogy_service.py` 的 `select_strategy()`
- C 只改了 `pedagogy_service.py` 的 `verify_response()`, `profile_service.py`, `llm_service.py`

---

## 第四步：集成验证

三个人都合到 main 后，在 `.env` 里逐一打开开关测试：

```bash
# 1. 先全关，跑基准测试
ENABLE_RAG_RERANK=false
ENABLE_AST_DIAGNOSIS=false
ENABLE_MULTI_JUDGE=false
pytest tests/ -v                    # 全部通过 = 旧逻辑没被破坏

# 2. 单独开 A
ENABLE_RAG_RERANK=true
python evaluation/run_rag_eval.py   # RAG Recall 对比

# 3. 单独开 B
ENABLE_RAG_RERANK=false
ENABLE_AST_DIAGNOSIS=true
python evaluation/run_v2_eval.py    # 诊断准确率对比

# 4. 单独开 C
ENABLE_AST_DIAGNOSIS=false
ENABLE_MULTI_JUDGE=true
# 手动测评分一致性

# 5. 全部打开
ENABLE_RAG_RERANK=true
ENABLE_AST_DIAGNOSIS=true
ENABLE_MULTI_JUDGE=true
pytest tests/ -v                    # 全部通过 = 无冲突
# 手动走完整流程
```

---

## 冲突预防表

| 冲突场景 | 预防方法 |
|---------|---------|
| 两人改了同一个函数 | 一个人改旧分支，另一个人在新分支里用 `if FLAG: 新逻辑 else: 旧逻辑` |
| `pedagogy_service.py` 被 B 和 C 同时改 | B 改 `select_strategy()`，C 改 `verify_response()`，两个函数独立 |
| `tutor_service.py` 被 A 和 B 同时改 | A 只改 L64 的 `[-20:]` 截断逻辑；B 改 `SYSTEM_PROMPT` 常量 |
| 测试集被多人扩展 | `v2_test_cases.json` 按编号分区：C01-C30 A 扩展，C31-C50 B 扩展，C51-C70 C 扩展 |

---

## 一句话总结

> 三个开关 = 三个人的代码可以**同时存在于 main 分支**，默认都不生效。谁测完谁打开，互不影响。
