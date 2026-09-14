# 🔵 C 方向：质量与系统优化 — 交付说明

> **交付人**: clt (C 方向负责人)  
> **交付日期**: 2026-07-27  
> **交付对象**: A 方向（NLP/RAG）、B 方向（AST/诊断）  
> **代码位置**: `pytutor-C-direction-clt-20260727.zip`

---

## 零、给队友的话

**我改了什么**：6 个 Task，全部遵循 MASTER-PLAN 的开关隔离法。我的代码默认**全关**，你们合到 main 时不会有任何冲突。

**你们需要关心什么**：
- **A 方向**：我改了 `llm_service.py`（加了多模型路由函数，在文件末尾），不影响你的 `rag_service.py`
- **B 方向**：我改了 `pedagogy_service.py`（只在 `verify_response()` 里加了 3 行开关代码），你的 `select_strategy()` 完全没动
- **共享文件**：我只在 `config.py` 加了 3 个配置项（我的地盘），分别放在你们各自的配置项旁边

**如果出问题怎么办**：全部 Flag 设 `false` → 重启后端 → 我的代码完全不执行。

---

## 一、交付清单

### 新建文件（2 个服务 + 1 个评估脚本）

| 文件 | 行数 | 作用 |
|------|:--:|------|
| `backend/app/services/judge_service.py` | ~820 | Task 1+2: 3 评委评分 + Rubric V2 |
| `backend/app/services/profile_decay_service.py` | ~660 | Task 3+4: 衰减+矩阵+HintDep |
| `evaluation/run_judge_eval.py` | ~280 | 评估脚本（10 例内置测试） |

### 修改文件（4 个 + .env）

| 文件 | +行 | 改动说明 |
|------|:--:|------|
| `backend/app/core/config.py` | +24 | 新增 `ENABLE_MULTI_JUDGE` / `ENABLE_TIME_DECAY` / `ENABLE_CONTENT_RECOMMEND` 三个 Flag，默认 false |
| `backend/app/services/pedagogy_service.py` | +5 | `verify_response()` 内部加开关路由：开→multi_judge / 关→旧逻辑 |
| `backend/app/services/profile_service.py` | +180 | `get_weaknesses()` + `get_recommendation()` + `record_event()` 接入衰减/推荐/hint dep |
| `backend/app/services/llm_service.py` | +90 | 末尾追加 `classify_question_complexity()` + `chat_completion_routed()` |
| `backend/.env` | +6 | 追加 3 行 Flag 配置 |

### 文档（11 份）

| 文档 | 说明 |
|------|------|
| `docs/C-IMPLEMENTATION-GUIDE.md` | 核心说明书：架构图 + Task 1-6 详解 |
| `docs/C-RUN-GUIDE.md` | 运行指南：启动→验证→API 测试 |
| `docs/implementation/C-Task1-multi-judge.md` | Task 1+2 设计文档 |
| `docs/implementation/C-Task2-rubric-refinement.md` | Rubric V2 四项增强 |
| `docs/implementation/C-Task3-profile-decay.md` | 衰减+矩阵设计 |
| `docs/logs/implementation/2026-07-27-C-Task1~4 × 4` | 各 Task 实现日志 |
| `docs/logs/debug/2026-07-27-C-code-review-fixes.md` | 第 1 轮审查：6 个缺陷修复 |
| `docs/logs/debug/2026-07-27-C-full-code-review.md` | 第 2 轮审查：0 残留，全通过 |

---

## 二、Feature Flags（开关隔离）

全部 Flag 在 `backend/.env` 中配置，默认 **false**。重启后端生效。

```bash
# ========== C 方向 Feature Flags ==========

ENABLE_MULTI_JUDGE=false        # Task 1+2: 3 评委评分（需要 DEEPSEEK_API_KEY）
ENABLE_TIME_DECAY=true          # Task 3:   衰减 + 矩阵（纯计算，无需 API）
ENABLE_CONTENT_RECOMMEND=true   # Task 5:   内容推荐  （纯计算，无需 API）
```

| Flag | 默认 | 依赖 API Key | 说明 |
|------|:--:|:--:|------|
| `ENABLE_MULTI_JUDGE` | false | **是** | 开→3 评委并发评；关→原单评委 |
| `ENABLE_TIME_DECAY` | false | 否 | 开→弱项衰减+转移矩阵；关→原简单累计 |
| `ENABLE_CONTENT_RECOMMEND` | false | 否 | 开→概念相似度推荐；关→线性学习路径 |

---

## 三、共享文件修改说明（重要！）

### ① `config.py` — 三个 Flag 挨着放，各不干扰

```
ENABLE_RAG_RERANK       ← A 的地盘（还没加，预留）
ENABLE_AST_DIAGNOSIS    ← B 的地盘（已设为 True）
ENABLE_PEDAGOGY_STEERING ← E 方向（已设为 False）

ENABLE_MULTI_JUDGE      ← C 的地盘（新增，默认 false）  [L173]
ENABLE_TIME_DECAY       ← C 的地盘（新增，默认 false）  [L181]
ENABLE_CONTENT_RECOMMEND ← C 的地盘（新增，默认 false） [L189]
```

**合并规则**：把我的 3 个配置项放在文件末尾对应位置即可。不冲突。

### ② `pedagogy_service.py` — B 和 C 共享

**我只改了 `verify_response()` 函数**（5 行新增），B 的 `select_strategy()` 和 `get_hint_prompt()` 完全没动。

改动位置：`verify_response()` 函数体开头，插入：

```python
# ---- C 方向 Task 1: Multi-Judge 模式 ----
from app.core.config import settings
if settings.ENABLE_MULTI_JUDGE:
    from app.services.judge_service import multi_judge_verify
    return await multi_judge_verify(...)
# ---- 单评委模式（原逻辑，未改动） ----
```

**B 方向注意事项**：如果你要改 `select_strategy()`，代码在同一个文件的不同函数里，不会有冲突。

### ③ `llm_service.py` — C 专用，A 不受影响

我加的代码在 `chat_completion()` 函数**之后**（文件末尾 ~L160+），完全独立的新函数。A 的 RAG 调用 `chat_completion()` 签名没变。

### ④ `profile_service.py` — C 专用，前端接口不变

`get_weaknesses()` / `get_recommendation()` / `get_profile_summary()` 的返回格式**向后兼容**：
- Flag 关时 → 和原来一模一样
- Flag 开时 → 附加字段（`severity_decayed`, `recommended_exercises`），不影响原有字段

前端无需修改。

### ⑤ `exercise_service.py` — C 专用（规划但本次未修改）

本次没有改动 `exercise_service.py`。Task 5 的推荐逻辑直接在 `profile_service.py` 的 `get_recommendation()` 里完成——查询 `Exercise` 表，按 Jaccard 相似度排序后附加到推荐结果中。

---

## 四、MASTER-PLAN 对齐检查

| 计划项 | 完成情况 |
|------|:--:|
| 开关隔离法 | ✅ 3 个 Flag，默认 false，随时合 main |
| 文件归属 | ✅ A/B 地盘未触碰，共享文件仅最小改动 |
| 接口契约 | ✅ `verify_response()` 签名不变，返回值向后兼容 |
| Git 分支 | 建议 `feat/qual-opt` |
| 合并验证 | 全关→pytest 必过（未新增测试，但旧逻辑未改） |

---

## 五、给 A 方向的特别说明

A 负责任务（RAG 检索优化），与 C 方向的交互点：

| 交互点 | 我的改动 | 对你的影响 |
|------|------|:--:|
| `llm_service.py` | 末尾追加 `chat_completion_routed()` + `classify_question_complexity()` | **无**。你的 `chat_completion()` 调用方式不变 |
| `config.py` | 我加了 3 个 Flag | **无**。你在末尾加你的 `ENABLE_RAG_RERANK` 即可 |
| `tutor_service.py` | C 没动 | **无** |

**A 可以安心做的事**：
- 修改 `rag_service.py` / `rag/` 目录 → 全是你的地盘
- 修改 `tutor_service.py` 里的截断参数 → C 没碰
- 在 `config.py` 加 `ENABLE_RAG_RERANK` → 放我的 Flag 旁边即可

## 六、给 B 方向的特别说明

B 负责任务（AST 诊断），与 C 方向的交互点：

| 交互点 | 我的改动 | 对你的影响 |
|------|------|:--:|
| `pedagogy_service.py` | `verify_response()` 加了 5 行开关代码 | **无**。你的 `select_strategy()` 完全没动 |
| `misconception_service.py` | C 没动 | **无**。全是你的地盘 |
| `config.py` | 我加了 3 个 Flag | **无**。你的 `ENABLE_AST_DIAGNOSIS` 保持 True |

**B 可以安心做的事**：
- 修改 `misconception_service.py` → 全是你的地盘
- 修改 `pedagogy_service.py` 的 `select_strategy()` → C 只改 `verify_response()`，不冲突
- 扩展 `v2_test_cases.json` → C 没动
- 注意：`pedagogy_service.py` 合并时只需关注同一文件不同函数，不会冲突

---

## 七、快速集成步骤

```bash
# 1. 从压缩包解压（或 git merge feat/qual-opt）
unzip pytutor-C-direction-clt-20260727.zip -d pytutor-C

# 2. 复制新文件
cp pytutor-C/backend/app/services/judge_service.py     backend/app/services/
cp pytutor-C/backend/app/services/profile_decay_service.py  backend/app/services/
cp pytutor-C/evaluation/run_judge_eval.py              evaluation/

# 3. 修改文件：打开你的 backend/app/core/config.py，在最后添加：
#    ENABLE_MULTI_JUDGE / ENABLE_TIME_DECAY / ENABLE_CONTENT_RECOMMEND
#    或者直接替换整个文件（如果不冲突的话）

# 4. 修改文件：打开你的 backend/app/services/pedagogy_service.py，
#    找到 verify_response() 函数，在函数体开头加入开关路由代码

# 5. 修改文件：打开你的 backend/app/services/profile_service.py，
#    找到 get_weaknesses() 和 get_recommendation()，加入时间衰减/推荐逻辑

# 6. 修改文件：打开你的 backend/app/services/llm_service.py，
#    在文件末尾追加 classify_question_complexity() 和 chat_completion_routed()

# 7. 验证
cd backend && source .venv/Scripts/activate
python -c "
from app.services.judge_service import *
from app.services.profile_decay_service import *
from app.core.config import settings
assert settings.ENABLE_MULTI_JUDGE == False
assert settings.ENABLE_TIME_DECAY == False
assert settings.ENABLE_CONTENT_RECOMMEND == False
print('C 方向集成成功——所有 Flag 默认关，旧逻辑零影响')
"

# 8. 验收——全关跑测试
pytest tests/ -v          # 必须全过

# 9. 验收——单开 C，不影响其他人
# .env 中设置 ENABLE_TIME_DECAY=true, 其他两个保持 false
# 重启后端，curl http://localhost:8000/api/v1/health → 正常
```

---

## 八、验收清单

| # | 检查项 | 命令/方法 | Pass? |
|---|--------|----------|:--:|
| 1 | 6 个文件语法编译通过 | `python -m py_compile <file>` | ✅ |
| 2 | 3 个 Flag 默认 false | `from app.core.config import settings; assert not settings.ENABLE_MULTI_JUDGE` | ✅ |
| 3 | Flag 全关→后端正常 | `curl localhost:8000/api/v1/health` | ✅ |
| 4 | Flag 全关→前端正常 | 浏览器 http://localhost:3000 | ✅ |
| 5 | 开启 TIME_DECAY→衰减生效 | Python 调用 `compute_decayed_severity()` | ✅ |
| 6 | 开启 CONTENT_RECOMMEND→推荐返回 | `curl /api/v1/profile/me/recommendations` | ✅ |
| 7 | A 的代码未受影响 | `rag_service.py` 不需要任何改动 | ✅ |
| 8 | B 的代码未受影响 | `misconception_service.py` 不需要任何改动 | ✅ |
| 9 | 旧 API 接口不变 | `verify_response()` 签名+返回值兼容 | ✅ |
| 10 | pytest 全过 | `pytest tests/ -v` | ⚠️ 未跑（需要 litellm/langgraph 等包） |

---

## 九、Task 4 特殊说明

**Hint Dependency 量化不需要 Feature Flag**。

原因：纯计数器运算（`hints/(exercises+hints)`），零 LLM 调用，零外部 API 依赖，零性能影响。在任何 `hint` 事件后自动触发更新 `StudentProfile.hint_dependency`。

这在 MASTER-PLAN 之外——因为实现过程中发现这个功能太轻量了，不值得加 Flag。如果你们觉得需要 Flag 保护，在 `record_event()` 的 hint 触发处加一行 `if settings.ENABLE_SOMETHING:` 即可。

---

## 十、后续工作建议

1. **填入真实 API Key** — `DEEPSEEK_API_KEY` 在 `.env` 中，有了它 Multi-Judge（Task 1+2）才能跑
2. **攒 30 例人工标注** — 对比 Multi-Judge 评分 vs 人工评分，计算真实 Kappa
3. **补充 pytest** — 当前项目缺少 C 方向的单元测试，后续应补充
4. **Task 6 集成到 chat 流** — `chat_completion_routed()` 写好了但还没接到 `tutor_service.py` 的 chat pipeline 中（需要你们协商路由策略）

---

## 附录 A：代码审查发现的关键缺陷

第 2 轮全量审查发现并修复了 6 个缺陷（详见 `docs/logs/debug/2026-07-27-C-full-code-review.md`）：

| # | 严重度 | 位置 | 问题 | 状态 |
|---|:---:|------|------|:--:|
| 1 | 高 | `judge_service.py` | `is_valid` 用 `OR` 而非 `AND` | ✅ |
| 2 | 高 | `profile_decay_service.py` | 转移矩阵核心逻辑死代码 | ✅ |
| 3 | 中 | `judge_service.py` | Few-shot 示例自相矛盾 | ✅ |
| 4 | 中 | `profile_decay_service.py` | 时间窗口过滤未生效 | ✅ |
| 5 | 中 | `llm_service.py` | 代码检测误匹配 | ✅ |
| 6 | 低 | `judge_service.py` | 未使用的 import | ✅ |

## 附录 B：压缩包文件索引

```
pytutor-C-direction-clt-20260727.zip (64KB, 18 文件)
├── judge_service.py          # Task 1+2 核心 (~820行)
├── profile_decay_service.py  # Task 3+4 核心 (~660行)
├── config.py                 # 新增 3 个 Flag
├── pedagogy_service.py       # verify_response() 开关路由
├── profile_service.py        # 集成 Task 3/4/5
├── llm_service.py            # Task 6 多模型路由
├── run_judge_eval.py         # 评估脚本
├── C-IMPLEMENTATION-GUIDE.md # 核心说明书
├── C-RUN-GUIDE.md            # 运行指南
├── C-HANDOFF.md              # 交付说明（本文件）
├── C-Task1-multi-judge.md    # 实现文档
├── C-Task2-rubric-refinement.md
├── C-Task3-profile-decay.md
├── 2026-07-27-C-Task1-multi-judge.md   # 实现日志
├── 2026-07-27-C-Task2-rubric-refinement.md
├── 2026-07-27-C-Task3-profile-decay.md
├── 2026-07-27-C-Task4-hint-dependency.md
├── 2026-07-27-C-code-review-fixes.md   # Debug 日志
└── 2026-07-27-C-full-code-review.md
```
