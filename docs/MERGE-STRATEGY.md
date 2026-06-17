# 三人协作合并策略

## 原则：改实现不改接口

三个人改各自的代码，但**所有函数的输入参数和返回值格式不变**。只要输入输出一致，内部怎么改都不会影响别人。

---

## 模块边界（谁负责哪些文件）

```
backend/app/
├── rag/                          ← A 的地盘
│   ├── retriever.py
│   ├── reranker.py
│   ├── splitter.py
│   └── vector_store.py
│
├── services/
│   ├── rag_service.py            ← A 的地盘
│   ├── misconception_service.py  ← B 的地盘
│   ├── pedagogy_service.py       ← B+C 共享（B 改策略，C 改评分）
│   ├── tutor_service.py          ← A+B 共享（A 改截断，B 改 Prompt）
│   ├── llm_service.py            ← C 的地盘
│   ├── profile_service.py        ← C 的地盘
│   └── exercise_service.py       ← C 的地盘
│
├── data/
│   ├── misconceptions.json       ← B 的地盘
│   └── mc_exercises.py           ← B 的地盘
│
└── evaluation/
    └── v2_test_cases.json        ← 三人共用（各自扩展）
```

## 接口契约（必须遵守的约定）

### 1. `retrieve_context(query, top_k) → [RAGResult]`

```
输入：query: str, top_k: int
输出：RAGRetrievalResponse（results 列表）
```

A 可以改内部检索逻辑（LLM 重排序、权重调优），但**返回格式不能变**。

B 和 C 调用 `retrieve_context()` 获取检索结果，不关心内部怎么算的。

---

### 2. `diagnose(code, stderr) → DiagnosisDict`

```
输入：code: str, stderr: str
输出：{has_misconception: bool, misconception_id: str, confidence: float, evidence: str}
```

B 可以换成 AST 分析、增强规则，但**输出字段不能变**。

A 和 C 拿到 diagnosis 结果后直接用，不关心是正则还是 AST 算的。

---

### 3. `verify_response(message, hint_level, mc_id) → VerificationDict`

```
输入：message: str, hint_level: int, misconception_id: str
输出：{is_valid: bool, score: int, issues: list, needs_revision: bool}
```

C 可以改成 Multi-Judge、细化 Rubric，但**返回字段不能变**。

---

### 4. `get_profile_summary(db, user_id) → dict`

```
输入：db: AsyncSession, user_id: str
输出：{level, stats, weaknesses, ...}
```

C 可以加时间衰减、转移矩阵，但**返回字段只增不减**。

前端和其他服务依赖这个接口，**不能删已有字段**。

---

## 共享文件的"分片规则"

`pedagogy_service.py` 和 `tutor_service.py` 是共享文件。规则：

| 文件 | 区域 | 负责人 |
|------|------|--------|
| `pedagogy_service.py` | `select_strategy()` 函数 | B |
| `pedagogy_service.py` | `verify_response()` 函数 | C |
| `pedagogy_service.py` | `get_hint_prompt()` 函数 | B |
| `tutor_service.py` | `SYSTEM_PROMPT` 常量 | B |
| `tutor_service.py` | `calculate_hint_level()` 函数 | B |
| `tutor_service.py` | `generate_tutor_response()` 参数构建部分 | A（窗口截断） |

**操作规则**：改共享文件前，先拉最新的 main，改完后立刻 push。另一个人 pull 后再改。

---

## Git 分支策略

```
main ──────────────────────────────────────────
   \
    ├── opt/a-rag ──────────── (A 的改动)
    │       ↓ merge
    ├── opt/b-diagnosis ────── (B 的改动)
    │       ↓ merge
    └── opt/c-quality ──────── (C 的改动)
            ↓ merge
```

**合并顺序**：C → B → A（先合质量层，再合诊断层，最后合检索层）

理由：C 的改动影响最小（评分函数+画像字段），B 可能改诊断接口但输出不变，A 改检索最多但都在 RAG 模块内部。

**每次合完一个人**，跑一次 `pytest tests/ -v`，全部通过才能合下一个。

---

## 协作检查清单

合并前，每个人确认：

- [ ] 所有新增/修改的函数有 docstring
- [ ] 没有删除任何已有的公共函数参数（只能追加默认参数）
- [ ] `pytest tests/ -v` 全部通过
- [ ] 前端 `npm run build` 通过
- [ ] 本地跑一遍核心流程：登录 → AI 对话 → 练习提交 → 看画像

---

## 集成测试：最终的保障

三人都合完后，跑一次端到端验证：

```bash
# 1. 运行全部测试
pytest tests/ -v

# 2. 前端构建
cd frontend && npm run build

# 3. RAG 评估
python evaluation/run_v2_eval.py

# 4. 核心流程手动测试
# - 登录 → 发消息 → 看 AI 回复
# - 练习中心 → 故意写错 → 看诊断卡片
# - 打开学习画像 → 看数据更新
```

全部通过 = 合并成功。
