# 修改日志 (Changelog)

> AI Python Tutor 项目——所有修改、新增、删除、Bug 修复的完整记录

---

## Phase 1: MVP 后端骨架 (Steps 1-6)

### Step 1 - 项目初始化与 FastAPI 骨架
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/pyproject.toml` | Python 项目依赖声明 |
| 新增 | `backend/.env.example` | 配置模板 |
| 新增 | `backend/.env` | 实际配置（含 DeepSeek API Key） |
| 新增 | `backend/.gitignore` | Python 项目忽略规则 |
| 新增 | `backend/app/__init__.py` | 应用包初始化 |
| 新增 | `backend/app/main.py` | FastAPI 入口：工厂模式、CORS、Health Check、异常处理 |
| 新增 | `backend/app/core/__init__.py` | 核心模块 |
| 新增 | `backend/app/core/config.py` | pydantic-settings 配置管理 |

### Step 2 - 结构化日志系统
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/core/logging_config.py` | structlog 日志初始化（开发彩色/生产 JSON） |
| 新增 | `backend/app/observability/__init__.py` | 可观测性模块 |
| 新增 | `backend/app/observability/logger.py` | `get_logger()` 工厂函数 |
| 新增 | `backend/app/observability/middleware.py` | `RequestLoggingMiddleware`：request_id、耗时、状态码 |
| 修改 | `backend/app/main.py` | 集成日志系统 + 中间件 |

### Step 3 - 数据库基础
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/database/__init__.py` | 数据库模块 |
| 新增 | `backend/app/database/session.py` | 异步引擎、会话工厂、`get_db()` 依赖注入 |
| 新增 | `backend/app/database/base.py` | `Base` 声明基类 + `TimestampMixin`（id, created_at, updated_at） |
| 新增 | `backend/app/models/__init__.py` | 模型模块 |
| 新增 | `backend/app/models/user.py` | User 模型：email, password_hash, display_name, role(Enum), is_active |
| 修改 | `backend/alembic.ini` | 数据库 URL 改为动态读取 |
| 修改 | `backend/alembic/env.py` | 异步引擎 + 模型导入 |
| 新增 | `backend/alembic/versions/6ff616aeec07_create_users_table.py` | 首次迁移 |
| 修改 | `backend/app/main.py` | Health check 添加数据库连接检测 |

### Step 4 - 用户认证系统
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/security/__init__.py` | 安全模块 |
| 新增 | `backend/app/security/password.py` | bcrypt 密码哈希与验证 |
| 新增 | `backend/app/security/jwt.py` | JWT 生成与解码 |
| 新增 | `backend/app/security/dependencies.py` | `get_current_user` + `require_role` 依赖 |
| 新增 | `backend/app/schemas/__init__.py` | Schema 模块 |
| 新增 | `backend/app/schemas/common.py` | 统一响应格式 `ResponseModel` |
| 新增 | `backend/app/schemas/auth.py` | 注册/登录请求和响应 Schema |
| 新增 | `backend/app/services/__init__.py` | 服务层 |
| 新增 | `backend/app/services/auth_service.py` | 注册（邮箱去重+密码校验）和登录逻辑 |
| 新增 | `backend/app/api/__init__.py` | API 路由模块 |
| 新增 | `backend/app/api/v1/__init__.py` | v1 API |
| 新增 | `backend/app/api/v1/auth.py` | `POST /register` + `POST /login` |
| 新增 | `backend/app/api/v1/users.py` | `GET /users/me` |
| 新增 | `backend/app/api/router.py` | 路由聚合器 |
| 修改 | `backend/app/main.py` | 注册 API 路由 |

**Bug 修复**:
- passlib 1.7.4 与 bcrypt 5.0 不兼容 → 改用原生 bcrypt 库
- Pydantic EmailStr 缺少 email-validator 依赖 → 安装 `email-validator`
- Pydantic `created_at: str` 与 SQLAlchemy `datetime` 类型不匹配 → 改用 `datetime` 类型 + `field_serializer`

### Step 5 - AI 服务基础
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/core/exceptions.py` | 自定义异常类（LLMException, NotFoundException 等） |
| 新增 | `backend/app/schemas/ai.py` | LLM 请求/响应 Schema |
| 新增 | `backend/app/services/llm_service.py` | DeepSeek API 封装（OpenAI SDK）+ fallback 模型 |
| 新增 | `backend/tests/test_llm.py` | LLM 连接测试脚本 |
| 修改 | `backend/.env` | 填入真实 DeepSeek API Key |

### Step 6 - Docker 化
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/Dockerfile` | 多阶段构建（builder + runtime）、健康检查、非 root 用户 |
| 新增 | `docker-compose.yml` | 编排 backend + postgres + redis（预留） |
| 新增 | `.dockerignore` | Docker 构建忽略规则 |
| 新增 | `Makefile` | 常用命令快捷方式 |
| 新增 | `README.md` | 项目说明 |

---

## Phase 2: AI 聊天 + RAG + 沙箱 (Steps 7-14)

### Step 7 - 聊天会话 API
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/models/chat.py` | ChatSession + ChatMessage 模型 |
| 新增 | `backend/app/schemas/chat.py` | 聊天请求/响应 Schema（含 AIResponse 结构化输出） |
| 新增 | `backend/app/services/chat_service.py` | 会话管理 + 消息处理 + RAG 集成 |
| 新增 | `backend/app/services/tutor_service.py` | AI 导师核心：System Prompt、分层提示、JSON 解析 |
| 新增 | `backend/app/api/v1/chat.py` | 聊天 API（创建会话、发消息、查历史、重命名、删除） |
| 新增 | `backend/tests/test_chat_api.py` | 聊天端到端测试 |
| 修改 | `backend/app/api/router.py` | 注册 chat 路由 |
| 修改 | `backend/alembic/env.py` | 导入 Chat 模型 |

**Bug 修复**:
- SQLAlchemy 异步 Greenlet 错误（`model_validate` 触发 lazy load）→ 手动构造 Response
- `related_concepts` 类型不匹配（DB 字符串 vs Pydantic list）→ 添加 `field_validator`

### Step 8 - RAG 知识库
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/models/rag.py` | RAGDocument + RAGChunk 模型 |
| 新增 | `backend/app/schemas/rag.py` | RAG Schema |
| 新增 | `backend/app/rag/__init__.py` | RAG 模块 |
| 新增 | `backend/app/rag/loader.py` | 文档加载器（Markdown） |
| 新增 | `backend/app/rag/splitter.py` | 文档切分器（按标题层级） |
| 新增 | `backend/app/rag/retriever.py` | TF-IDF 混合检索器（内存索引） |
| 新增 | `backend/app/rag/reranker.py` | LLM 重排序 |
| 新增 | `backend/app/services/rag_service.py` | RAG 业务逻辑（导入、索引重建、检索） |
| 新增 | `backend/app/api/v1/rag.py` | RAG 管理 API |
| 新增 | `backend/scripts/seed_knowledge.py` | 初始知识库（10 篇 Python 教学文档，41 chunks） |
| 新增 | `backend/tests/test_rag.py` | RAG 检索测试 |
| 修改 | `backend/app/main.py` | lifespan 启动时自动重建 RAG 索引 |
| 修改 | `backend/app/services/chat_service.py` | 聊天时自动调用 RAG 检索 |
| 修改 | `backend/app/api/router.py` | 注册 rag 路由 |

**Bug 修复**:
- RAG 索引服务重启后丢失 → lifespan 中调用 `rebuild_index()`
- 文档导入后 `len(doc.chunks)` 触发 Greenlet 懒加载 → 用 `_chunk_count` 属性替代

### Step 9 - 代码沙箱
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/models/submission.py` | CodeSubmission + ExecutionResult 模型 |
| 新增 | `backend/app/schemas/code.py` | 代码提交/执行 Schema |
| 新增 | `backend/app/sandbox/__init__.py` | 沙箱模块 |
| 新增 | `backend/app/sandbox/executor.py` | 子进程执行器（超时 10s、输出限制 100KB） |
| 新增 | `backend/app/sandbox/security.py` | 静态安全检查（禁止 os, subprocess, eval 等） |
| 新增 | `backend/app/services/code_service.py` | 代码执行业务逻辑 |
| 新增 | `backend/app/api/v1/code.py` | `POST /code/submit` + `GET /code/submissions/{id}` |
| 修改 | `backend/app/api/router.py` | 注册 code 路由 |

**Bug 修复**:
- bytes literal 中文字符 → `"[超时]...".encode("utf-8")`

### Step 10 - LangGraph Agent 工作流
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/agents/__init__.py` | Agent 模块 |
| 新增 | `backend/app/agents/state.py` | AgentState 状态定义 |
| 新增 | `backend/app/agents/graph.py` | LangGraph 工作流图（6 节点 + 条件路由） |
| 新增 | `backend/app/agents/nodes/__init__.py` | 节点模块 |
| 新增 | `backend/app/agents/nodes/safety_check.py` | 安全检查节点（Prompt Injection 检测） |
| 新增 | `backend/app/agents/nodes/intent_router.py` | 意图识别节点 |
| 新增 | `backend/app/agents/nodes/rag_retrieval.py` | RAG 检索节点 |
| 新增 | `backend/app/agents/nodes/code_executor.py` | 代码执行节点 |
| 新增 | `backend/app/agents/nodes/tutor_node.py` | AI 教学回复节点 |
| 新增 | `backend/app/agents/nodes/output_validator.py` | 输出校验节点 |
| 新增 | `backend/app/services/agent_service.py` | Agent 调用服务 |
| 新增 | `backend/app/api/v1/agent.py` | Agent API（`POST /agent/chat`） |
| 新增 | `backend/app/agents/tools/__init__.py` | 工具模块 |
| 新增 | `backend/app/agents/prompts/__init__.py` | Prompt 模板模块 |
| 修改 | `backend/app/api/router.py` | 注册 agent 路由 |

### Step 11 - 练习生成
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/models/exercise.py` | Exercise + TestCase 模型 |
| 新增 | `backend/app/schemas/exercise.py` | 练习请求/响应 Schema |
| 新增 | `backend/app/services/exercise_service.py` | AI 出题 + 参考答案验证 |
| 新增 | `backend/app/api/v1/exercises.py` | 练习 API（列表、生成、提交判题） |
| 修改 | `backend/app/api/router.py` | 注册 exercises 路由 |

### Step 12 - 学习画像
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/models/profile.py` | StudentProfile + StudentWeakness + LearningEvent 模型 |
| 新增 | `backend/app/services/profile_service.py` | 画像管理、薄弱点检测、学习路径推荐 |
| 新增 | `backend/app/api/v1/profile.py` | 画像 API（摘要、薄弱点、推荐） |
| 修改 | `backend/app/services/auth_service.py` | 注册时自动创建学习画像 |
| 修改 | `backend/app/api/router.py` | 注册 profile 路由 |

---

## Phase 3: 前端开发

### Step 13 - Next.js 项目初始化
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `frontend/` | Next.js 16 + TypeScript + Tailwind 初始化 |
| 新增 | `frontend/src/lib/api.ts` | API 客户端（自动 JWT、401 拦截、16 个 API 方法） |
| 新增 | `frontend/src/stores/auth.ts` | Zustand 认证状态管理 |
| 新增 | `frontend/src/components/nav-user.tsx` | 导航栏用户组件 |

### Step 14 - 前端页面
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `frontend/src/app/layout.tsx` | 根布局：毛玻璃导航栏、渐变色 Logo、导航链接 |
| 修改 | `frontend/src/app/globals.css` | 全局样式：滚动条、Markdown 渲染、动画 |
| 新增 | `frontend/src/app/login/page.tsx` | 登录页：左侧品牌区 + 表单 |
| 新增 | `frontend/src/app/register/page.tsx` | 注册页：Emerald 绿色主题 |
| 修改 | `frontend/src/app/page.tsx` | **主聊天页**：会话侧栏 + 聊天区 + Monaco 代码编辑器 |
| 新增 | `frontend/src/components/chat-message.tsx` | 消息气泡组件：语法高亮、代码复制、Markdown 渲染 |
| 新增 | `frontend/src/app/exercises/page.tsx` | 练习中心：AI 出题 + 作答 + 判题结果 |
| 新增 | `frontend/src/app/profile/page.tsx` | 学习画像 Dashboard：统计卡片、薄弱点图表、推荐 |

### Step 15 - AI 回复质量优化
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| **重写** | `backend/app/services/tutor_service.py` | System Prompt 大幅简化（100 行 → 20 行），**取消 JSON 输出要求**，改用纯文本 Markdown + 首行注释元数据 |
| **重写** | `backend/app/agents/nodes/tutor_node.py` | 同步简化，纯文本回复 + Fallback 机制 |
| 修改 | `backend/app/services/chat_service.py` | AI 回复 content 字段**只存消息文本**（之前错误地存了完整 JSON） |
| 修改 | `frontend/src/components/chat-message.tsx` | 兼容旧数据：auto-detect JSON 格式并提取 message 字段 |

### Step 16 - 会话管理增强
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `backend/app/api/v1/chat.py` | 新增 `PATCH /sessions/{id}`（重命名）+ `DELETE /sessions/{id}`（删除） |
| 修改 | `backend/app/services/chat_service.py` | 首条消息自动命名（SQL count 方式，避免 Greenlet） |
| 修改 | `frontend/src/lib/api.ts` | 新增 `renameSession` + `deleteSession` 方法 |
| 修改 | `frontend/src/app/page.tsx` | 侧栏："⋮" 按钮 → 重命名/置顶/删除下拉菜单；双击重命名；置顶排序 |
| 修改 | `frontend/src/app/page.tsx` | 代码面板重设计：编辑器（上 45%）+ 结果区（下 55%，始终可见） |

---

## Phase 4: 管理后台 + 评测 + Prompt 管理 (Steps 17-19)

**日期**: 2026-06-08 ~ 2026-06-09

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/api/v1/admin.py` | 管理员 API：stats/users/logs/exercises |
| 新增 | `frontend/src/app/admin/page.tsx` | 管理后台页面 |
| 新增 | `backend/app/models/prompt.py` | Prompt 模板版本管理 |
| 新增 | `evaluation/golden_dataset.json` | 8 个标准测试用例 |
| 新增 | `evaluation/run_eval.py` | AI 评测脚本 |

---

## Phase 5: UI 重设计 + 练习中心 ACM (Steps 20-25)

**日期**: 2026-06-09

| 操作 | 文件 | 说明 |
|------|------|------|
| **重写** | `frontend/src/app/globals.css` | 深空主题：玻璃拟态、霓虹、动画、暗色滚动条、prose-dark |
| **重写** | `frontend/src/app/layout.tsx` | Glass 导航栏 + 渐变 Logo + 导航高亮 |
| **重写** | `frontend/src/app/login/page.tsx` | 沉浸式科幻登录页 |
| **重写** | `frontend/src/app/register/page.tsx` | 匹配深空主题 |
| **重写** | `frontend/src/app/page.tsx` | 暗色聊天页：glass 面板、neon 输入、Monaco 暗色 |
| **重写** | `frontend/src/components/chat-message.tsx` | 语法高亮代码块 + "在编辑器中运行"按钮 |
| **重写** | `frontend/src/app/exercises/page.tsx` | ACM 布局：题目左 + 编辑器右 + 判题结果面板 |
| **重写** | `frontend/src/app/profile/page.tsx` | 学习画像暗色化 |
| **重写** | `frontend/src/app/admin/page.tsx` | 管理后台暗色化 |
| 新增 | `frontend/src/components/nav-link.tsx` | 导航高亮组件（usePathname） |
| 新增 | `frontend/src/stores/chat.ts` | Zustand persist 聊天状态持久化 |
| 新增 | `frontend/src/stores/exercise.ts` | Zustand persist 练习状态持久化 |
| 修改 | `backend/app/sandbox/security.py` | **重写**：去掉注释字符串再检查、只拦截真正危险操作、放行 input() |
| 修改 | `backend/app/sandbox/executor.py` | 统一两个执行函数的 UTF-8 设置、新增 stdin 输入支持 |
| 修改 | `backend/app/api/v1/exercises.py` | ACM 判题：每用例独立执行 + stdin 传入 + 提示/参考答案接口 |
| 修改 | `backend/app/api/v1/code.py` | 新增 stdin 参数支持 + 独立错误分析接口 |
| 修改 | `backend/app/schemas/code.py` | 新增 ErrorAnalysis schema |
| 修改 | `backend/app/services/tutor_service.py` | 三次迭代：JSON→纯文本→极简（100 行→20 行） |
| 新增 | `vision.js` | 千问 VL 识图脚本（node vision.js 图片路径） |
| 新增 | `CLAUDE.md` | AI 项目说明 |
| 新增 | `docs/tech-explanation.md` | 14 章技术栈详解 |
| 新增 | `docs/interview-prep.md` | 快手面试准备指南（25 道题 + 项目具体实现） |

---

## Phase 6: 工业级架构升级 (2026-06-11)

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/rag/vector_store.py` | ChromiDB 持久化向量库 + MiniLM embedding |
| 修改 | `backend/app/services/rag_service.py` | 混合检索：向量(ChromaDB) + 关键词(TF-IDF) |
| 修改 | `docker-compose.yml` | PostgreSQL+pgvector 配置就绪 |
| 修改 | `backend/.env` | DB 双模式（SQLite默认，PG生产） |
| 新增 | `pyproject.toml` | chromadb, sentence-transformers, litellm, langfuse, ragas 依赖 |
| 重写 | `backend/app/services/llm_service.py` | LiteLLM 网关替换裸 OpenAI SDK |
| 新增 | `backend/app/api/v1/chat.py` | SSE 流式端点 `POST /sessions/{id}/stream` |
| 新增 | `backend/app/services/chat_service.py` | `send_message_stream()` 流式消息 |
| 新增 | `backend/app/services/tutor_service.py` | `generate_tutor_response_stream()` LiteLLM stream |
| 新增 | `backend/app/observability/langfuse_setup.py` | Langfuse + LiteLLM callback |
| 新增 | `backend/app/sandbox/docker_executor.py` | Docker 容器沙箱（auto-fallback） |
| 新增 | `evaluation/run_eval_ragas.py` | Ragas 自动化评测 |

---

## Bug 汇总（共 22 个）

| # | 问题 | 解决方案 | 影响文件 |
|---|------|----------|----------|
| 1 | Windows GBK 编码导致 emoji 报错 | 所有 emoji 替换为 ASCII 标签 | `main.py`, `logging_config.py`, `test_llm.py` |
| 2 | passlib + bcrypt 5.0 不兼容 | 改用原生 `bcrypt` 库 | `security/password.py` |
| 3 | Pydantic EmailStr 缺少 email-validator | 安装 `email-validator` | `pyproject.toml` |
| 4 | datetime 序列化类型不匹配 | `datetime` 类型 + `field_serializer` | `schemas/auth.py` |
| 5 | 端口 8000 残留占用 | `taskkill //F //IM python.exe` | 运维 |
| 6 | SQLAlchemy Greenlet 异步懒加载 | 手动构造 Response / SQL count | `services/chat_service.py`, `services/rag_service.py` |
| 7 | related_concepts 字符串 vs 列表 | `field_validator(mode="before")` | `schemas/chat.py` |
| 8 | Windows 日志 UnicodeEncodeError | `io.TextIOWrapper(encoding='utf-8')` + ASCII 清理 | `logging_config.py`, `llm_service.py` |
| 9 | bytes literal 中文字符 | `.encode("utf-8")` 替代 `b"..."` | `sandbox/executor.py` |
| 10 | RAG 索引服务重启丢失 | lifespan 中 `rebuild_index()` | `main.py` |
| 11 | LLM JSON 输出不稳定 | 取消 JSON 要求，纯文本 Markdown | `tutor_service.py`, `tutor_node.py` |
| 12 | AI 回复 content 存 JSON 致历史乱码 | 只存 message 文本 | `services/chat_service.py` |
| 13 | 会话切换后历史丢失 | content 纯文本化 + 前端兼容旧 JSON | `chat_message.tsx` |
| 14 | 中文输出乱码（10 轮排查） | 两个执行函数 UTF-8 不一致：`execute_python_code` 缺 `-X utf8` | `executor.py` |
| 15 | ACM 空输入 EOFError | 空 stdin 传 `b""` 而非 `None`，加 `\n` 变成空行 | `executor.py` |
| 16 | 安全拦截误杀正常代码 | 去掉注释和字符串后再检查 + 精简黑名单 | `security.py` |
| 17 | `sanitize_code` 被误删导致 500 | 内联替代代码 | `executor.py` |
| 18 | `"use client"` 位置错误导致构建失败 | 拆出独立 NavLink 客户端组件 | `layout.tsx` + `nav-link.tsx` |
| 19 | 练习中心换题不清空状态 | Zustand persist + 切换时 reset | `stores/exercise.ts` |
| 20 | AI 聊天卡死 485 秒 | SentenceTransformer 同步下载 HuggingFace 模型阻塞事件循环。修复：添加 15s 超时 + executor 线程加载 + 失败后标记跳过 | `chat_service.py`, `vector_store.py`, `main.py` |
| 21 | RAG 向量索引重建结果被消费 | `db.execute()` 返回的迭代器被第一个 for 循环耗尽，向量库写入拿到空列表。修复：`result.all()` 物化结果 | `services/rag_service.py` |
| 22 | 练习中心生成题目即显示 ✅ | 用概念标签匹配判断完成状态（通过一题，同标签全打勾）。修复：改为按题目 ID 精确匹配，新增 `/me/passed-ids` 端点 | `profile.py`, `exercises/page.tsx` | |

---

## Phase 4: 管理后台 + 评测 + Prompt 管理

### Step 17 - 管理员后台
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/api/v1/admin.py` | 管理员 API：stats/users/logs/exercises 增删改查 |
| 新增 | `frontend/src/app/admin/page.tsx` | 管理后台页面：概览/用户管理/题库管理/日志查看 |
| 修改 | `backend/app/api/router.py` | 注册 admin 路由 |

### Step 18 - Prompt 模板版本管理
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/models/prompt.py` | PromptTemplate 模型：版本化/可审计/可回滚 |
| 修改 | `backend/alembic/env.py` | 导入 PromptTemplate |

### Step 19 - AI 评测体系
**日期**: 2026-06-08

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `evaluation/golden_dataset.json` | Golden Dataset：8 个标准测试用例 |
| 新增 | `evaluation/run_eval.py` | 评测脚本：意图/知识点/内容/格式四维评分 |

---

## Phase 7: RAG 语义向量升级 + Bug 修复

### Step 20 - DashScope Embedding API 替换本地模型
**日期**: 2026-06-11

**背景**: 本地 `sentence-transformers` 模型（paraphrase-multilingual-MiniLM-L12-v2，~100MB）需从 HuggingFace 下载，在中国网络环境下不可达，导致首次聊天请求阻塞 485 秒。项目已有阿里云百炼 DashScope API Key（用于识图），其 text-embedding API 提供 SOTA 中文语义向量，无需下载模型。

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/rag/embedding.py` | DashScopeEmbedding 类：封装 text-embedding-v3 API（OpenAI 兼容），支持同步/异步、自动批量（max 10/批）、失败降级 |
| 修改 | `backend/app/rag/vector_store.py` | 用 DashScopeEmbedding 完全替代 SentenceTransformer；移除模型下载/加载/锁/失败标记等 ~100 行代码；新的 ChromaDB collection `python_knowledge_v2`（1024 维） |
| 修改 | `backend/app/main.py` | 移除模型预加载后台任务；启动时加载项目根目录 `.env`（获取 `DASHSCOPE_API_KEY`）；改为验证 embedding 服务连通性 |
| 修改 | `backend/app/core/config.py` | 新增 `dashscope_api_key` 和 `embedding_model` 配置项 |
| 修改 | `backend/.env` | 添加 `EMBEDDING_MODEL=text-embedding-v3` |
| 修改 | `backend/app/services/rag_service.py` | `search_async` 替代同步 `search`；`is_model_available()` 跳过不可用向量检索；向量搜索带 12s 内部超时 |

**效果**: 聊天响应从 485s → 3-4s；语义检索 41 条 chunk 已索引（1024 维向量）；降级链路：DashScope API → TF-IDF → 无 RAG

### Step 21 - Bug 修复：RAG 索引重建 + 练习对勾误判 + 双重计数
**日期**: 2026-06-11

| 分类 | 问题 | 根因 | 修复 |
|------|------|------|------|
| Bug #20 | AI 聊天卡死 | `SentenceTransformer` 同步下载阻塞事件循环 485s | 15s 超时 + executor 线程 + 失败标记 |
| Bug #21 | 向量索引写入 0 条 | `db.execute()` 结果被第一个 for 循环耗尽 | `result.all()` 物化 |
| Bug #22 | 生成题目即显示 ✅ | 按概念标签匹配（通过一题全打勾） | 改为按题目 ID 匹配 + 新增 `/me/passed-ids` 端点 |
| Bug #23 | 练习完成数翻倍（2 而非 1） | `exercises.py` 手动更新 profile + `record_event()` 内部再更新 = 双重计数；failed 行还有重复 `+= 1` | 移除 `exercises.py` 重复累加，由 `record_event()` 统一管理；前端 `exercises_passed` 替代 `exercises_completed` |

---

## 当前项目统计

```
总文件数:   62+ (不含 node_modules)
后端文件:   45
前端文件:   12
数据库表:   10 (users, chat_sessions, chat_messages, rag_documents, rag_chunks,
                code_submissions, execution_results, exercises, test_cases,
                student_profiles, student_weaknesses, learning_events)
API 端点:   21+
Alembic 迁移: 7 次
记录 Bug:   23 个
技术文档:   14 章
```
