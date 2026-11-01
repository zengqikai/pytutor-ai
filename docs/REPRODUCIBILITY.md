# 可复现配置与运行说明

> 对应完善任务清单 **01（固定基线并建立可复现配置）** 与 **09（启动、迁移与 CI）**。
> 本文只记录"怎么复现"，结果口径与限制写在 §6、§7。

---

## 1. 代码基线

| 项 | 值 |
|----|----|
| 基线提交 | `59c7444`（`fix: 对话 500 修复 + Multi-Judge JSON 健壮性 + 队友文档归档`） |
| 在此基础上 | 未提交的完善改动（清单 02–13 的修复） |
| Python | 3.12（CI 与本地一致；最低 3.11） |
| Node | 20+ |

查看当前实际运行的是哪份代码：

```bash
git rev-parse --short HEAD
git status --short        # 有改动说明跑的不是纯基线
```

---

## 2. 安装入口（唯一来源）

| 层 | 清单文件 | 安装命令 |
|----|----------|----------|
| 后端 | `backend/pyproject.toml`（依赖版本） + `backend/requirements.txt`（部署用平铺列表） | `cd backend && pip install -e .` |
| 前端 | `frontend/package.json` | `cd frontend && npm install` |
| 根目录 | `package.json` | **不再声明依赖**，只转发到 `frontend/`（`npm run build` = `npm --prefix frontend run build`） |

根目录原先那份 `package.json` 重复声明了一组与 `frontend/package.json` 版本不一致的依赖
（如 `react-markdown` 10 vs 9），会让根目录多装一份 `node_modules`。现在根目录
`package.json` 无依赖，`package-lock.json` 已删除；前端依赖以 `frontend/package.json` 为准。

一键安装：`./setup.sh`（Linux/macOS）或 `setup.bat`（Windows），内部就是上面两条命令。

---

## 3. 配置与功能开关

复制 `backend/.env.example` 为 `backend/.env`，至少填 `DEEPSEEK_API_KEY`；
RAG 语义检索还需要 `DASHSCOPE_API_KEY`（缺失时自动降级为 TF-IDF，不阻塞对话）。

功能开关在 `backend/app/core/config.py` 定义，`.env` 覆盖。**代码默认全关**，
`backend/.env` 中的演示配置打开了三项：

| 开关 | 代码默认 | 演示配置 | 作用 | 验证方式 |
|------|----------|----------|------|----------|
| `ENABLE_AST_DIAGNOSIS` | 关 | **开** | AST 结构诊断替代纯正则 | `evaluation/run_v2_eval.py --mode ast-only` + `tests/test_ast_*.py` |
| `ENABLE_PEDAGOGY_STEERING` | 关 | 关 | 教学意图转移图 + 误区锚定 prompt | `tests/test_e_direction.py`（离线） |
| `ENABLE_MULTI_JUDGE` | 关 | 关 | 3 评委 Rubric V2 评分 | `evaluation/run_judge_eval.py`（需 key，付费） |
| `ENABLE_TIME_DECAY` | 关 | **开** | 画像时间衰减 + 转移矩阵 | `tests/test_profile_decay.py` |
| `ENABLE_CONTENT_RECOMMEND` | 关 | **开** | Content-Based 练习推荐 | `tests/test_profile_decay.py` |
| `ENABLE_MULTI_MODEL_ROUTING` | 关 | 关 | 简单/复杂问题分流模型 | 未单独评测 |
| `ENABLE_RAG_RERANK` | 关 | 关 | RAG LLM 重排序 | 未单独评测 |
| `ENABLE_HYBRID_WEIGHTS` | 关 | 关 | 向量 + TF-IDF 加权融合 | 未单独评测 |
| `ENABLE_TOKEN_CHUNKING` | 关 | 关 | token 窗口 + 重叠切块 | `tests/test_rag_optimization.py`（离线） |
| `ENABLE_CONTEXT_COMPRESSION` | 关 | 关 | 上下文截断压缩 | `tests/test_rag_optimization.py`（离线） |

沙箱边界（`backend/app/core/config.py`）：

| 变量 | 默认 | 说明 |
|------|------|------|
| `SANDBOX_MODE` | `auto` | `docker` / `subprocess` / `auto` |
| `SANDBOX_REQUIRE_ISOLATION` | `false` | 为 true 时禁止降级到宿主进程 |
| `APP_ENV` | `development` | `production` 等价于强制隔离；Docker 不可用则拒绝执行学生代码（`status="unavailable"`），不判题、不发奖励 |

判断当前实际走了哪条路径：启动日志里的 `tfidf_index_rebuilt`、`embedding_service_ready`、
`schema_managed_by_alembic`；每次对话的 `message.metadata_json` 里有 `strategy`、
`strategy_source`（`steering_graph` 或规则）、`misconception_id`、`hint_level`。

---

## 4. 数据库：路径、首次启动与升级

### 路径规则（重要）

`DATABASE_URL` 是**相对路径**（默认 `sqlite+aiosqlite:///./ai_tutor.db`），
解析基准是**进程工作目录**。因此：

```bash
cd backend && uvicorn app.main:app          # → backend/ai_tutor.db
cd ..       && uvicorn app.main:app         # → 仓库根目录/ai_tutor.db（另一份空库）
```

评测脚本同理，必须在 `backend/` 下运行：

```bash
cd backend && python ../evaluation/run_rag_eval.py
```

### 首次启动（空库）

lifespan 顺序固定为：建表（或确认迁移已管） → 种子误区 M1–M8 → **知识库为空则导入** → 重建 TF-IDF → 初始化 embedding。

所以空库第一次启动即可对话并检索，不需要先手动跑 `scripts/seed_knowledge.py`。
该脚本仍然保留，用于手动补种（重复执行会产生重复文档）。

`APP_ENV=production` 时**不会**调用 `create_all()`，只记录 `schema_managed_by_alembic`，
建表必须由 `alembic upgrade head` 完成。

### 升级已有库

```bash
cd backend
alembic current            # 当前版本
alembic upgrade head       # 升级
```

已有库不会被 `create_all()` 加列，新增字段一律走迁移。当前 head 是
`d3e4f5a6b7c8`（补 2.0 画像字段），迁移均为幂等（先 `inspect` 再建/加列）。

### 备份与恢复

```bash
cd backend
cp ai_tutor.db "ai_tutor.db.bak-$(date +%Y%m%d%H%M%S)"
```

恢复：停服务 → 用备份覆盖 `ai_tutor.db` → `alembic upgrade head`（备份可能落后几个版本）。

---

## 5. 知识库与测试集版本

| 文件 | 条目 | sha256 前 16 位 | 说明 |
|------|------|------------------|------|
| `app/rag/seed_data.py`（知识库正文） | 10 篇 / 41 chunk | 随代码 | RAG 语料；chunk 数见启动日志 `tfidf_index_rebuilt` |
| `evaluation/v2_test_cases.json` | 47 正例 + 22 干净代码 | `62569c1f2343e557` | 误区诊断评测集 |
| `evaluation/clean_code_cases.json` | 22 | `967bffb95df52555` | 干净代码误报集 |
| `evaluation/v2_holdout_cases.json` | 30（8 类全覆盖） | `8d3e008fdb3c76b7` | 留出集：评测前单独编写，未用于调规则 |
| `evaluation/holdout_clean_cases.json` | 15 | `a4a69607f88c5a3e` | 留出集的干净代码对照 |
| `evaluation/rag_golden.json` | 30 可答 + 5 无答案查询 | `e12dd15fc2fd54e7` | RAG 相关性标注；无答案查询单独统计 |
| `research/faithfulness/dataset_seed.json` | 10 条种子 | `8c8e786623216b92` | 忠实度实验种子（待扩到 170） |
| `evaluation/golden_dataset.json` | 10 | `9d18ab5eaed9c7c9` | 早期裁判/回复数据集 |
| `research/faithfulness/results_real_deepseek_v2_run{1,2}.json` | 10×2 ×2 次 | 见文件 | 当前主结果：真实模型 + `rules_v2` 抽取器（含逐条解释、逐断言判定、token 用量） |
| `research/faithfulness/results_real_deepseek_run{1,2}.json` | 10×2 ×2 次 | 见文件 | v1 历史结果（抽取器未清理 Markdown 噪声），仅作对照 |

> 这些哈希是对当前工作区文件算的；改动数据集后请重算，并在结果文件里记录。

---

## 6. 评测命令与当前数字

全部在 `backend/` 目录下运行（相对路径依赖）。

```bash
cd backend

# 1) 误区诊断（离线，无需 key）
python ../evaluation/run_v2_eval.py --mode ast-only

# 2) RAG 检索（三种模式各跑一次；结果分别写到 rag_eval_results_{mode}.json）
python ../evaluation/run_rag_eval.py --mode tfidf
python ../evaluation/run_rag_eval.py --mode vector    # 需要 DASHSCOPE_API_KEY
python ../evaluation/run_rag_eval.py --mode hybrid

# 3) Multi-Judge（需 DEEPSEEK_API_KEY，付费）
python ../evaluation/run_judge_eval.py

# 4) 忠实度核验（在 research/faithfulness 目录下运行）
cd ../research/faithfulness
python run_experiment.py --demo                       # 桩模型，离线
python run_experiment.py --out results_real.json      # 真实模型，读 backend/.env
```

跑完上面的实验后，汇总成一张表（不重新调用 API，任意目录可运行）：

```bash
python evaluation/build_results_summary.py    # → evaluation/results_summary.csv
```

当前结果（`evaluation/*_results.json`）：

| 评测 | 数据 | 结果 | 口径提醒 |
|------|------|------|----------|
| AST 误区诊断（同集） | 47 正例 + 22 干净 | exact match 1.000，macro-F1 1.000，干净代码误报 0/22 | 规则与用例同一批，**属于同集验证，不是留出集估计** |
| AST 误区诊断（留出集） | 30 正例 + 15 干净 | exact match 0.833（25/30），macro-F1 0.883，干净代码误报 0/15 | 评测前单独编写、未据此调规则；**单作者编写，不是双人标注**；M5 recall 0.25、M6 recall 0.50，其余 1.00 |
| RAG · TF-IDF | 30 可答查询 / 41 chunk，覆盖 100% | Hit@3 90.0%、Recall@3 29.9%、MRR 0.900；Hit@5 90.0%、Recall@5 40.7%、MRR 0.900；Top-5 上下文 251 token（最大 390） | 30 条查询仍是单作者小样本，只能作 smoke 基线；5 条无答案查询仍返回结果（Top-1 分数 1.0），检索器没有拒答能力；token 为 `splitter.estimate_tokens` 估算值，不是分词器精确值 |
| RAG · 向量 | 同上 | Hit@3 90.0%、Recall@3 36.1%、MRR 0.883；Hit@5 93.3%、Recall@5 50.1%、MRR 0.890；Top-5 上下文 315 token（最大 455） | 平均延迟 ~636 ms（含 embedding API）；无答案查询 Top-1 相似度 0.498，同样没有拒答 |
| RAG · Hybrid | 同上 | 与向量完全一致（Hit@5 93.3%、Recall@5 50.1%、MRR 0.890）；Top-5 上下文 315 token | `ENABLE_HYBRID_WEIGHTS=false` 时 Hybrid = 向量优先拼接，Top-5 全被向量占满，**这不是融合有效性的证据** |
| Multi-Judge | 10 案例 | 均分 2.4、修订率 9/10、平均 Fleiss κ 0.405 | 无人工对照，κ 只说明评委之间一致 |
| 忠实度 C1/C2（rules_v2） | 10 条种子（5 positive / 5 hard_negative），重复 2 次 | run1：C1 0.683 / C2 0.647；run2：C1 0.667 / C2 0.650；配对差 −0.127（CI [−0.56,0.21]）、−0.090（CI [−0.19,0.00]） | 真实 `deepseek-chat`、温度 0.3、各 20 次调用、0 失败；抽取器已清理 Markdown/代码块噪声；**C2 两次都未优于 C1，CI 含 0**，不能宣称证据注入有效，详见 [research/faithfulness/RESULTS.md](../research/faithfulness/RESULTS.md) |

同一批数字的机器可读汇总：[`evaluation/results_summary.csv`](../evaluation/results_summary.csv)（由 `build_results_summary.py` 生成）。
可视化：[`docs/figures/results-overview.svg`](figures/results-overview.svg)（深色版 `results-overview-dark.svg`），
图注、表格视图与配色校验记录见 [`docs/figures/README.md`](figures/README.md)。

---

## 7. 状态用词（写论文/答辩时请严格区分）

- **已实现**：代码在仓库里，有单测或可直接运行。
- **已启用**：当前演示配置（`backend/.env`）打开，界面/接口实际会走这条路径。
- **已验证**：有可复现的实验结果文件，且说明了数据与口径。

按此口径的现状：

| 能力 | 已实现 | 已启用 | 已验证 |
|------|--------|--------|--------|
| AST 误区诊断 | ✅ | ✅ | ⚠️ 同集 1.000；单作者留出集 0.833（需双人标注） |
| 教学策略转移图 | ✅ | ❌ | ⚠️ 仅单测 |
| Multi-Judge | ✅ | ❌ | ⚠️ 无人工对照 |
| 画像衰减 / 推荐 | ✅ | ✅ | ⚠️ 仅单测 |
| RAG 三路检索 | ✅ | ✅（tfidf+vector） | ⚠️ 30 条单作者查询 |
| 忠实度核验器 | ✅ | —（研究脚本） | ✅ 真实模型 10 条试跑（C2 未优于 C1，见 §6） |
| 统一沙箱边界 | ✅ | ✅ | ✅ 单测覆盖 4 种模式 |
| 判题/奖励幂等 | ✅ | ✅ | ✅ 单测 + 服务端事件核对 |

**尚缺证据、不可宣称的结论**：学习增益、教师认可度、概率校准、全量 170 条数据集上的效果。
对应清单任务 11、14、15，需要人工标注与真实参与者。

---

## 8. CI

`.github/workflows/ci.yml`：

1. 后端：Python 3.12 → `pip install -r backend/requirements.txt`（精确版本）→
   `compileall` 语法检查 → `ruff check app tests --select E9,F63,F7,F82`（只拦未定义名、
   重复定义、语法等真错误，不拦风格）→ 空库 `alembic upgrade head` 并断言
   `student_profiles` 的四个画像字段存在 → `pytest tests/ -q --cov=app --cov-fail-under=40`
   （`pyproject.toml` 的 `addopts` 默认排除 `integration` 与 `llm` 标记，无需外部服务）
2. 前端：Node 20 → `npm ci --legacy-peer-deps` → `npm run build`

离线测试覆盖 AST 诊断、沙箱边界、权限、Multi-Judge 失败处理、RAG 优化、忠实度核验器、
入门诊断落库、知识库自动导入、JWT/密码注册登录、限流中间件、流式入口 501。集成测试（`tests/test_api.py`）需要先起服务，
用 `-m integration` 单独跑；它们通过 HTTP 访问服务端，请让服务端指向一个专用库：

```bash
cd backend
DATABASE_URL=sqlite+aiosqlite:///./ai_tutor_test.db uvicorn app.main:app --port 8000
# 另一个终端
cd backend && python -m pytest tests/ -m integration -q
```

单元测试不碰开发库：需要数据库的用例在 `tmp_path` 下自建临时 SQLite 文件。
