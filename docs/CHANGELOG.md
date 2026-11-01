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
| Bug #24 | 做对题目不打勾 + 切换后结果丢失 | `already_passed` 按概念去重 + `selectExercise` 无条件清空 result | 按 exercise_id 去重；已通过题目保留结果 |
| Bug #25 | 2.0 profile 接口返回 None | SQLAlchemy `create_all` 不修改已有表，新增 4 个 2.0 字段缺失 | 手动 `ALTER TABLE ADD COLUMN` |

---

## Phase 8: PyTutor 2.0 — Misconception-Aware AI Tutoring
**日期**: 2026-06-11

### Step 22 — 新手引导 (Priority 1)
| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `frontend/src/components/onboarding-modal.tsx` | 首次登录弹窗：4 选项（零基础/学过/会基础/自由提问） |
| 新增 | `frontend/src/components/onboarding-wrapper.tsx` | 客户端包装器：检测 profile 状态，决定是否弹窗 |
| 新增 | `frontend/src/components/lesson-0.tsx` | Lesson 0 教程：9 步引导式对话 + 实时代码编辑器 |
| 修改 | `frontend/src/app/layout.tsx` | 集成 OnboardingWrapper |
| 修改 | `backend/app/api/v1/profile.py` | 新增 `/onboarding` + `/lesson/complete` 端点 |
| 修改 | `backend/app/services/profile_service.py` | 返回 `onboarding_done` 字段 |

### Step 23 — 误区分类与诊断 (Priority 2)
| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/models/misconception.py` | Misconception + MisconceptionEvent 模型 |
| 新增 | `backend/app/data/misconceptions.json` | 8 类误区种子数据（M1-M8，含正则匹配规则） |
| 新增 | `backend/app/services/misconception_service.py` | 规则匹配 + LLM 辅助双通道诊断引擎 |
| 新增 | `backend/app/api/v1/misconceptions.py` | `POST /diagnose` + `GET /misconceptions` |
| 修改 | `backend/app/main.py` | 启动时 auto-create 表 + seed 误区数据 |
| 修改 | `backend/app/api/router.py` | 注册 misconceptions 路由 |

### Step 24 — 教学策略 + 渐进式提示 (Priority 3)
| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/services/pedagogy_service.py` | 7 种教学策略 + 5 级提示系统 + 回复质量检查 |
| 修改 | `backend/app/services/chat_service.py` | 代码消息自动触发误区诊断 + 注入教学策略到 Prompt |
| 修改 | `backend/app/api/v1/exercises.py` | 提交未通过时自动诊断误区，返回 misconception 结果 |
| 修改 | `backend/app/schemas/chat.py` | AIResponse 新增 misconception_id / pedagogical_strategy / reflection_question |
| 修改 | `frontend/src/app/exercises/page.tsx` | 判题结果区展示「🧠 误区诊断」卡片 |

### Step 25 — 学习画像增强 (Priority 4)
| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `backend/app/models/profile.py` | 新增 weak_topics / recent_misconceptions / hint_dependency / completed_lessons |
| 修改 | `backend/app/services/profile_service.py` | 画像摘要返回 2.0 字段 |
| 修改 | `frontend/src/app/profile/page.tsx` | 新增「最近误区」+「提示依赖度」展示区 |

### Step 26 — 评估数据集 (Priority 5)
| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `evaluation/v2_test_cases.json` | 20 个 Python 初学者错误案例（含期望误区和提示等级） |

---

## 当前项目统计

```
总文件数:   75+ (不含 node_modules)
后端文件:   50
前端文件:   15
数据库表:   12 (users, chat_sessions, chat_messages, rag_documents, rag_chunks,
                code_submissions, execution_results, exercises, test_cases,
                student_profiles, student_weaknesses, learning_events,
                misconceptions, misconception_events)
API 端点:   25+
Alembic 迁移: 7 次
记录 Bug:   39 个
版本:      2.0 (Misconception-Aware AI Tutoring)
```

---

## Phase 9: 新手教程完整系统 (Steps 27-29)

### Step 27 — 7 课教程 + 通用播放器
**日期**: 2026-06-11

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `frontend/src/data/tutorial-data.ts` | 7 课结构化数据（0A, 0B, 1-5），每课含 steps、代码、任务 |
| 新增 | `frontend/src/components/lesson-player.tsx` | 通用 LessonPlayer 组件：AI 分步引导 + Code Lab + 误区诊断 |
| 修改 | `frontend/src/components/onboarding-wrapper.tsx` | Lesson0 → LessonPlayer；四选项差异化行为 |
| 删除 | `frontend/src/components/lesson-0.tsx` | 被 LessonPlayer 替代 |

### Step 28 — 退出按钮 + 进度持久化
**日期**: 2026-06-11

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `lesson-player.tsx` | 右上角「暂时退出」按钮 + 确认弹窗；localStorage 自动保存/恢复 |
| 修改 | `lesson-player.tsx` | 进度按用户 ID 隔离（`pytutor_progress_{userId}`） |
| 修改 | `onboarding-wrapper.tsx` | 右下角 🎓 浮动按钮：有进度直接续学 |

### Step 29 — stdin 输入 + 输出区域扩大
**日期**: 2026-06-11

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `lesson-player.tsx` | 右侧 50/50 布局；新增 stdin 输入行；输出区域加大 |
| 修改 | `frontend/src/app/page.tsx` | 主页编辑器新增 stdin 输入字段 |

## Bug 汇总补充

| # | 问题 | 根因 | 修复 |
|----|------|------|------|
| Bug #26 | 新用户进教程看到旧用户进度 | localStorage key 用 token 前 16 位 | key 改为 `pytutor_progress_{user.id}` |
| Bug #27 | 管理员用 SQLite 直插的账号无法登录 | bcrypt 哈希格式与 app 不兼容 | 通过 API 注册，再 SQL 升级角色 |
| Bug #28 | 教师/管理员看到学生弹窗 | OnboardingWrapper 未检查 role | `user.role !== "student"` 跳过 |
| Bug #29 | 管理员仍看到弹窗 | `isAuthenticated` 在 `user` 加载完前变 true | 等 `user` 就绪后再检查角色 |
| Bug #30 | 部署后页面不停闪烁 | `api.ts` 401 时 `window.location.href` 强制跳转 + `loadUser` 失败清零 `isAuthenticated` | 删除强制跳转；token 存在即保持登录 |
| Bug #31 | 退出后新手弹窗残留 | OnboardingWrapper `useEffect([], [])` 只挂载一次 | 依赖 `isAuthenticated`，退出时隐藏全部弹窗 |
| Bug #32 | SSR 时 `localStorage` 不存在崩溃 | `getToken()` 在 Node.js 端调用 `localStorage.getItem` | `typeof window === "undefined"` 守卫 |
| Bug #33 | Render 上 `litellm` 无法安装 | pip 静默失败或版本不兼容 | `llm_service` 增加 `openai` SDK 备用通道 |
| Bug #34 | Vercel Git 自动部署持续失败 | Git 作者 `dev@pytutor.local` 无权限 + Root Directory 未设 `frontend` | 改 Git 配置匹配 Vercel 账号；清空 Root Directory |
| Bug #35 | Vercel CLI 部署持续报 project name 错误 | 根目录 `vercel.json` 被多次自动生成，导致 monorepo 检测冲突 | 删除旧 Vercel 项目，全新导入时正确设 Root Directory=`frontend` |
| Bug #36 | AI 回复中代码块无运行按钮 | page.tsx 重写时遗漏 `onRunInEditor` 属性传递 | 恢复 ChatMessage 的 onRunInEditor prop |
| Bug #37 | 未登录时首页黑屏不跳转登录页 | `loadUser()` 需等 Render 后端响应才决定跳转，休眠时卡住 | 不等后端，token 不存在立刻 `router.push("/login")` |
| Bug #38 | 两个 Vercel 网址行为不一致 | 旧项目连 Git 自动更新，新项目未连 Git 代码过时 | 统一用旧地址 `pytutor-ai-git-main-...`，删除新项目 |
| Bug #39 | 本地运行首页空白不跳登录 | 浏览器残留 Vercel 的旧 token | 清 localStorage 旧 token |

---

## Phase 11: 基础功能补齐 (Step 38)

### Step 39 — AI 导师人物升级
**日期**: 2026-06-17

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `tutor_service.py` | System Prompt 重写：共情+生活比喻+禁止否定语+回复结构+代码限制 |
| 修改 | `chat_service.py` | 画像驱动对话：注入最近误区+提示依赖度+修正后总结 |

### Step 38 — 回复自检前端 + 画像自动更新
**日期**: 2026-06-17

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `schemas/chat.py` | AIResponse 新增 `verify_score` 字段 |
| 修改 | `tutor_service.py` | 回复自检分数透传到前端 |
| 修改 | `chat_service.py` | 聊天中诊断出误区后自动更新 `recent_misconceptions` + `weak_topics` |
| 修改 | `chat-message.tsx` | AI 回复上方显示质量徽章（✅ 质量 4/5） |
| 修改 | `page.tsx`, `chat.ts` | Message 接口新增 `verify_score` |

---

## Phase 10: 入口 B 基础诊断系统 (Step 30)

### Step 30 — DiagnosticFlow 诊断流程
**日期**: 2026-06-12

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `frontend/src/data/diagnostic-tasks.ts` | 6 道诊断题 |
| 新增 | `frontend/src/components/diagnostic-flow.tsx` | 3 页 Portal 流程：说明→答题→报告 |
| 修改 | `onboarding-wrapper.tsx` | 入口 B 触发 DiagnosticFlow |

### Step 31 — 教学策略前端接入
**日期**: 2026-06-12

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `exercises.py` hint API | 接入 misconception 诊断 + 5 级渐进提示 + 策略选择 |
| 修改 | `exercises/page.tsx` | 提示卡片展示误区名 + 策略标签 |
| 修改 | `chat-message.tsx` | AI 回复展示 misconception_id + pedagogical_strategy 徽章 |
| 修改 | `page.tsx` | Message 接口新增 2.0 字段传递 |

### Step 32 — 回复质量自检 + Baseline 评估
**日期**: 2026-06-12

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `tutor_service.py` | AI 回复后调用 verify_response()，不合格自动重新生成 |
| 新增 | `evaluation/run_v2_eval.py` | 20 例 Baseline 评估脚本，3 维评分 |
| **评估结果** | — | **92.3%** 综合分，77.5% 诊断准确率，100% 不早给答案 |

### Step 33 — 教程 Lesson 6-10 + 误区专项练习
**日期**: 2026-06-12

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `tutorial-data.ts` | 新增 5 课（共 12 课完整教程） |
| 新增 | `misconception-exercises.ts` | 16 道 M1-M8 误区靶向练习 |
| 新增 | `misconception_exercises.py` | seed 端点，已入库 16 题 |

### Step 35 — 代码重构清理
**日期**: 2026-06-12

### Step 37 — 全项目架构文档 + 项目全史
**日期**: 2026-06-12

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `ARCHITECTURE.md` | 961 行：需求→代码映射、36 Step 时间线、29 Bug 记录 |
| 新增 | `PROJECT-STORY.md` | 317 行：从零到 2.0 的完整历程，小白也能看懂 |

### Step 36 — 企业级 CI/CD + 测试体系
**日期**: 2026-06-12

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `ARCHITECTURE.md` | 961 行：10 章 + 核心代码逐函数详解 + 关键算法伪代码 |

### Step 36 — 企业级 CI/CD + 测试体系
**日期**: 2026-06-12

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/tests/conftest.py` | 共享 fixtures（auth, client） |
| 新增 | `backend/tests/test_misconception.py` | 11 个误区诊断单元测试 |
| 新增 | `backend/tests/test_pedagogy.py` | 8 个教学策略单元测试 |
| 新增 | `backend/tests/test_api.py` | 9 个 API 集成测试 |
| 新增 | `.github/workflows/ci.yml` | CI pipeline：backend test + frontend build + lint |
| 修改 | `pyproject.toml` | test deps + markers |
| 修改 | `exercises.py`, `vector_store.py` | 静默吞错改为 log warning |
| **测试结果** | — | **28/28 全部通过**（19 unit + 9 integration） |

### Step 35 — 代码重构清理
**日期**: 2026-06-12

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/data/mc_exercises.py` | 16 题数据与 API 分离 |
| 修改 | `misconception_exercises.py` | 简化为纯 API 逻辑（从 data 导入） |
| 修改 | `main.py` | 添加 `result.all()` 物化 + 注释说明 |
| 修改 | `router.py` | 导入统一置顶，清晰分组 |
| 修改 | `teacher.py` | 补充完整 docstring + 分段注释 + 异常处理 |

### Step 34 — 教师仪表盘
**日期**: 2026-06-12

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/api/v1/teacher.py` | `GET /teacher/overview` 聚合统计 |
| 新增 | `frontend/src/app/teacher/page.tsx` | 误区频次 / 薄弱点排行 / 提示依赖 / 学生列表 / 动态 |
| 修改 | `layout.tsx` | 导航栏新增「教学分析」入口 |

---

## Phase 12: PyTutor 3.0 — 三人算法优化整合 (Steps 40-44)

**日期**: 2026-09-14

> 整合 B（AST 诊断）、E（教学意图转移）、C（质量优化）、A（RAG 优化）四方向，
> 采用 MASTER-PLAN 的 feature-flag 开关隔离法，全部默认关，逐一验证后转默认开。

### Step 40 — B 组：AST 代码结构分析诊断

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/analysis/` | AST 诊断模块（ast_analyzer + 6 个 NodeVisitor + confidence + error_class + root_cause） |
| 修改 | `backend/app/services/misconception_service.py` | `diagnose()` 顶部按 `ENABLE_AST_DIAGNOSIS` 分支到 `_ast_diagnose()` |
| 新增 | `backend/tests/test_ast_analyzer.py` | 48 单元测试 |
| 新增 | `backend/tests/test_ast_adversarial_v31.py` | 26 对抗性负例测试 |
| 修改 | `evaluation/v2_test_cases.json` | 20→47 例（修正 3 个误标注用例） |
| 新增 | `evaluation/clean_code_cases.json` | 20→22 例干净代码（测误报率） |

**Bug 修复**:
- Bug #40：M7 类型转换检测漏判 `a='hello'; b=123; c=a+b` — `_is_likely_int` 检查 `"int"` 但 `_scan_assignments` 存 `"num"`，类型映射不一致。改为接受 `("int","num")`
- 测试用例误标注修正：C41（`pop()` 有返回值，非 M3）、C17（正确 range 代码，非 M5）移至 clean 集；C13（for 循环标 M8，无 while）移除

**指标**: Exact Match 92% → **100%**（47/47），Macro F1 0.964 → **1.000**，误报率 **0%**（0/22）

### Step 41 — E 方向：教学意图转移图 + 误区锚定 prompt

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/services/pedagogy/steering.py` | 教学意图转移图（`select_strategy`） |
| 新增 | `backend/app/services/pedagogy/transition_graph.yaml` | 转移图数据 |
| 新增 | `backend/app/services/prompts/misconception_anchored.py` | 误区锚定 prompt（`build_system_prompt` + `leaks_answer`） |
| 修改 | `backend/app/services/chat_service.py` | 按 `ENABLE_PEDAGOGY_STEERING` 注入转移图决策 + 锚定 prompt |
| 修改 | `backend/app/api/v1/exercises.py` | 接入 `error_class`（第 1 层错误大类，E-FR-02） |
| 新增 | `backend/tests/test_e_direction.py` | 30 测试 |
| 新增 | `backend/tests/test_srs32_supplement.py` | 24 测试 |

### Step 42 — C 组：质量与系统优化

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/services/judge_service.py` | Multi-Judge 3 评委评分 + Rubric V2（Task 1+2） |
| 新增 | `backend/app/services/profile_decay_service.py` | 时间衰减 + 转移矩阵 + Hint 依赖（Task 3+4） |
| 修改 | `backend/app/services/pedagogy_service.py` | `verify_response()` 按 `ENABLE_MULTI_JUDGE` 路由到 `multi_judge_verify` |
| 修改 | `backend/app/services/profile_service.py` | 按 `ENABLE_TIME_DECAY` / `ENABLE_CONTENT_RECOMMEND` 接入衰减 + 内容推荐（Task 5） |
| 修改 | `backend/app/services/llm_service.py` | 追加 `classify_question_complexity()` + `chat_completion_routed()`（Task 6） |
| 修改 | `backend/app/services/tutor_service.py` | 按 `ENABLE_MULTI_MODEL_ROUTING` 路由（含流式） |
| 新增 | `backend/tests/test_judge_service.py` | 12 测试 |
| 新增 | `backend/tests/test_profile_decay.py` | 17 测试 |
| 新增 | `evaluation/run_judge_eval.py` | Multi-Judge 评估脚本 |

### Step 43 — A 组：RAG 检索优化（核心 4 项）

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `backend/app/services/rag_service.py` | A1 重排序接线 + A2 加权融合 `_weighted_merge` + A6 上下文压缩 `_format_compressed` |
| 修改 | `backend/app/rag/splitter.py` | A4 `estimate_tokens` + `_split_by_tokens`（token 窗口 + 重叠） |
| 修改 | `backend/app/core/config.py` | 新增 `RAG_VECTOR_WEIGHT` / `RAG_CONTEXT_MAX_TOKENS` 参数 |
| 新增 | `backend/tests/test_rag_optimization.py` | 13 测试 |
| 新增 | `evaluation/run_rag_eval.py` + `rag_golden.json` | Recall@K / MRR 评测 |

**指标**: Recall@3/5 = **88.9%**，MRR = **0.889**（TF-IDF 基线，均超 MASTER-PLAN 目标 ≥0.85 / ≥0.75）

### Step 44 — Feature Flags 脚手架 + 全量整合

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `backend/app/core/config.py` | 新增 10 个 `ENABLE_*` flag + `extra="ignore"`（忽略根 .env 的 VISION_MODEL） |
| 修改 | `backend/.env` | 追加 10 个 flag，最终默认：AST/时间衰减/内容推荐=true，其余=false |

**Bug 修复**:
- Bug #41：`docker_executor.py` bytes 字面量含中文致 SyntaxError — 改用 `.encode("utf-8")`
- Bug #42：backend 从根目录运行读到根 .env 的 `VISION_MODEL`（vision.js 专用）触发 pydantic `extra_forbidden` — config 加 `extra="ignore"`

**最终 flag 默认值**:

| Flag | 默认 | 说明 |
|------|------|------|
| `ENABLE_AST_DIAGNOSIS` | **true** | AST 诊断已达标（100% EM / 0% FP） |
| `ENABLE_TIME_DECAY` / `ENABLE_CONTENT_RECOMMEND` | **true** | 纯计算，零 API 成本 |
| `ENABLE_PEDAGOGY_STEERING` | false | E 方向灰度 |
| `ENABLE_MULTI_JUDGE` / `ENABLE_MULTI_MODEL_ROUTING` | false | 需 DEEPSEEK_API_KEY |
| A 组 4 个 flag | false | 验证达标后按需开 |

**测试结果**: **189 passed**（147 基线 + 29 C + 13 A），前端 `npm run build` 通过，`compileall` 全绿。

---

## Phase 13: 端到端验证 Bug 修复 (Steps 45)

**日期**: 2026-09-14

> 启动后端走通「注册→登录→对话→画像」全流程时发现并修复的 bug。

### Step 45 — 对话 500 错误 + Multi-Judge JSON 健壮性

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `backend/app/services/rag_service.py` | 检索统计 `db.commit()` 加 try/except + `db.rollback()`，失败不阻断检索、不毒化会话 |
| 修改 | `backend/app/services/chat_service.py` | RAG 检索超时 3s→10s（DashScope 向量检索约 2-3s）；两处 except 块补 `db.rollback()` 防会话污染 |
| 修改 | `backend/app/services/judge_service.py` | `max_tokens` 600→1200（避免 `finish_reason=length` 截断 JSON）；加 `response_format={"type":"json_object"}` 强制合法 JSON |
| 修改 | `backend/app/services/llm_service.py` | `chat_completion` 新增 `response_format` 参数透传 |

**Bug 修复**:
- Bug #43：对话 500 `PendingRollbackError` — 根因是 RAG 检索内部 `db.commit()` 在 3s 超时取消时中断，遗留空异常污染会话，后续 commit 连锁失败。修复：commit 加 rollback 保护 + 超时放宽到 10s + except 块补 rollback
- Bug #44：Multi-Judge `finish_reason=length` JSON 截断 — `max_tokens` 600 不够容纳 V2 CoT 推理链
- Bug #45：Multi-Judge JSON 解析失败（reasoning 字符串破坏 JSON）— 加 `response_format={"type":"json_object"}` 强制结构化输出

**端到端验证结果**：注册→登录→创建会话→代码对话（`a='hello'; b=123; c=a+b`）→ 正确诊断 M7 + 共情式引导回复（不给答案）；画像接口 200。Multi-Judge 实测 Kappa 0.4050（moderate，评委真实分歧，无 fallback 掩盖）。

---

## Phase 14: 完善清单 01–13 落地 (Steps 46-52)

**日期**: 2026-10-22

> 按 `PyTutor_后续完善任务清单.md` 执行 P0–P2 工程项；研究项只做到"量尺可用 + 小规模真实试跑"。

### Step 46 — 启动顺序、迁移与知识库自举

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `backend/app/main.py` | lifespan 顺序固定：建表/迁移确认 → 种子误区 → 知识库为空则导入 → TF-IDF → embedding；生产环境跳过 `create_all()` |
| 新增 | `backend/app/rag/seed_data.py` | 知识库正文从脚本抽出，`seed_knowledge()` / `ensure_knowledge_seeded()` |
| 修改 | `backend/scripts/seed_knowledge.py` | 变成薄封装，复用上面的函数 |
| 新增 | `backend/alembic/versions/c2d3e4f5a6b7_normalize_hint_dependency.py` | 归一化历史 `hint_dependency` 值 |
| 新增 | `backend/tests/test_knowledge_seed.py` | 空库导入、二次启动不重复、单篇失败不中断 |
| 修改 | `backend/pyproject.toml` | `.github/workflows/ci.yml` 已改为全量离线测试 + 前端构建 |

**Bug 修复**:
- Bug #46：`hint_dependency` 把 `{"score":..,"label":..}` 写进 `VARCHAR(20)`，SQLite 不报错但教师端 `== 'high'` 永远匹配不上 —— 改为只存标签，读取侧 `normalize_hint_dependency()` 兼容旧值，附数据迁移

### Step 47 — 权限、执行边界与判题

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/sandbox/runner.py` | 统一执行边界：`sandbox_mode` × `isolation_required`；生产无 Docker 返回 `unavailable` |
| 修改 | `backend/app/api/v1/exercises.py` | 服务端统计提示/看答案、首次奖励幂等、执行不可用不判题、通过/失败都更新弱项 |
| 新增 | `backend/tests/test_authz.py` / `test_sandbox_runner.py` | 角色、答案闸门、四种沙箱模式 |

### Step 48 — 误区事件、画像与引导隔离

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `backend/app/services/misconception_service.py` | 记录误区时同步 `recent_misconceptions` |
| 修改 | `backend/app/services/profile_service.py` | `lesson_completed` 维护 `completed_lessons`；`update_weakness` 同步 `weak_topics` |
| 修改 | `backend/app/api/v1/profile.py` | 入门诊断的逐题结果落库（薄弱点 + 误区），返回 `weak_count` |
| 修改 | `frontend/src/components/onboarding-wrapper.tsx` | 引导状态按 `user.id` 隔离；完成时写回同一 key |
| 新增 | `backend/tests/test_onboarding_profile.py` / `test_learning_loop.py` | 诊断→画像→教师看板；完整学习闭环 |

**Bug 修复**:
- Bug #47：引导完成标记用 `token.slice(0,16)`，而同批 JWT 的前缀完全相同，同一浏览器下所有账号共用一个标记 —— 改用 `user.id`

### Step 49 — 回复审核与教学策略

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `backend/app/services/tutor_service.py` | 审核传入真实误区；修订后**再次审核**，分数不再写死为 2；复审失败记为未复核 |
| 修改 | `backend/app/services/pedagogy_service.py` | 单评委失败/解析不出分数 → `score=0, review_available=False` |
| 修改 | `backend/app/services/chat_service.py` | 真实策略/提示等级/质量分写入 `metadata_json` |
| 修改 | `frontend/src/components/chat-message.tsx` | 展示误区名称/置信度/依据、策略来源、降级标记、质量分（仅审核过才显示） |
| 新增 | `backend/tests/test_tutor_review.py` | 失败不伪造分数、修订后重新审核、误区透传 |

**Bug 修复**:
- Bug #48：修订回复后质量分固定为 2，无证据 —— 改为对修订稿重新审核，失败留空
- Bug #49：单评委异常时默认 3 分，下游当成通过 —— 改为 0 分 + 不可评估

### Step 50 — 研究侧：忠实度核验器与真实试跑

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `research/faithfulness/ast_facts.py` | 作用域栈、类型推断、`may_never_terminate`，仅对 Add/Sub/Div/FloorDiv/Pow 判定类型错误 |
| 修改 | `research/faithfulness/faithfulness_verifier.py` | supported/contradicted/unverifiable 边界；零可核验断言返回 N/A |
| 修改 | `research/faithfulness/run_experiment.py` | `build_llm()` 真实接入（显式加载 backend/.env）、断点续跑、token 用量、配对 CI、数据哈希 |
| 修改 | `research/faithfulness/dataset_seed.json` | P04 改为硬负例、P03 标为 intent_dependent、补来源与 schema |
| 新增 | `research/faithfulness/RESULTS.md` + `results_real_deepseek_run{1,2}.json` | 10 条 × 2 条件 × 2 次真实运行 |

### Step 51 — RAG 评测三路打通

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `evaluation/run_rag_eval.py` | tfidf / vector / hybrid 各走真实实现；Hit@K、Recall@K、MRR 分开；覆盖率与跳过原因入库；空库退出码 2 |
| 修改 | 输出路径 | 每种模式写 `rag_eval_results_{mode}.json` |

**结果**：TF-IDF Hit@5 88.9% / MRR 0.889；向量 Hit@5 100% / Recall@5 51.4% / MRR 0.911；Hybrid 在 `ENABLE_HYBRID_WEIGHTS=false` 时与向量一致（不构成融合有效性的证据）。

**Bug 修复**:
- Bug #50：三种模式共用同一个结果文件，后跑的覆盖先跑的 —— 按模式分文件

### Step 52 — 可复现交付

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `docs/REPRODUCIBILITY.md` | 基线、开关矩阵、数据库路径/迁移、数据集哈希、评测口径、状态用词 |
| 重写 | `README.md` | 技术栈与结构对齐现状；安装/启动/测试/评测命令 |
| 修改 | `package.json`（根） | 删除重复依赖声明，只转发到 `frontend/`；删除根 `package-lock.json` |
| 修改 | `.gitignore` | 忽略 `*.bundle` / `*.mp4`；`pytutor.bundle` 取消跟踪 |
| 修改 | `Makefile` | `install` 覆盖前后端，新增 `build-frontend` |

**测试结果**：**233 passed, 12 deselected**；前端 `npm run build` 通过。

### Step 53 — 结果包与 PPT 对齐

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `evaluation/build_results_summary.py` + `results_summary.csv` | 从各结果 JSON 生成 31 行机器可读汇总，避免手抄数字 |
| 新增 | `docs/figures/results-overview.svg` / `-dark.svg` | 浅色/深色结果图：检索三路 Hit@5/Recall@5/MRR + AST 统计卡片 |
| 新增 | `docs/figures/make_figures.py` / `README.md` | 可重生成；含表格视图、配色校验记录、PNG 导出方法 |
| 修改 | `PyTutor_3.0_Academic_Presentation.pptx` | P12 改 10 案例 + RAG 指标；P14 加实测区；P15 加校准边界；P17 加负面分支 |
| 新增 | `docs/CLAIMS-EVIDENCE.md` | 四条主贡献 + 三条支撑主张，逐条列算法、界面、证据与"不能宣称" |
| 修改 | `docs/PPT-ALIGNMENT.md` / `docs/TASK-STATUS.md` / `docs/REPRODUCIBILITY.md` / `README.md` / `CLAUDE.md` | 4 处修改标记为已应用；链接结果图、CSV 与主张矩阵；任务 16 转为完成；修正 flag 默认值与 47 例数据集的旧描述 |

**口径**：图中 Hybrid 与 Vector 相同，并在图上注明是 `ENABLE_HYBRID_WEIGHTS=false` 所致；
AST 四项均标为 same-set。浅色 MRR 对底色的对比度 2.74:1，按 dataviz 规则用表格视图兜底。

### Step 54 — 忠实度抽取器 rules_v2 + 真实重跑

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `research/faithfulness/faithfulness_verifier.py` | `RuleBasedClaimExtractor` 增加 `_clean_markdown()`：丢弃代码块/标题/表格行/分隔线，去掉列表符号与加粗，支持英文句末切分，过滤过短引导句 |
| 修改 | `research/faithfulness/run_experiment.py` | `meta.claim_extractor` 记为 `RuleBasedClaimExtractor/rules_v2` |
| 新增 | `research/faithfulness/results_real_deepseek_v2_run{1,2}.json` | 真实 `deepseek-chat` 两次重跑（各 20 次调用，0 失败） |
| 修改 | `research/faithfulness/RESULTS.md` | 以 v2 为主结果重写；附清理前后断言量对比（621/667 → 278/287） |
| 修改 | `backend/tests/test_faithfulness_verifier.py` | 新增 `TestMarkdownIsNotAClaim`（5 个用例） |
| 修改 | `docs/TASK-STATUS.md` / `docs/REPRODUCIBILITY.md` / `docs/CLAIMS-EVIDENCE.md` / `PyTutor_3.0_Academic_Presentation.pptx` | 同步 v2 数字与"C2 两次都未优于 C1"的结论；PPT P14 实测区改为新数字 |

**Bug 修复**:
- Bug #51：Markdown 标题、代码块、表格行被当作断言计入未核验，导致忠实度分母含大量噪声 ——
  抽取前先清洗格式行；断言总量下降约 55%，未核验噪声下降约 60%

**结果**：C1/C2 为 0.683/0.647（run1）、0.667/0.650（run2），配对差 −0.127、−0.090，95% CI 均含 0。
结论从"方向不稳定"改为"没有证据表明 C2 更优，点估计偏向 C1"；仍不能宣称证据注入有效。

### Step 55 — RAG 评测补充上下文 token

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `evaluation/run_rag_eval.py` | 每个查询记录 Top-K chunk 的估算 token 之和，汇总 `mean/max/total_context_tokens`；控制台与 `metric_definitions` 同步说明口径 |
| 修改 | `evaluation/build_results_summary.py` + `results_summary.csv` | 三路检索各加一行 `mean_context_tokens` |
| 修改 | `docs/TASK-STATUS.md` / `docs/REPRODUCIBILITY.md` / `docs/CLAIMS-EVIDENCE.md` | 任务 13 的"未报告 token"缺口关闭；表格补 token 列 |

**结果**：TF-IDF 242.3（最大 369）、向量 315.2（最大 455）、Hybrid 315.2（同向量）。
口径：`app/rag/splitter.estimate_tokens()` 估算（CJK 1 字 ≈ 1 token，其余 4 字符 ≈ 1 token），
不是分词器精确计数；9 条查询仍是 smoke 规模。

### Step 56 — 关闭未对齐的 SSE 入口（任务 17 决策）

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `backend/app/api/v1/chat.py` | `POST /chat/sessions/{id}/stream` 不再流式返回，改为 **501** 并指向非流式入口 |
| 修改 | `backend/app/services/chat_service.py` | 删除 `send_message_stream`：它缺 RAG/诊断/画像/审核，且 `session.messages` 在异步上下文有懒加载风险 |
| 修改 | `backend/tests/test_authz.py` | 新增 `TestStreamingDisabled`：断言 501 且提示使用 messages 接口，不触库 |

**理由**：清单 17 允许"没有体验需求时保留非流式入口"。保留一个会给出降级回复的公开端点
比不提供更容易造成"两套接口诊断不一致"，因此显式关闭而不是静默降级。

### Step 57 — RAG 黄金集扩到 30 条并重跑三路

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `evaluation/rag_golden.json` | 从 9 条可答 + 2 条无答案扩到 **30 条可答 + 5 条无答案**（新增 g013–g036）；sha256 前缀 `e12dd15fc2fd54e7` |
| 重跑 | `evaluation/rag_eval_results_{tfidf,vector,hybrid}.json` | 30 条查询上重跑三路，含 Top-5 上下文 token |
| 修改 | `docs/figures/make_figures.py` / `README.md` / `results-overview.svg`（含深色） | 图与表同步到 0.900/0.407/0.900（TF-IDF）、0.933/0.501/0.890（向量） |
| 修改 | `evaluation/build_results_summary.py` + `results_summary.csv` | 34 行；RAG caveat 改为 30 条单作者 smoke 基线 |
| 修改 | `docs/REPRODUCIBILITY.md` / `docs/CLAIMS-EVIDENCE.md` / `docs/DATA_CARD.md` / `docs/TASK-STATUS.md` / `CLAUDE.md` | 同步数字、哈希与"MRR 略低于 TF-IDF、无拒答能力"的边界 |

**结果**：向量相对 TF-IDF：Hit@5 90.0% → 93.3%，Recall@5 40.7% → 50.1%，MRR 0.900 → 0.890；
Top-5 上下文 251 → 315 token（估算）。Hybrid 仍与向量一致（`ENABLE_HYBRID_WEIGHTS=false`）。
**不能说**"向量全面优于 TF-IDF"：MRR 点估计略低；查询仍为单作者标注。

### Step 58 — 诊断留出集（30 + 15 条）

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `evaluation/v2_holdout_cases.json` | 30 条新写误区正例，覆盖 M1–M8；sha256 前缀 `8d3e008fdb3c76b7` |
| 新增 | `evaluation/holdout_clean_cases.json` | 15 条干净代码；sha256 前缀 `a4a69607f88c5a3e` |
| 修改 | `evaluation/run_v2_eval.py` | `run_ast_only_eval()` 接受 dataset/clean/output；新增 `--dataset`、`--clean`、`--out` |
| 新增 | `evaluation/v2_holdout_results.json` | 留出集结果 |
| 修改 | `docs/DATA_CARD.md` / `docs/REPRODUCIBILITY.md` / `docs/CLAIMS-EVIDENCE.md` / `docs/TASK-STATUS.md` | 记录规模、哈希、结果与"未据此调规则" |

**结果**：exact match **0.833（25/30）**、macro-F1 0.883、干净代码误报 **0/15**；
漏检集中在 H18–H20（M5，recall 0.25）与 H22/H24（M6，recall 0.50）。
这是项目第一个非训练集上的泛化估计；同集的 1.000 仍只能说明规则自洽。

### Step 59 — 生产化加固（依赖、迁移、CI、认证与限流）

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `backend/requirements.txt` | 全部精确 pin；移除未使用的 `sentence-transformers`；加入 ruff、pytest-cov |
| 新增 | `backend/alembic/versions/d3e4f5a6b7c8_add_profile_learning_fields.py` | 补 2.0 画像四字段；幂等加列；head 变为 `d3e4f5a6b7c8` |
| 修改 | `backend/alembic/versions/c2d3e4f5a6b7_normalize_hint_dependency.py` | 列不存在时直接返回，避免空库链式迁移失败 |
| 修改 | `.github/workflows/ci.yml` | 精确版本安装 → compileall → ruff 错误门（E9/F63/F7/F82）→ 空库迁移并断言四个画像列 → pytest 覆盖率门 40% → `npm ci --legacy-peer-deps` + build |
| 新增 | `backend/app/core/rate_limit.py` + `tests/test_rate_limit.py` | 进程内滑动窗口限流；登录/注册 10 次/分/IP，普通 API 120 次/分/IP；健康检查与 CORS 预检跳过 |
| 修改 | `backend/app/core/config.py` / `backend/app/main.py` | `RATE_LIMIT_*` 配置；中间件注册 |
| 新增 | `backend/tests/test_auth_service.py` | 7 个用例：密码盐/校验、JWT 往返/篡改/过期、注册/登录、重复 409、统一 401、禁用 403 |
| 新增 | `docs/DEPLOYMENT.md` | 三种环境的判题边界；Render 无 Docker 时 `unavailable`；迁移与限流注意事项 |

**Bug 修复**:
- Bug #52：2.0 画像字段只靠手工 `ALTER TABLE`，空库 `alembic upgrade head` 在
  `c2d3e4f5a6b7` 处报 `no such column: hint_dependency` —— 新增幂等迁移，CI 用空库验证
- Bug #53：`app/main.py` lifespan 内局部 `from app.database.session import AsyncSessionFactory`
  使该名字在整个函数内变成本地变量，前面几处种子写入抛 `UnboundLocalError` 并被
  `try/except` 吞掉 → 误区/知识库种子静默跳过。移除局部导入后恢复；由 ruff F823 捕获

**测试结果**：**251 passed, 12 deselected**，覆盖率 47%；ruff 错误门通过；空库迁移 head `d3e4f5a6b7c8`。

### Step 60 — 忠实度人工抽查工具

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `evaluation/build_spotcheck.py` | 从 v2 run1 确定性分层抽样：每个「判定 × 条件」5 条，共 30 条；按题目轮转避免单题占满 |
| 新增 | `evaluation/faithfulness_spotcheck.csv` | 11 列；人工列（`human_extraction_ok` / `human_verdict` / `notes`）留空，UTF-8 BOM 便于 Excel |
| 新增 | `docs/FAITHFULNESS-SPOTCHECK.md` | 填写规则、空白汇总表、填完后需同步的 6 个位置、为什么不能自动填 |

**边界**：这一步只交付工具与抽样表，**没有**填入任何人工判定；"抽取/判定一致率"必须等人填完后才能写。

### Step 61 — 结果包补入留出集与人工抽查入口

| 操作 | 文件 | 说明 |
|------|------|------|
| 修改 | `evaluation/build_results_summary.py` | 新增 `ast_diagnosis_holdout` 六行：exact match、macro-F1、FP rate、平均延迟、M5/M6 recall；CSV 从 34 行增至 **40 行** |
| 修改 | `docs/figures/README.md` | 增加留出集表格；CSV 行数更新；数据出处补 `v2_holdout_results.json` |
| 修改 | `docs/TASK-STATUS.md` | 任务 10 指向抽查表；修正"留出集还没做"的旧说法；待人工事项拆成二次标注/人工抽查/盲评/校准 |
| 修改 | `docs/FAITHFULNESS-SPOTCHECK.md` | 抽样说明改为每桶 5 条、固定 seed、脚本路径 |

**口径**：图中右栏仍只画同集卡片；留出集只进表格与 CSV，避免读者把 25/30 误读成同集结果。

### Step 62 — 全量代码审计修复（功能可用性 / 数据正确性 / 安全边界）

审计范围：后端全部路由与服务、沙箱三层、RAG 写入删除、前端练习与对话页。
原则：先补能复现问题的测试，再改代码；不含论文/证据类内容。

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/sandbox/process.py` | 输出限额读取 `communicate_with_limit`；Windows `taskkill /T` 杀进程树 |
| 修改 | `backend/app/sandbox/executor.py` | 合并为单一 `_run_python`；环境变量白名单；独立临时目录作 cwd；强制 `strict=True`；输出上限 100KB |
| 修改 | `backend/app/sandbox/security.py` | `STRICT_FORBIDDEN_MODULES/PATTERNS`；`check_code_safety(code, strict)` |
| 修改 | `backend/app/sandbox/docker_executor.py` | 容器名带 `uuid4`；超时与 `finally` 都 `docker rm -f`；输出限额 |
| 修改 | `backend/app/services/chat_service.py` | `resolve_model_choice()` 白名单；用户消息先落库；RAG 失败不 rollback；LLM 失败 `_recover_user_message()` + 503 |
| 修改 | `backend/app/api/v1/chat.py` / `schemas/chat.py` | 删除返回 404/403；改名用 `RenameSessionRequest`（1–100 字符） |
| 修改 | `backend/app/services/rag_service.py` / `rag/vector_store.py` | 向量写入改 `asyncio.to_thread`；新增 `delete_chunks`；`search` 在 collection 为空时安全返回 |
| 修改 | `backend/app/api/v1/rag.py` | 导入/删除/详情走 404；删除三处一起清；`chunk_count` 不再读 lazy relationship；列表用 `GROUP BY` 计数 |
| 修改 | `backend/app/api/v1/exercises.py` / `schemas/exercise.py` | 请求体模型化并限长；按 `solution_views_total` 判定"本次看答案"；`exercise_stats` 统一统计 |
| 新增 | `backend/app/services/exercise_stats.py` | 答题事件读取/聚合：`load_attempt_events`、`is_counted_pass`、`passed_exercise_ids`、`passed_count_by_user` |
| 修改 | `backend/app/api/v1/admin.py` / `profile.py` / `teacher.py` | 按题目而非概念统计；批量取用户；`group_by` 补全字段；最后一个管理员不可降级/禁用 |
| 修改 | `backend/app/api/v1/misconception_exercises.py` | 种子接口限 admin/teacher；幂等比对带前缀标题；清理历史重复行 |
| 修改 | `backend/app/core/config.py` / `rate_limit.py` | `TRUST_PROXY_HEADERS` 默认 false；生产配置校验（debug/弱密钥直接拒绝） |
| 修改 | `backend/app/main.py` | 生产不回显异常详情；lifespan 异常在生产重新抛出 |
| 修改 | `backend/app/services/auth_service.py` / `code_service.py` / `exercise_service.py` / `misconception_service.py` | 登录 dummy bcrypt；注册并发 409；代码运行校验会话/题目归属；参考解答预检；服务层只 `flush` 不 `commit` |
| 修改 | `frontend/src/app/exercises/page.tsx` / `page.tsx` / `lib/api.ts` / `lesson-player.tsx` | 练习列表去重请求；提交体只传 `code`；删除/重命名会话实现；去掉死 SSE 代码；进度越界钳制 |
| 新增测试 | `tests/test_chat_resilience.py` / `test_rag_ingest.py` / `test_exercise_scoring.py` / `test_seed_mc_exercises.py` | 13 个用例覆盖下列每个 Bug |
| 修改测试 | `tests/test_onboarding_profile.py` / `test_rate_limit.py` | 适配请求体模型；新增伪造 XFF 不能绕过限流的用例 |

**Bug 修复**:
- Bug #54：`ingest_document` 用 `doc.chunks` 构造向量数据，async 会话里 relationship 未加载
  抛 `MissingGreenlet` → `POST /rag/documents` 500，启动时知识库种子永远写不进向量库
- Bug #55：删除 RAG 文档只清 DB 和 TF-IDF，ChromaDB 残留 → 已删文档仍被检索到
- Bug #56：聊天 RAG 检索异常时 `await db.rollback()`，把尚未提交的用户消息一并回滚，
  随后 `refresh` 抛 `InvalidRequestError`，整轮对话 500
- Bug #57：LLM 生成失败分支先 rollback 再 commit，看似"保存用户消息"，实际什么都没保存
- Bug #58：`SendMessageRequest.model` 任意字符串直接透传给 litellm，`openai/gpt-4o` 也能通；
  且 `model=None` 时回落到 `request.model` 再次绕过校验
- Bug #59：看过参考答案后同一次提交仍拿满分与首次通关奖励。原实现靠"倒序扫描事件"，
  而 SQLite `CURRENT_TIMESTAMP` 只到秒、UUID 主键无时间序，判定不可靠 → 改单调计数
- Bug #60：管理端"已完成题目"按 `concept` 去重、`/me/passed` 只取最近 50 条，
  多用户时还会串数据 → 统一按 `user_id + exercise_id` 聚合
- Bug #61：误区专项练习种子接口无鉴权，学生也能写库；幂等判断拿无前缀 `title` 比
  入库的 `[M1] 标题`，永远不相等 → 每调用一次多插 16 道题
- Bug #62：沙箱子进程继承完整环境变量，学生代码可 `os.environ["DEEPSEEK_API_KEY"]` 读到密钥
- Bug #63：strict 安全检查未接入，`open('.env')`、`importlib` 可执行；超时/输出上限
  只在部分路径生效 → 公开入口统一 `strict=True` + 100KB 截断
- Bug #64：Docker 容器名固定，并发运行互相顶掉；超时只 kill 进程不删容器，留下僵尸容器
- Bug #65：限流默认信任 `X-Forwarded-For`，客户端伪造该头即可每条请求换一个 IP
- Bug #66：生产环境可带着 `DEBUG=true` 或弱 `SECRET_KEY` 启动；500 响应与 `/health`
  在任何环境都回显异常详情；lifespan 初始化异常被 `try/except` 吞掉
- Bug #67：登录时用户不存在直接返回，bcrypt 时间差可枚举已注册邮箱；并发同邮箱注册
  撞唯一键抛 500 而不是 409
- Bug #68：删除会话/文档、管理员改用户等接口返回 `200 + {"detail": ...}`，前端无法区分失败；
  管理员可把最后一个管理员降级或禁用，锁死后台
- Bug #69：请求体无校验：会话改名可为空/超长，提交代码无长度上限，
  `hint_level` 可越界；`used_hints` / `viewed_solution` 由前端传入即可影响评分
- Bug #70：代码运行接口不校验 `session_id` / `exercise_id` 归属与存在性 →
  可把消息写进别人的会话或不存在的题目
- Bug #71：参考解答从不预检，测试用例写错的坏题会直接发给学生 → 发布前跑一遍，
  不过则置 `is_published=False` 并跳过，不返回给前端
- Bug #72：前端练习中心在 `store` 每次变化时重拉题目列表；提交体字段与后端不一致；
  会话删除/重命名只有 UI 没有实现；本地进度越界时 `lesson-player` 直接白屏

**测试结果**：**267 passed, 12 deselected**；`ruff --select E9,F63,F7,F82 app tests` 通过；
`tsc --noEmit` 无错误；`TestClient` 启动 lifespan 后 `/api/v1/health` → `api/database healthy`。

#### Step 62 补充 — 复查发现的接口契约问题

| 操作 | 文件 | 说明 |
|------|------|------|
| 新增 | `backend/app/schemas/misconception.py` | `DiagnoseRequest`（code ≤20k、stderr ≤5k、exercise_id ≤64） |
| 修改 | `backend/app/schemas/code.py` / `exercise.py` | `AnalyzeErrorRequest`（code ≤50k、stderr ≤10k）；`ExercisePublishRequest` |
| 修改 | `backend/app/api/v1/admin.py` / `code.py` / `misconceptions.py` | 缺资源改抛 404/403；`body: dict` 换成模型；`diagnose` 校验 `exercise_id` 存在性 |
| 新增测试 | `backend/tests/test_api_error_contract.py` | 5 个用例：404/403/长度上限 |

**Bug 修复**:
- Bug #73：找不到资源时仍返回 `200 {"detail": "..."}`（`GET /admin/students/{id}`、
  `PATCH /admin/exercises/{id}`、`GET /code/submissions/{id}`），前端 `res.ok` 为真，
  把错误当成功渲染
- Bug #74：`POST /code/analyze`、`POST /misconceptions/diagnose` 收 `body: dict`，
  代码长度无上限且直接拼进 LLM prompt；`diagnose` 的 `exercise_id` 也不校验，
  可写出一条挂着不存在练习的事件
- Bug #75：7 处裸 `except:` 会把 `CancelledError` / `KeyboardInterrupt` 一起吞掉，
  异步任务取消后继续往下跑 → 统一为 `except Exception`

**测试结果**：**272 passed, 12 deselected**；ruff 错误门通过。
