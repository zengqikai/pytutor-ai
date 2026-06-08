# AI Python Tutor

> 基于 Agentic RAG、安全代码执行与个性化学习画像的 Python 编程智能导师平台

## 项目简介

AI Python Tutor 是一个 AI 驱动的 Python 编程学习平台。它能够：
- 通过自然语言对话帮助学生理解 Python 概念
- 在安全沙箱中运行学生代码并返回结果
- 分析代码错误并提供分层提示（鼓励独立思考）
- 根据学生水平生成个性化练习
- 追踪学习进度并推荐学习路径

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Next.js + React + TypeScript（后续开发） |
| 后端 | FastAPI + Python 3.12+ |
| AI | LangGraph + DeepSeek + RAG（后续开发） |
| 数据库 | PostgreSQL + pgvector（生产）/ SQLite（开发） |
| 缓存 | Redis（可选） |
| 部署 | Docker + Kubernetes |

> 📖 **技术栈详解**：[docs/tech-explanation.md](docs/tech-explanation.md) —— 逐个解释每个技术是什么、为什么选它、怎么用，面向不熟悉技术栈的开发者。

## 快速开始

### 环境要求

- Python 3.11+
- （可选）Docker & Docker Compose

### 本地开发

```bash
# 1. 进入后端目录
cd backend

# 2. 创建虚拟环境
python -m venv .venv
source .venv/Scripts/activate  # Windows
# source .venv/bin/activate    # macOS/Linux

# 3. 安装依赖
pip install -e .

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 DeepSeek API Key 等信息

# 5. 运行数据库迁移
alembic upgrade head

# 6. 启动开发服务器
uvicorn app.main:app --reload

# 7. 访问 API 文档
# http://localhost:8000/docs
```

### Docker 部署

```bash
# 启动所有服务
docker-compose up -d

# 查看日志
docker-compose logs -f backend

# 停止服务
docker-compose down
```

## 项目结构

```
├── backend/              # FastAPI 后端
│   ├── app/
│   │   ├── api/          # API 路由
│   │   ├── core/         # 配置、异常
│   │   ├── agents/       # AI Agent（待开发）
│   │   ├── rag/          # RAG 检索（待开发）
│   │   ├── sandbox/      # 代码沙箱（待开发）
│   │   ├── services/     # 业务逻辑
│   │   ├── models/       # 数据库模型
│   │   ├── schemas/      # Pydantic Schema
│   │   ├── security/     # 认证授权
│   │   ├── observability/# 日志监控
│   │   └── database/     # 数据库连接
│   ├── tests/            # 测试
│   └── alembic/          # 数据库迁移
├── docker-compose.yml    # Docker 编排
├── Makefile              # 常用命令
└── README.md
```

## API 接口

启动后访问 http://localhost:8000/docs 查看完整 Swagger 文档。

主要接口：
- `POST /api/v1/auth/register` - 用户注册
- `POST /api/v1/auth/login` - 用户登录
- `GET /api/v1/users/me` - 获取当前用户信息
- `GET /api/v1/health` - 健康检查

## 开发进度

- [x] Step 1: 项目骨架搭建
- [x] Step 2: 日志系统搭建
- [x] Step 3: 数据库基础
- [x] Step 4: 用户认证系统
- [x] Step 5: AI 服务基础
- [x] Step 6: Docker 化
- [ ] Step 7+: LangGraph Agent、RAG、代码沙箱、前端...
