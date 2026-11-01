# AI Python Tutor（PyTutor）

> 基于 Agentic RAG、AST 误区诊断与安全代码执行沙箱的 Python 编程智能导师平台

## 项目简介

PyTutor 面向 Python 零基础/初学者，能：

- 通过自然语言对话讲解概念，回答基于知识库检索（RAG）
- 在统一沙箱边界内运行学生代码并返回结果
- 用 AST 结构分析 + 规则诊断 8 类典型初学者误区（M1–M8）
- 按教学策略与渐进提示等级给提示，不直接甩答案
- 维护学习画像（薄弱点、误区历史、提示依赖）并推荐下一步
- 为教师提供班级误区排行、薄弱点排行与提示依赖分布

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js 16 + React 19 + TypeScript + Zustand + Monaco 编辑器 |
| 后端 | FastAPI + Python 3.12 + SQLAlchemy 2.0（async） |
| AI | DeepSeek（LiteLLM/OpenAI 兼容）+ DashScope `text-embedding-v3` |
| 检索 | ChromaDB 向量检索 + TF-IDF 关键词检索，可降级 |
| 数据库 | SQLite（开发）/ PostgreSQL（生产）；Alembic 迁移 |
| 部署 | 本地/Docker Compose（完整判题）；Render + Vercel 仅聊天/RAG（见 [DEPLOYMENT.md](docs/DEPLOYMENT.md)） |

### 关于 Ast 与诊断

诊断链路：正则规则 → AST 结构分析（`ENABLE_AST_DIAGNOSIS`）→ AST 置信度融合。
AST 分析器在 `backend/app/analysis/`，只做代码结构事实（赋值/比较混淆、缩进、返回值误用等），
不执行学生代码；执行仍走沙箱。

## 快速开始

### 环境要求

- Python 3.11+
- Node 20+
- Docker —— **生产环境运行学生代码必需**；没有 Docker 时代码执行会被拒绝，练习显示“未判定”

### 一键安装

```bash
./setup.sh        # macOS / Linux
setup.bat         # Windows
```

手动安装等价于：

```bash
cd backend && python -m venv .venv && .venv/bin/pip install -e .   # Windows: .venv\Scripts\pip
cd ../frontend && npm install
```

> 仓库根目录的 `package.json` 不再声明依赖，只把命令转发到 `frontend/`。
> 前端依赖唯一来源是 `frontend/package.json`。

### 配置

```bash
cd backend
cp .env.example .env
# 必填：DEEPSEEK_API_KEY
# RAG 语义检索：DASHSCOPE_API_KEY（缺失自动降级到 TF-IDF，不影响对话）
```

功能开关（默认全关，`.env` 可开）：`ENABLE_AST_DIAGNOSIS`、`ENABLE_PEDAGOGY_STEERING`、
`ENABLE_MULTI_JUDGE`、`ENABLE_TIME_DECAY`、`ENABLE_CONTENT_RECOMMEND`、
`ENABLE_MULTI_MODEL_ROUTING`、`ENABLE_RAG_RERANK`、`ENABLE_HYBRID_WEIGHTS`、
`ENABLE_TOKEN_CHUNKING`、`ENABLE_CONTEXT_COMPRESSION`。
完整含义与验证方式见 [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md)。

### 启动

```bash
# 数据库迁移（首次或升级时）
cd backend && alembic upgrade head

# 终端 1：后端
cd backend && uvicorn app.main:app --reload

# 终端 2：前端
cd frontend && npm run dev
```

打开 http://localhost:3000 ，API 文档在 http://localhost:8000/docs 。

**数据库位置**：`DATABASE_URL` 是相对路径，基准是进程工作目录。
`cd backend` 启动 → `backend/ai_tutor.db`；在仓库根启动会得到另一份空库。
空库首次启动会自动建表、写入 M1–M8 定义并导入知识库，无需额外脚本。
详见 [docs/REPRODUCIBILITY.md §4](docs/REPRODUCIBILITY.md)。

## 测试

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/ -q      # Windows
.venv/bin/python -m pytest tests/ -q             # macOS/Linux
```

默认只跑离线用例（`integration`、`llm` 标记的用例需外部服务/付费 key，默认排除）。
当前：**251 passed, 12 deselected**（覆盖率 47%）。

前端构建：

```bash
cd frontend && npm run build
```

评测脚本（在 `backend/` 下运行）：

```bash
cd backend
python ../evaluation/run_v2_eval.py --mode ast-only      # 误区诊断，离线
python ../evaluation/run_rag_eval.py --mode tfidf        # RAG 检索，离线
python ../evaluation/run_judge_eval.py                   # Multi-Judge，需 key
```

结果口径、数据集哈希与"已实现/已启用/已验证"对照表见
[docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md)。

## 项目结构

```
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── api/              # 路由（v1）
│   │   ├── analysis/         # AST 结构分析 + 置信度
│   │   ├── agents/           # LangGraph 工作流
│   │   ├── rag/              # 检索、切分、embedding、知识库种子
│   │   ├── sandbox/          # 统一执行边界（runner / docker_executor）
│   │   ├── services/         # 聊天、判题、画像、误区、教学策略、裁判
│   │   ├── models/           # SQLAlchemy 模型
│   │   ├── schemas/          # Pydantic schema
│   │   └── security/         # JWT、角色依赖
│   ├── alembic/              # 数据库迁移
│   └── tests/                # 离线单测 + 集成测试（默认排除）
├── frontend/                 # Next.js 前端
├── evaluation/               # 评测脚本与结果
├── research/faithfulness/    # 忠实度实验（核验器、数据集、runner）
├── docs/                     # 架构、可复现性、变更记录
├── docker-compose.yml
└── Makefile
```

## 文档

- [docs/REPRODUCIBILITY.md](docs/REPRODUCIBILITY.md) —— 基线、开关、数据库、评测口径
- [docs/TASK-STATUS.md](docs/TASK-STATUS.md) —— 17 项完善任务的真实状态
- [docs/DEMO.md](docs/DEMO.md) —— 可复现演示脚本（含失败分支）
- [docs/DATA_CARD.md](docs/DATA_CARD.md) —— 数据集来源、规模、已知问题
- [docs/figures/](docs/figures/) —— 结果图（SVG，浅色/深色）与表格视图
- [docs/CLAIMS-EVIDENCE.md](docs/CLAIMS-EVIDENCE.md) —— 每条创新主张对应的实现、界面与证据
- [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) —— 部署边界（哪些环境能判题）与限流
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) —— 系统架构
- [docs/tech-explanation.md](docs/tech-explanation.md) —— 技术栈逐项解释
- [docs/CHANGELOG.md](docs/CHANGELOG.md) —— 变更与问题记录

## 状态说明

已实现 ≠ 已验证。误区诊断、RAG、Multi-Judge 目前有离线结果，但样本量小或与规则同集；
学习增益、教师盲评、概率校准需要真实参与者与人工标注，尚未完成。具体边界见
[docs/REPRODUCIBILITY.md §7](docs/REPRODUCIBILITY.md)。
