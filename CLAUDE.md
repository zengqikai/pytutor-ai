# 识图能力

遇到图片时，**不要用 Read 工具**，改用 vision.js：

```
node vision.js "<图片路径>" "用中文描述这张图片"
```

## 触发场景

- 用户发送图片（消息中出现图片路径或 ["Saved attachments:"]）
- 用户要求分析、描述、识别图片内容
- 看到 `[Unsupported Image]` 标记时，主动询问用户图片是否已保存到本地

## 用法

```
# 本地文件
node vision.js screenshot.png "用中文描述这张图片的内容"

# 网络 URL
node vision.js --url https://example.com/img.jpg "这是什么"
```

## 配置

- 服务：阿里云百炼千问 `qwen-vl-max`
- Key 已配置在项目 .env 中

---

# RAG / Embedding 架构

## 检索链路

```
用户问题
  → DashScope text-embedding-v3 API (语义向量, 1024维)
  → ChromaDB (余弦相似度检索)
  + TF-IDF 关键词检索 (内存, 服务重启自动重建)
  → 合并去重 (向量优先)
  → 注入 System Prompt → LLM 生成回复
```

## Embedding 服务

- 服务商：阿里云百炼 DashScope（OpenAI 兼容接口）
- 模型：`text-embedding-v3`（1024 维，中文 SOTA）
- Key：`DASHSCOPE_API_KEY`，配置在项目根目录 `.env`
- 接口：`POST https://dashscope.aliyuncs.com/compatible-mode/v1/embeddings`
- 限制：每批最多 10 条文本
- 成本：~¥0.0007/千token

## 降级策略（三层防护）

1. DashScope API 正常 → 语义向量 + TF-IDF 混合检索
2. DashScope API 失败 → 自动降级到纯 TF-IDF 检索
3. TF-IDF 也失败 → 无 RAG 模式（基础对话照样正常）

## 配置项

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DASHSCOPE_API_KEY` | - | 阿里云百炼 API Key（必填） |
| `EMBEDDING_MODEL` | `text-embedding-v3` | Embedding 模型 |
| `DASHSCOPE_BASE_URL` | `https://dashscope.aliyuncs.com/compatible-mode/v1` | API 端点 |

## 常见问题

### AI 聊天卡住/超时
- 先检查 `DASHSCOPE_API_KEY` 是否正确配置
- 检查 ChromaDB collection 是否有数据（`vector_store.get_collection().count()`）
- 如果没有数据：`python -c "import asyncio; from app.database.session import AsyncSessionFactory; from app.services.rag_service import rebuild_index; ..."`
- 如果 API 不可达：自动降级到 TF-IDF，不影响聊天

### 重启后向量索引丢失
- TF-IDF 索引在 lifespan 启动时自动从 DB 重建
- ChromaDB 向量数据持久化在 `backend/chroma_db/` 目录
- 如果丢失：运行 `rebuild_index()` 重建

### 启动后误区/知识库种子没写入
- 先看 `uvicorn` 启动日志有没有被 `try/except` 吞掉的异常
- `app/main.py` 的 lifespan 里不要写局部 `from app.database.session import AsyncSessionFactory`：
  这会让该名字在整个函数内变成本地变量，前面的调用抛 `UnboundLocalError`，种子静默跳过
- CI 的 `ruff --select F823` 会拦住这类作用域错误

---

# 新手教程系统

## 架构

```
OnboardingModal（4 选项）
  → A: LessonPlayer（完整 7 课，从 Lesson 0A 开始）
  → B: LessonPlayer（跳过编辑器，从 Lesson 1 开始）
  → C: router.push("/exercises")
  → D: 留在 AI 对话页
```

## LessonPlayer 组件

- 左侧：AI Tutor 分步引导面板（教程文案 + 误区诊断卡片）
- 右侧：Code Lab（编辑器 + stdin 输入 + 运行 + 输出）
- 底部：进度条 + 下一课按钮
- 课程数据：`frontend/src/data/tutorial-data.ts`（7 课，新增课程只需加数据）
- 进度持久化：localStorage key = `pytutor_progress_{userId}`，按用户隔离

## 退出与恢复

- 右上角「暂时退出」按钮 → 弹窗确认 → 保存进度
- 右下角 🎓 浮动按钮：有进度直接续学，无进度弹选择窗

## 教程 stdin 支持

- LessonPlayer 和主页编辑器均支持 stdin 输入
- `codeAPI.submit(code, undefined, stdinInput)`

---

# PyTutor 2.0 — Misconception-Aware Tutoring

## 核心新增功能

1. **新手引导**：OnboardingModal（4 选项） + Lesson 0（9 步教程）
2. **误区诊断**：8 类 Python 初学者误区（M1-M8），规则匹配 + LLM 辅助
3. **教学策略**：7 种策略 + 5 级渐进提示（禁止首次给答案）
4. **学习画像增强**：weak_topics / recent_misconceptions / hint_dependency
5. **评估数据集**：evaluation/v2_test_cases.json（47 个误区正例，另有 22 条干净代码）

## 四入口行为

| 入口 | 行为 |
|------|------|
| A 零基础 | LessonPlayer 完整 7 课教程 |
| B 学过一点 | DiagnosticFlow 6 题诊断 → 按结果推荐补漏或练习 |
| C 会基础 | 跳转 `/exercises` 练习中心 |
| D 自由提问 | 留在 AI 对话页 |

## 误区分类（8 类）

| ID | 名称 | 典型模式 |
|----|------|----------|
| M1 | 赋值与比较混淆 | `if x = 3:` |
| M2 | 缩进理解错误 | if/for 后无缩进 |
| M3 | append 返回值误解 | `new = list.append(x)` |
| M4 | index/value 混淆 | `for i in list: list[i]` |
| M5 | range 右边界 | 以为 range(1,5) 含 5 |
| M6 | print/return 混淆 | 函数只 print 不 return |
| M7 | 类型转换错误 | string + int |
| M8 | while 条件错误 | 无限循环 |

## 误区诊断接入点

- **练习提交**（exercises.py）：未通过时自动诊断
- **AI 对话**（chat_service.py）：检测代码块后诊断 + 注入 Prompt
- **API 端点**：`POST /api/v1/misconceptions/diagnose`

## 常见问题

### 新字段/表缺失
- 2.0 的画像字段已进入迁移链：`d3e4f5a6b7c8_add_profile_learning_fields`
  （`weak_topics` / `recent_misconceptions` / `hint_dependency` / `completed_lessons`）
- 已有库直接 `cd backend && alembic upgrade head`；迁移会跳过已经手工加过的列
- 不要再手工 `ALTER TABLE`：生产环境不跑 `create_all()`，手工改动不会进入迁移链

---

# PyTutor 3.0 — 三人算法优化（Feature Flag 开关隔离）

## Feature Flags（10 个，默认值）

所有开关在 `backend/app/core/config.py` 定义，`.env` 可覆盖。默认值：

| Flag | 默认 | 方向 | 作用 |
|------|------|------|------|
| `ENABLE_AST_DIAGNOSIS` | false | B | AST 代码结构分析诊断（替换纯正则） |
| `ENABLE_PEDAGOGY_STEERING` | false | E | 教学意图转移图 + 误区锚定 prompt |
| `ENABLE_MULTI_JUDGE` | false | C | 3 评委评分（需 DEEPSEEK_API_KEY） |
| `ENABLE_TIME_DECAY` | false | C | 画像时间衰减 + 转移矩阵 |
| `ENABLE_CONTENT_RECOMMEND` | false | C | Content-Based 练习推荐 |
| `ENABLE_MULTI_MODEL_ROUTING` | false | C | 多模型路由（简单/复杂分流） |
| `ENABLE_RAG_RERANK` | false | A | RAG LLM 重排序 |
| `ENABLE_HYBRID_WEIGHTS` | false | A | 向量+TF-IDF 加权融合 |
| `ENABLE_TOKEN_CHUNKING` | false | A | token 窗口 + 重叠分块 |
| `ENABLE_CONTEXT_COMPRESSION` | false | A | RAG 上下文截断压缩 |

> 代码默认全关；`backend/.env` 的演示配置打开了 `ENABLE_AST_DIAGNOSIS`、
> `ENABLE_TIME_DECAY`、`ENABLE_CONTENT_RECOMMEND` 三项。判断"当前实际走哪条路"以启动日志
> 和 `message.metadata_json` 为准，不要只看代码默认值。

## 新增模块

- **AST 诊断**：`backend/app/analysis/`（ast_analyzer + ast_visitors + confidence + error_class + root_cause）
- **E 方向**：`backend/app/services/pedagogy/steering.py` + `backend/app/services/prompts/misconception_anchored.py`
- **C 方向**：`backend/app/services/judge_service.py`（Multi-Judge）、`profile_decay_service.py`（衰减+矩阵）
- **A 方向**：`backend/app/services/rag_service.py`（`_weighted_merge`/`_format_compressed`）、`backend/app/rag/splitter.py`（`estimate_tokens`/`_split_by_tokens`）

## 评测

| 脚本 | 用途 |
|------|------|
| `evaluation/run_v2_eval.py --mode ast-only` | 误区诊断（同集：47 正例 + 22 干净代码） |
| `evaluation/run_v2_eval.py --mode ast-only --dataset ../evaluation/v2_holdout_cases.json --clean ../evaluation/holdout_clean_cases.json --out ../evaluation/v2_holdout_results.json` | 留出集诊断（30 + 15，单作者） |
| `evaluation/run_judge_eval.py` | Multi-Judge 评分（需 key） |
| `evaluation/run_rag_eval.py` | RAG Recall@K / MRR（离线，从 backend 目录运行） |
| `evaluation/build_results_summary.py` | 汇总所有结果 JSON → `results_summary.csv`（不重跑实验） |

结果图在 `docs/figures/`（`make_figures.py` 生成浅色/深色 SVG），数字口径与表格视图见
`docs/figures/README.md`；改动数据集或评测后需同时重跑汇总脚本与图。

## 常见问题

### backend 从根目录运行报 `extra_forbidden: vision_model`
- 根 `.env` 的 `VISION_MODEL`（vision.js 专用）被 pydantic 当作未知字段拒绝
- 已通过 config.py `extra="ignore"` 修复

### 跑 RAG 评测 / 诊断评测
- 需从 `backend/` 目录运行（`.env` 和 `./ai_tutor.db` 都是相对路径）：
  ```bash
  cd backend && python ../evaluation/run_rag_eval.py
  ```

---

# 工程边界与排障补充（2026-10）

## 学生代码执行边界

所有入口（练习判题、代码运行、Agent）统一走 `backend/app/sandbox/runner.py` 的
`execute_student_code()` / `execute_student_code_plain()`，不要直接调 `subprocess` 或
`docker_executor`。

| `SANDBOX_MODE` | `isolation_required` | 行为 |
|----------------|----------------------|------|
| `auto` | false | 有 Docker 用 Docker，否则宿主进程 |
| `auto` | true | 只用 Docker；不可用时返回 `status="unavailable"` |
| `docker` | — | 只用 Docker；不可用返回 `unavailable` |
| `subprocess` | false | 宿主进程 |
| `subprocess` | true | 拒绝执行，返回 `unavailable` |

`isolation_required = SANDBOX_REQUIRE_ISOLATION or APP_ENV == "production"`。
练习提交遇到 `unavailable` 直接返回"未判定"，**不写画像、不发奖励**。

## 部署与限流

- 部署边界见 `docs/DEPLOYMENT.md`：Render 无 Docker → 生产强制隔离 → 判题全部
  `unavailable`，只能演示聊天/RAG；完整判题需本地或 Docker Compose。
- 进程内限流 `backend/app/core/rate_limit.py`：普通 API 120 次/分/IP，登录注册
  10 次/分/IP（`RATE_LIMIT_ENABLED` 可关）。多 worker 时每个进程各算一份。
- 空库必须 `alembic upgrade head`；生产不跑 `create_all()`。CI 会用空库验证迁移链。

## 判题与奖励

- 只有 `score_pct > 0` 且全部用例通过（用例数 > 0）才算通过。
- 首次奖励幂等：`rewarded = all_passed and score_pct > 0 and already_passed == 0`。
- 提示次数、看答案行为由服务端 `LearningEvent` 统计（`hint_requested` / `solution_viewed`），
  不信任前端传来的 `used_hints` / `viewed_solution`。
- 参考答案闸门：学生需通过该题或累计尝试 ≥3 次（`SOLUTION_ATTEMPT_THRESHOLD`），教师/管理员不限。

## 画像字段格式

| 字段 | 格式 |
|------|------|
| `weak_topics` | JSON 数组字符串 |
| `recent_misconceptions` | JSON 数组字符串（误区编号 M1–M8，最多 10 个） |
| `completed_lessons` | JSON 数组字符串（去重） |
| `hint_dependency` | **纯标签** `low` / `medium` / `high`（不要再写 JSON） |

读取旧数据用 `profile_service.normalize_hint_dependency()`。
迁移 head：`d3e4f5a6b7c8`。

## 前端引导状态

`onboarding-wrapper.tsx` 用 `onboarding_${user.id}` 作 localStorage key（不是 token 前缀）。
课程进度是 `pytutor_progress_${userId}`。换账号不会互相沿用。

## RAG 评测

```bash
cd backend
python ../evaluation/run_rag_eval.py --mode tfidf|vector|hybrid
```

结果分别写 `evaluation/rag_eval_results_{mode}.json`，含 Top-5 上下文 token 估算
（`mean/max/total_context_tokens`，口径为 `splitter.estimate_tokens`，不是分词器精确值）。
`ENABLE_HYBRID_WEIGHTS=false` 时 hybrid 等于"向量优先 + TF-IDF 补位"，Top-5 往往被向量占满，
不要拿它证明融合有效。

## 忠实度实验

```bash
cd research/faithfulness
python run_experiment.py --demo                 # 桩模型，离线
python run_experiment.py --out results_real.json # 真实模型，读 backend/.env
```

`build_llm()` 会显式加载 `backend/.env`（settings 的 env_file 是相对路径，从该目录直接运行读不到）。
10 条种子的真实试跑结论见 `research/faithfulness/RESULTS.md`：抽取器 `rules_v2` 下两次运行
C2 都未优于 C1（配对差为负，95% CI 含 0），不能宣称证据注入有效。

## 可复现入口

`docs/REPRODUCIBILITY.md` 记录了基线提交、开关矩阵、数据库路径规则、数据集哈希、
评测口径和"已实现/已启用/已验证"对照表。改数据集或开关后请同步更新。
