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
5. **评估数据集**：evaluation/v2_test_cases.json（20 个案例）

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
- 2.0 使用 `Base.metadata.create_all()` 在启动时建表
- SQLite 不支持修改已有表，新字段需手动添加：
  ```sql
  ALTER TABLE student_profiles ADD COLUMN weak_topics TEXT;
  ALTER TABLE student_profiles ADD COLUMN recent_misconceptions TEXT;
  ALTER TABLE student_profiles ADD COLUMN hint_dependency VARCHAR(20) DEFAULT 'low';
  ALTER TABLE student_profiles ADD COLUMN completed_lessons TEXT;
  ```

---

# PyTutor 3.0 — 三人算法优化（Feature Flag 开关隔离）

## Feature Flags（10 个，默认值）

所有开关在 `backend/app/core/config.py` 定义，`.env` 可覆盖。默认值：

| Flag | 默认 | 方向 | 作用 |
|------|------|------|------|
| `ENABLE_AST_DIAGNOSIS` | **true** | B | AST 代码结构分析诊断（替换纯正则） |
| `ENABLE_PEDAGOGY_STEERING` | false | E | 教学意图转移图 + 误区锚定 prompt |
| `ENABLE_MULTI_JUDGE` | false | C | 3 评委评分（需 DEEPSEEK_API_KEY） |
| `ENABLE_TIME_DECAY` | **true** | C | 画像时间衰减 + 转移矩阵 |
| `ENABLE_CONTENT_RECOMMEND` | **true** | C | Content-Based 练习推荐 |
| `ENABLE_MULTI_MODEL_ROUTING` | false | C | 多模型路由（简单/复杂分流） |
| `ENABLE_RAG_RERANK` | false | A | RAG LLM 重排序 |
| `ENABLE_HYBRID_WEIGHTS` | false | A | 向量+TF-IDF 加权融合 |
| `ENABLE_TOKEN_CHUNKING` | false | A | token 窗口 + 重叠分块 |
| `ENABLE_CONTEXT_COMPRESSION` | false | A | RAG 上下文截断压缩 |

## 新增模块

- **AST 诊断**：`backend/app/analysis/`（ast_analyzer + ast_visitors + confidence + error_class + root_cause）
- **E 方向**：`backend/app/services/pedagogy/steering.py` + `backend/app/services/prompts/misconception_anchored.py`
- **C 方向**：`backend/app/services/judge_service.py`（Multi-Judge）、`profile_decay_service.py`（衰减+矩阵）
- **A 方向**：`backend/app/services/rag_service.py`（`_weighted_merge`/`_format_compressed`）、`backend/app/rag/splitter.py`（`estimate_tokens`/`_split_by_tokens`）

## 评测

| 脚本 | 用途 |
|------|------|
| `evaluation/run_v2_eval.py --mode ast-only` | 误区诊断（离线，47 正例 + 22 干净代码） |
| `evaluation/run_judge_eval.py` | Multi-Judge 评分（需 key） |
| `evaluation/run_rag_eval.py` | RAG Recall@K / MRR（离线，从 backend 目录运行） |

## 常见问题

### backend 从根目录运行报 `extra_forbidden: vision_model`
- 根 `.env` 的 `VISION_MODEL`（vision.js 专用）被 pydantic 当作未知字段拒绝
- 已通过 config.py `extra="ignore"` 修复

### 跑 RAG 评测 / 诊断评测
- 需从 `backend/` 目录运行（`.env` 和 `./ai_tutor.db` 都是相对路径）：
  ```bash
  cd backend && python ../evaluation/run_rag_eval.py
  ```
