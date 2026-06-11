# PyTutor 全项目架构文档

> 从 1.0 MVP 到 2.0 Misconception-Aware AI Tutoring 的完整设计、实现与优化记录

---

## 目录

1. [项目概述](#1-项目概述)
2. [技术栈](#2-技术栈)
3. [系统架构](#3-系统架构)
4. [需求→代码映射](#4-需求代码映射)
5. [完整修改时间线](#5-完整修改时间线)
6. [Bug 修复记录](#6-bug-修复记录)
7. [数据库设计](#7-数据库设计)
8. [API 端点清单](#8-api-端点清单)
9. [前端组件树](#9-前端组件树)
10. [关键设计决策](#10-关键设计决策)

---

## 1. 项目概述

### 1.1 一句话定位

**PyTutor 2.0** — 面向 Python 初学者的 AI 引导式、误区感知型编程学习平台。

### 1.2 核心能力

| 能力 | 说明 |
|------|------|
| AI 对话 | DeepSeek 驱动的智能导师，支持 CHAT/REASONING 双模式 |
| 代码实验室 | 安全沙箱执行，stdin/stdout/stderr + AI 解释 |
| 新手教程 | 12 课完整教程，AI 分步引导 + 实时编码 |
| 基础诊断 | 6 题诊断 → 报告 → 个性化补漏路径 |
| 练习中心 | ACM 模式，自动判题 + 误区诊断 + 渐进提示 |
| 误区诊断 | M1-M8 八类误区，规则+LLM 双通道 |
| 教学策略 | 7 种策略 + 5 级渐进提示 |
| 学习画像 | 薄弱点、误区、提示依赖追踪 |
| 教师仪表盘 | 全班统计分析 |
| RAG 检索 | DashScope 语义向量 + TF-IDF 混合检索 |

### 1.3 用户角色

| 角色 | 入口 | 可见功能 |
|------|------|----------|
| Student | AI对话/练习/画像 | 教程、诊断、练习中心、AI对话 |
| Instructor | 教学分析 | 教师仪表盘 |
| Admin | 管理后台 | 用户管理、题库管理、系统日志 |

---

## 2. 技术栈

### 后端
```
FastAPI + Uvicorn          # 异步 Web 框架
Pydantic v2 + Settings     # 数据校验 + 配置
SQLAlchemy 2.0 (async)     # ORM
SQLite (dev) / PostgreSQL  # 数据库
Alembic                   # 迁移
bcrypt + python-jose      # 安全（密码 + JWT）
LiteLLM                   # LLM 统一网关（DeepSeek）
LangGraph                 # Agent 工作流编排
ChromaDB                  # 向量数据库
DashScope text-embedding-v3  # 语义向量 API
structlog                 # 结构化日志
Docker                    # 代码沙箱
```

### 前端
```
Next.js 16 (Turbopack)    # React 框架
React 19                  # UI
Tailwind CSS 4            # 样式
Zustand                   # 状态管理
Monaco Editor             # 代码编辑器
react-markdown             # AI 回复渲染
Vercel AI SDK             # SSE 流式对话
```

### 测试 & CI
```
pytest + pytest-asyncio   # 后端测试
ruff                      # 代码检查
GitHub Actions            # CI pipeline
```

---

## 3. 系统架构

### 3.1 整体数据流

```
浏览器 (Next.js)
    │
    ├─ /api/v1/* ──→ FastAPI ──→ SQLAlchemy ──→ SQLite/PostgreSQL
    │                    │
    │                    ├─→ LiteLLM ──→ DeepSeek API
    │                    ├─→ ChromaDB + DashScope (RAG)
    │                    ├─→ LangGraph Agent (工作流)
    │                    ├─→ Docker Sandbox (代码执行)
    │                    └─→ Langfuse/OTel (可观测，可选)
```

### 3.2 后端分层

```
backend/app/
├── api/v1/              # 路由层 (13 个模块)
│   ├── auth.py          #   注册/登录
│   ├── users.py         #   用户信息
│   ├── chat.py          #   AI 对话 + SSE 流
│   ├── code.py          #   代码执行
│   ├── exercises.py     #   练习 CRUD + 提交 + 提示
│   ├── profile.py       #   学习画像 + 引导
│   ├── misconceptions.py #  误区诊断
│   ├── misconception_exercises.py  # 误区专项练习种子
│   ├── teacher.py       #   教师仪表盘
│   ├── admin.py         #   管理后台
│   ├── agent.py         #   LangGraph Agent
│   ├── rag.py           #   知识库管理
│   └── router.py        #   路由聚合
│
├── services/            # 业务逻辑层 (11 个模块)
│   ├── auth_service.py
│   ├── chat_service.py
│   ├── code_service.py
│   ├── exercise_service.py
│   ├── profile_service.py
│   ├── tutor_service.py
│   ├── llm_service.py       # LiteLLM 网关
│   ├── rag_service.py
│   ├── misconception_service.py
│   ├── pedagogy_service.py
│   └── verify_service.py    # (pedagogy 内置)
│
├── models/              # 数据模型 (9 个)
│   ├── user.py
│   ├── chat.py
│   ├── profile.py          # StudentProfile + Weakness + LearningEvent
│   ├── misconception.py    # 2.0 新增
│   ├── exercise.py
│   ├── submission.py
│   ├── rag.py
│   ├── prompt.py
│   └── __init__.py
│
├── rag/                 # RAG 子系统
│   ├── embedding.py        # DashScope API 封装 (2.0)
│   ├── vector_store.py     # ChromaDB 操作
│   ├── retriever.py        # TF-IDF 检索
│   ├── reranker.py
│   ├── splitter.py
│   └── loader.py
│
├── agents/              # LangGraph 工作流
│   ├── state.py
│   ├── graph.py
│   └── nodes/              # 安全检查 → 意图 → RAG → 生成 → 校验
│
├── sandbox/             # 代码安全执行
│   ├── executor.py
│   ├── docker_executor.py
│   └── security.py
│
├── data/                # 种子数据
│   ├── misconceptions.json   # M1-M8 定义
│   └── mc_exercises.py       # 16 题数据
│
├── core/                # 配置 & 基础
│   ├── config.py
│   ├── exceptions.py
│   └── logging_config.py
│
├── database/            # DB 连接
│   ├── base.py             # TimestampMixin (id, created_at, updated_at)
│   └── session.py
│
├── security/            # 认证
│   ├── password.py
│   ├── jwt.py
│   └── dependencies.py
│
├── observability/       # 可观测
│   ├── logger.py
│   ├── middleware.py
│   ├── langfuse_setup.py
│   └── otel_setup.py
│
├── schemas/             # Pydantic Schema
│   ├── common.py           # ResponseModel 统一响应
│   ├── auth.py
│   ├── chat.py             # AIResponse 2.0 字段
│   ├── ai.py
│   ├── code.py
│   ├── exercise.py
│   └── rag.py
│
└── main.py              # FastAPI 入口 + lifespan
```

### 3.3 前端组件树

```
layout.tsx
├── NavLink (AI对话/练习中心/学习画像/教学分析)
├── NavUser (登录/注册/用户菜单)
├── OnboardingWrapper
│   ├── OnboardingModal    # 四入口选择
│   ├── DiagnosticFlow     # 6题诊断 (入口B)
│   └── LessonPlayer       # 12课教程 (入口A/B)
└── main
    ├── page.tsx           # AI 对话主页
    │   ├── ChatMessage     # 含 hint/strategy/misconception 徽章
    │   └── Monaco Editor   # 代码面板 (stdin + 输出)
    ├── exercises/page.tsx  # 练习中心
    ├── profile/page.tsx    # 学习画像 (2.0 误区卡片)
    ├── teacher/page.tsx    # 教师仪表盘
    ├── admin/page.tsx      # 管理后台
    ├── login/page.tsx      # 登录 (密码眼睛)
    └── register/page.tsx   # 注册 (密码眼睛)
```

---

## 4. 需求→代码映射

### SRS 2.0 章节映射

| SRS 章节 | 功能 | 后端文件 | 前端文件 |
|----------|------|----------|----------|
| 7.1-7.3 新手引导 | 四入口 + Lesson 0 | `profile.py`, `profile_service.py` | `onboarding-modal.tsx`, `onboarding-wrapper.tsx`, `lesson-player.tsx`, `tutorial-data.ts` |
| 7.2 基础选择 | 四入口差异化 | `profile.py:POST /onboarding` | `onboarding-wrapper.tsx` |
| 8. AI Tutor | 对话 + Debug 模式 | `chat_service.py`, `tutor_service.py`, `llm_service.py` | `page.tsx`, `chat-message.tsx` |
| 9. Code Lab | 编辑/运行/stdin/输出 | `code.py`, `executor.py` | `page.tsx`(代码面板) |
| 10. 误区体系 | M1-M8 定义 | `misconception.py`, `misconceptions.json` | - |
| 11. 误区诊断 | 规则+LLM | `misconception_service.py`, `misconceptions.py` | `exercises/page.tsx` |
| 12. 教学策略 | 7策略+选择器 | `pedagogy_service.py` | `chat-message.tsx` |
| 13. 渐进提示 | 5级系统 | `pedagogy_service.py`, `exercises.py` | `exercises/page.tsx` |
| 14. 学习画像 | 4新字段 | `profile.py`(model), `profile_service.py` | `profile/page.tsx` |
| 15. AI结构化 | 2.0字段 | `chat.py`(schema), `tutor_service.py` | `chat-message.tsx` |
| 16. 回复检查 | verify_response | `pedagogy_service.py`, `tutor_service.py` | - |
| 17. 练习增强 | 误区专项 | `misconception_exercises.py`, `mc_exercises.py` | `exercises/page.tsx` |
| 18. 数据模型 | misconceptions/hint | `misconception.py` | - |
| 19. API新增 | diagnose/misconceptions | `misconceptions.py`, `profile.py` | - |
| 21. 评估 | Baseline | `run_v2_eval.py`, `v2_test_cases.json` | - |
| 22-25. 教程+诊断 | 完整教程系统 | - | `tutorial-data.ts`, `diagnostic-tasks.ts`, `diagnostic-flow.tsx`, `misconception-exercises.ts` |
| 教师视图 | 仪表盘 | `teacher.py` | `teacher/page.tsx` |

---

## 5. 完整修改时间线

### Phase 1: MVP 后端骨架 (2026-06-08)

| Step | 内容 | 关键文件 |
|------|------|----------|
| 1 | FastAPI 骨架 | `main.py`, `config.py` |
| 2 | 结构化日志 | `logging_config.py`, `logger.py`, `middleware.py` |
| 3 | 数据库基础 | `session.py`, `base.py`, `user.py` |
| 4 | 用户认证 | `auth.py`, `password.py`, `jwt.py`, `auth_service.py` |
| 5 | AI 服务 | `llm_service.py`, `ai.py`(schema) |
| 6 | Docker 化 | `Dockerfile`, `docker-compose.yml` |

### Phase 2: AI 聊天 + RAG + 沙箱 (2026-06-08)

| Step | 内容 | 关键文件 |
|------|------|----------|
| 7-9 | Chat + RAG 基础 | `chat.py`, `rag_service.py`, `retriever.py` |
| 10-14 | 练习 + 代码 + Agent | `exercises.py`, `code.py`, `agents/` |

### Phase 3-6: 前端 + 工业升级 (2026-06-08 ~ 2026-06-11)

| Phase | 内容 |
|-------|------|
| 3 | 前端开发（Next.js + Tailwind） |
| 4 | 管理后台 + 评测 + Prompt |
| 5 | UI 重设计 + ACM 练习中心 |
| 6 | LiteLLM + SSE + ChromaDB + Langfuse + Ragas |

### Phase 7: RAG 语义向量升级 (2026-06-11)

| Step | 内容 | 关键文件 |
|------|------|----------|
| 20 | DashScope API 替换本地模型 | `embedding.py`(新), `vector_store.py`(重写) |

### Phase 8: PyTutor 2.0 核心 (2026-06-11)

| Step | 内容 | 关键文件 |
|------|------|----------|
| 22-23 | 误区分类+诊断 | `misconception.py`, `misconception_service.py`, `misconceptions.json` |
| 24 | 教学策略+渐进提示 | `pedagogy_service.py`, `chat_service.py` |
| 25-26 | 学习画像+评估 | `profile.py`(2.0字段), `v2_test_cases.json` |

### Phase 9: 教程系统 (2026-06-11)

| Step | 内容 | 关键文件 |
|------|------|----------|
| 27 | 7课教程+LessonPlayer | `tutorial-data.ts`, `lesson-player.tsx` |
| 28 | 退出+进度持久化 | `lesson-player.tsx`(+exit), `onboarding-wrapper.tsx`(+resume) |
| 29 | stdin+输出扩大 | `lesson-player.tsx`, `page.tsx` |

### Phase 10: 入口 B/C + 教学策略接入 + 评估 + 补全 (2026-06-12)

| Step | 内容 | 关键文件 |
|------|------|----------|
| 30 | DiagnosticFlow | `diagnostic-tasks.ts`, `diagnostic-flow.tsx` |
| 31 | 教学策略前端接入 | `exercises.py`(hint), `chat-message.tsx`(+badges) |
| 32 | 回复自检+Baseline | `tutor_service.py`(+verify), `run_v2_eval.py` |
| 33 | Lesson 6-10 + 误区练习 | `tutorial-data.ts`(+5课), `misconception-exercises.ts` |
| 34 | 教师仪表盘 | `teacher.py`, `teacher/page.tsx` |
| 35 | 代码重构 | `mc_exercises.py`(数据分离), `router.py`(导入统一) |
| 36 | CI/CD + 28测试 | `.github/workflows/ci.yml`, `conftest.py`, 5个测试文件 |

---

## 6. Bug 修复记录

| # | 问题 | 根因 | 修复 | 日期 |
|---|------|------|------|------|
| 1 | Windows GBK emoji 报错 | 终端编码 GBK vs 源码 UTF-8 | ASCII 标签替代 emoji | 06-08 |
| 2 | passlib+bcrypt 不兼容 | passlib 1.7.4 依赖 bcrypt.__about__ | 原生 bcrypt | 06-08 |
| 3 | EmailStr 缺依赖 | pydantic 不强制安装 email-validator | 安装 email-validator | 06-08 |
| 4 | datetime 序列化 | Schema str vs ORM datetime | datetime 类型 + field_serializer | 06-08 |
| 5 | 端口占用 | 残留 uvicorn 进程 | taskkill | 06-08 |
| 6 | Greenlet 懒加载 | async 下 Pydantic 访问 relationship | 手动构造 Response | 06-08 |
| 7 | related_concepts 类型 | DB 逗号串 vs Schema list | field_validator(mode="before") | 06-08 |
| 8 | 日志 UnicodeEncodeError | GBK 终端 + emoji | UTF-8 wrapper + ASCII 清理 | 06-08 |
| 9 | bytes 中文字符 | b"..." 只能 ASCII | .encode("utf-8") | 06-08 |
| 10 | RAG 索引重启丢失 | 内存索引 | lifespan rebuild_index() | 06-08 |
| 11 | JSON 输出不稳定 | DeepSeek 不严格遵守 JSON | 取消 JSON 要求 | 06-08 |
| 12 | content 存 JSON 乱码 | AI 回复 JSON 存 content 字段 | 只存 message 文本 | 06-08 |
| 13 | 会话历史丢失 | 同上 | content 纯文本化 | 06-08 |
| 14 | 中文乱码(10轮) | 两个执行函数 UTF-8 不一致 | -X utf8 | 06-08 |
| 15 | ACM 空输入 EOFError | stdin 传 None | 传 b"" | 06-08 |
| 16 | 安全拦截误杀 | 黑名单太广 | 去掉注释+字符串再检查 | 06-08 |
| 17 | sanitize_code 被误删 | 重构丢失 | 内联替代 | 06-08 |
| 18 | "use client" 位置 | 服务端组件导入客户端模块 | 拆出 NavLink 组件 | 06-08 |
| 19 | 练习换题不清状态 | Zustand 未 reset | 切换时清空 | 06-08 |
| 20 | AI 聊天卡死 485s | SentenceTransformer HF 下载阻塞 | 15s 超时+executor+失败标记 | 06-11 |
| 21 | 向量索引写入 0 条 | db.execute() 迭代器耗尽 | result.all() 物化 | 06-11 |
| 22 | 生成题目即显示 ✅ | 概念标签匹配 | 改为题目 ID 匹配 | 06-11 |
| 23 | 练习完成数翻倍 | exercises.py + record_event 双重计数 | record_event 统一管理 | 06-11 |
| 24 | 做对不打勾+结果丢失 | already_passed 按概念去重 | 按 exercise_id 去重 | 06-11 |
| 25 | profile 接口返回 null | create_all 不修改已有表 | ALTER TABLE ADD COLUMN | 06-11 |
| 26 | 新用户看到旧进度 | localStorage key 用 token | 改为 user.id | 06-11 |
| 27 | 管理员 SQLite 直插无法登录 | bcrypt 哈希格式不兼容 | 通过 API 注册 | 06-12 |
| 28 | 教师/管理员看到弹窗 | 未检查 role | user.role !== "student" | 06-12 |
| 29 | 管理员仍看到弹窗 | user 未加载完 role 为 undefined | 等 user 就绪后再检查 | 06-12 |

---

## 7. 数据库设计

### 7.1 核心表 (12 张)

```
users                    # 用户 (email, password_hash, role, display_name)
chat_sessions            # 对话会话 (student_id, title)
chat_messages            # 对话消息 (session_id, role, content, response_type...)
student_profiles         # 学习画像 (user_id, level, total_*, weak_topics, 
                         #   recent_misconceptions, hint_dependency, completed_lessons)
student_weaknesses       # 薄弱点 (user_id, concept, fail_count, severity)
learning_events          # 学习事件 (user_id, event_type, concept, detail_json)
exercises                # 练习题 (title, description, difficulty, concepts,
                         #   example_input, example_output, reference_solution)
test_cases               # 测试用例 (exercise_id, input_data, expected_output)
code_submissions         # 代码提交 (user_id, code, stdout, stderr, status)
rag_documents            # RAG 文档 (title, content, difficulty, concepts)
rag_chunks               # RAG 片段 (document_id, chunk_index, content, tokens)
misconceptions           # 2.0: 误区定义 (code, name, description, typical_patterns)
misconception_events     # 2.0: 误区事件 (user_id, misconception_id, confidence)
```

### 7.2 关键索引

- `users.email` UNIQUE
- `student_profiles.user_id` UNIQUE, FK→users
- `chat_messages.session_id` FK→chat_sessions
- `misconception_events.user_id` FK→users
- `misconception_events.misconception_id` FK→misconceptions

---

## 8. API 端点清单

### 认证
```
POST /api/v1/auth/register
POST /api/v1/auth/login
```

### 用户
```
GET  /api/v1/users/me
```

### 聊天
```
POST /api/v1/chat/sessions
GET  /api/v1/chat/sessions
GET  /api/v1/chat/sessions/{id}
POST /api/v1/chat/sessions/{id}/messages
POST /api/v1/chat/sessions/{id}/stream    (SSE)
PATCH /api/v1/chat/sessions/{id}
DELETE /api/v1/chat/sessions/{id}
```

### 代码
```
POST /api/v1/code/submit
POST /api/v1/code/analyze
```

### 练习
```
GET    /api/v1/exercises
POST   /api/v1/exercises/generate
GET    /api/v1/exercises/{id}
POST   /api/v1/exercises/{id}/submit
POST   /api/v1/exercises/{id}/hint
GET    /api/v1/exercises/{id}/solution
POST   /api/v1/exercises/seed-mc-exercises   (2.0)
```

### 画像
```
GET  /api/v1/profile/me
GET  /api/v1/profile/me/weaknesses
GET  /api/v1/profile/me/passed
GET  /api/v1/profile/me/passed-ids           (2.0)
GET  /api/v1/profile/me/misconceptions       (2.0)
GET  /api/v1/profile/me/recommendations
POST /api/v1/profile/me/onboarding           (2.0)
POST /api/v1/profile/me/lesson/complete      (2.0)
```

### 误区诊断 (2.0)
```
POST /api/v1/misconceptions/diagnose
GET  /api/v1/misconceptions
```

### 教师 (2.0)
```
GET  /api/v1/teacher/overview
```

### 系统
```
GET  /api/v1/health
```

---

## 9. 前端组件树

```
layout.tsx                          # 根布局 (Header + Main + OnboardingWrapper)
│
├── nav-link.tsx                    # 导航链接 (AI对话/练习中心/学习画像/教学分析)
├── nav-admin-link.tsx              # 管理员入口
├── nav-user.tsx                    # 用户菜单 (登录/注册/登出)
│
├── onboarding-wrapper.tsx          # 引导总控 (学生专用)
│   ├── onboarding-modal.tsx        #   四入口选择弹窗
│   ├── diagnostic-flow.tsx         #   入口B: 6题诊断
│   └── lesson-player.tsx           #   入口A/B: 12课教程
│
├── page.tsx                        # AI 对话主页
│   └── chat-message.tsx            #   消息气泡 (含2.0徽章)
│       ├── hint_level badge
│       ├── misconception_id badge
│       ├── pedagogical_strategy badge
│       └── react-markdown + 代码高亮
│
├── exercises/page.tsx              # 练习中心
│   ├── 左侧题库 (对勾按ID匹配)
│   ├── 中间题目 + 提示区
│   │   ├── 🧠 误区诊断卡片
│   │   └── 💡 提示 (含strategy/misconception标签)
│   └── 右侧 Code Lab (Monaco + 运行 + 判题结果)
│
├── profile/page.tsx                # 学习画像
│   ├── 统计卡片 (exercises_passed)
│   ├── 最近常见误区
│   └── 提示依赖度
│
├── teacher/page.tsx                # 教师仪表盘
│   ├── 5 统计卡片
│   ├── 误区频次柱状图
│   ├── 薄弱知识点排行
│   ├── 提示依赖分布
│   ├── 学生列表
│   └── 最近动态
│
├── admin/page.tsx                  # 管理后台
├── login/page.tsx                  # 登录 (密码眼睛)
└── register/page.tsx               # 注册 (密码眼睛)
```

---

## 10. 关键设计决策

### 10.1 为什么用 DashScope API 替代本地 SentenceTransformer

- HuggingFace 在中国不可达，模型下载阻塞 485s
- DashScope API 国内可达，零维护
- 1024 维 vs 384 维，精度更高
- 降级链路: API → TF-IDF → 无 RAG

### 10.2 为什么按 exercise_id 去重而非按 concept

- 概念标签是分类属性，不具备唯一性
- 同一概念下多道题，通过一道不应全打勾
- `already_passed` 按概念检查导致 `exercise_passed` 事件永远不触发

### 10.3 为什么 `record_event()` 统一管理计数器

- 之前 exercises.py 和 record_event() 双重累加
- 单一权威来源（Single Source of Truth）
- 防止 failed 分支 `+= 1` 重复行 bug

### 10.4 为什么 LessonPlayer 用 Portal 渲染

- z-index 与 layout header 冲突
- `createPortal(content, document.body)` 直接渲染到 body，z-index 9999
- textarea 替代 Monaco 编辑器，避免加载延迟

### 10.5 为什么教程进度用 localStorage + user.id

- 不需要后端 API，离线可用
- `pytutor_progress_{userId}` 按用户隔离
- token 前 16 位不可靠（切换账号时残留）

### 10.6 四入口的差异化路由

- A: 完整教程 (Lesson 0A)
- B: 诊断 → 基础好→练习中心 / 基础弱→Lesson 1
- C: 直接 → /exercises
- D: 留在 AI 对话

---

> **最后更新**: 2026-06-12 | **版本**: 2.0 | **总提交**: 40+ | **Bug**: 29 | **Step**: 36
