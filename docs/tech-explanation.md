# MVP 后端技术栈详解

> 本文档面向技术栈不熟悉的开发者，用通俗语言解释每个技术的"是什么、为什么、怎么用"。

---

## 目录

1. [Python 项目基础](#1-python-项目基础)
2. [FastAPI —— Web 框架](#2-fastapi--web-框架)
3. [Pydantic —— 数据校验](#3-pydantic--数据校验)
4. [SQLAlchemy —— 数据库 ORM](#4-sqlalchemy--数据库-orm)
5. [Alembic —— 数据库迁移](#5-alembic--数据库迁移)
6. [JWT —— 身份认证](#6-jwt--身份认证)
7. [bcrypt —— 密码安全](#7-bcrypt--密码安全)
8. [structlog —— 结构化日志](#8-structlog--结构化日志)
9. [OpenAI SDK —— LLM 调用](#9-openai-sdk--llm-调用)
10. [Docker —— 容器化](#10-docker--容器化)

---

## 1. Python 项目基础

### 1.1 pyproject.toml 是什么？

`pyproject.toml` 是 Python 项目的"身份证"——它告诉其他人（和工具）：
- 这个项目叫什么名字
- 需要 Python 什么版本
- 依赖哪些第三方包
- 用什么工具来格式化、测试、构建

**类比**：就像前端的 `package.json`，或者 Java 的 `pom.xml`。

```toml
[project]
name = "ai-python-tutor"          # 项目名
requires-python = ">=3.11"        # 最低 Python 版本
dependencies = [
    "fastapi>=0.115.0",           # 依赖包及最低版本
    "uvicorn[standard]>=0.32.0",
]
```

### 1.2 虚拟环境（venv）是什么？

Python 在**全局**安装包时，所有项目共享同一套包。这会导致：
- 项目 A 需要 `fastapi==0.100`，项目 B 需要 `fastapi==0.115` → 冲突！
- 不知道当前项目到底用了哪些包

**虚拟环境**给每个项目一个独立的 Python 环境：
```
d:\FYP_python\backend\.venv\     # 这个项目的"私人 Python"
├── Lib\site-packages\           # 只属于这个项目的包
├── Scripts\python.exe           # 这个项目专用的 Python 解释器
└── Scripts\activate             # 激活脚本
```

```bash
# 创建虚拟环境
python -m venv .venv

# 激活（Windows Git Bash）
source .venv/Scripts/activate

# 激活后，pip install 只会安装到 .venv 中
pip install fastapi
```

### 1.3 .env 文件与配置管理

**问题**：数据库密码、API Key 这些东西不能写在代码里（会被 Git 记录、泄露）。

**解决**：把配置放在 `.env` 文件中，代码运行时读取。

```bash
# .env 文件（不提交到 Git）
DEEPSEEK_API_KEY=sk-abc123
DATABASE_URL=postgresql://...
SECRET_KEY=my-secret-key
```

`pydantic-settings` 库自动把 `.env` 中的配置映射为 Python 对象：

```python
# config.py
class Settings(BaseSettings):
    deepseek_api_key: str   # 自动匹配 .env 中的 DEEPSEEK_API_KEY
    database_url: str       # 自动匹配 .env 中的 DATABASE_URL

settings = Settings()
print(settings.deepseek_api_key)  # "sk-abc123"
```

**优先级**：环境变量 > .env 文件 > 代码默认值。生产环境（Kubernetes）用环境变量注入配置，开发和测试用 .env 文件。

---

## 2. FastAPI —— Web 框架

### 2.1 什么是 Web 框架？

浏览器（或前端）向后端发 HTTP 请求（如 `GET /api/v1/users/me`），后端需要：
1. 解析这个请求（提取 Header、Body）
2. 根据 URL 路径找到对应的处理函数
3. 调用处理函数
4. 把返回值转成 JSON 返回给前端

**Web 框架**就是帮你做第 1、2、4 步的工具——你只需写第 3 步的业务逻辑。

### 2.2 为什么选 FastAPI？

| 特性 | FastAPI | Flask | Django |
|------|---------|-------|--------|
| 异步支持 | ✅ 原生 | ❌ 需要插件 | ⚠️ 部分支持 |
| 自动 API 文档 | ✅ Swagger UI | ❌ 需要插件 | ⚠️ 需要插件 |
| 数据校验 | ✅ Pydantic 内置 | ❌ 手动 | ⚠️ DRF Serializer |
| 性能 | ⭐⭐⭐ 最快 | ⭐⭐ 中等 | ⭐ 较慢 |
| 学习曲线 | 中等 | 简单 | 陡峭 |

**异步**是关键：FastAPI 可以在等待数据库返回时处理其他请求，不浪费时间。

### 2.3 核心概念

**路由（Route）**：URL 路径 → 函数的映射。

```python
@app.get("/api/v1/users/me")        # 当 GET /api/v1/users/me 被请求时
async def get_me():                  # 执行这个函数
    return {"name": "小明"}
```

**依赖注入（Depends）**：FastAPI 自动为你的函数提供参数。

```python
# get_db 返回一个数据库会话
# FastAPI 自动调用 get_db()，把结果传给 db
@router.get("/users")
async def list_users(db: AsyncSession = Depends(get_db)):
    return await db.execute(select(User))
```

**中间件（Middleware）**：请求到达处理函数之前和之后执行的代码。

```
请求 → [CORS中间件] → [日志中间件] → [处理函数] → [日志中间件] → [CORS中间件] → 响应
```

### 2.4 uvicorn 是什么？

FastAPI 本身不处理网络连接——它只定义了"收到什么请求时调用什么函数"。
**uvicorn** 是实际监听 8000 端口、接收 HTTP 请求、发给 FastAPI 的服务器。

**类比**：FastAPI 是餐厅的厨师（做菜），uvicorn 是服务员（接单、上菜）。

---

## 3. Pydantic —— 数据校验

### 3.1 为什么需要数据校验？

用户发来的数据不可信！前端可能被绕过（用 curl 直接调 API），所以后端**必须**自己校验。

```python
# 不安全的写法
@app.post("/register")
async def register(email: str, password: str):  # email 可能是 "not-an-email"！
    ...

# 安全的写法
class RegisterRequest(BaseModel):
    email: EmailStr      # Pydantic 自动校验邮箱格式
    password: str = Field(min_length=8, max_length=72)

@app.post("/register")
async def register(request: RegisterRequest):  # 校验失败自动返回 422
    ...
```

### 3.2 Pydantic 做了什么

1. **类型校验**：`email: EmailStr` → 自动检查是不是有效邮箱
2. **长度校验**：`min_length=8` → 太短自动拒绝
3. **范围校验**：`ge=0, le=2` → temperature 必须在 0~2 之间
4. **自动文档**：Schema 会出现在 Swagger UI 中
5. **序列化**：把 Python 对象转为 JSON 字符串

### 3.3 Schema vs Model

| | Pydantic Schema | SQLAlchemy Model |
|---|---|---|
| 作用 | 定义 API 的输入/输出格式 | 定义数据库表结构 |
| 在哪用 | 请求校验、响应序列化 | 数据库查询、存储 |
| 例子 | `RegisterRequest` | `User` |
| 包含密码？ | 不暴露 | 存储 password_hash |

**为什么要分开？** 数据库结构变化（比如加了一个字段）不应该直接影响 API 返回给前端的数据。Schema 是一层"安全过滤"。

---

## 4. SQLAlchemy —— 数据库 ORM

### 4.1 ORM 是什么？

**ORM = Object-Relational Mapping（对象关系映射）**

不用 ORM（手写 SQL）：
```python
# 字符串拼接 SQL，容易出错，不安全
db.execute(f"SELECT * FROM users WHERE email = '{email}'")  # SQL 注入风险！
```

用 ORM：
```python
# Python 代码，安全，有 IDE 自动补全
user = await db.execute(select(User).where(User.email == email))
```

ORM 把数据库的**行**映射为 Python 的**对象**：
```
数据库表 users               Python 对象
┌──────────────────┐        User
│ id  │ email      │        ├── id = "abc-123"
├─────┼────────────┤  ──→   ├── email = "test@example.com"
│ abc │ test@...   │        └── display_name = "小明"
└─────┴────────────┘
```

### 4.2 同步 vs 异步

```
同步（阻塞）：
  请求1: [查询数据库...............等结果.........返回]
  请求2:                                       [查询....返回]
  请求3:                                              [查询..]
  → 同一时间只能处理一个请求

异步（非阻塞）：
  请求1: [查询]..等结果中..[返回]
  请求2:   [查询]..等结果中..[返回]
  请求3:     [查询]..等结果中..[返回]
  → 三个请求几乎同时处理
```

异步的关键：等待数据库返回的 CPU 空闲时间，用来处理其他请求。

### 4.3 会话（Session）管理

```python
async def get_db():
    async with AsyncSessionFactory() as session:
        yield session           # 交给业务代码使用
        await session.commit()  # 业务成功 → 提交
        # 如果抛异常 → 自动回滚（rollback）
```

每个 HTTP 请求创建一个独立的 Session，请求结束自动关闭。这保证了：
- 不同用户之间数据隔离
- 请求出错时数据不会半途写入

---

## 5. Alembic —— 数据库迁移

### 5.1 问题场景

你定义了 `User` 模型，创建了 `users` 表。几周后需要加一个 `bio` 字段：

```python
# 旧版本
class User(Base):
    email: Mapped[str]
    display_name: Mapped[str]

# 新版本
class User(Base):
    email: Mapped[str]
    display_name: Mapped[str]
    bio: Mapped[str]            # 新增字段！
```

怎么让数据库也加上这个字段？
- ❌ 手动写 `ALTER TABLE users ADD COLUMN bio TEXT`（容易忘，不同环境要分别执行）
- ✅ 用 Alembic 自动生成迁移脚本

### 5.2 Alembic 工作流

```bash
# 1. 修改模型（在代码中加字段）
# 2. 自动生成迁移脚本
alembic revision --autogenerate -m "add_bio_to_users"
#   → 生成 alembic/versions/xxx_add_bio_to_users.py

# 3. 执行迁移
alembic upgrade head
#   → ALTER TABLE users ADD COLUMN bio TEXT

# 4. 如果出问题，回滚
alembic downgrade -1
#   → ALTER TABLE users DROP COLUMN bio
```

**类比**：Alembic 是数据库的 Git——每次变更都有记录，可以前进（upgrade）和回退（downgrade）。

---

## 6. JWT —— 身份认证

### 6.1 HTTP 是无状态的

HTTP 协议本身不记得"上一个请求是谁发的"。每次请求都是独立的。

```
客户端: GET /api/v1/users/me
服务器: 你是谁？我不知道。
```

### 6.2 JWT 如何解决

**JWT = JSON Web Token**

```
登录流程：
1. 用户发送邮箱+密码
2. 服务器验证正确 → 用密钥签发 JWT → 返回给客户端
3. 客户端存储 JWT
4. 后续每次请求都带上 JWT（放在 Authorization 头中）
5. 服务器验证 JWT 签名 → 确认身份 → 返回数据
```

### 6.3 JWT 的三段式结构

```
eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMTIzIn0.4LqXo8...

┌──────────────────┬─────────────────────┬──────────────────┐
│     Header       │       Payload       │    Signature     │
│  {"alg":"HS256"} │  {"sub":"user123"}  │  HMAC-SHA256(    │
│                  │  {"exp":1234567890} │    Header+Payload │
│                  │                     │    + secret_key)  │
└──────────────────┴─────────────────────┴──────────────────┘
     Base64 编码        Base64 编码          加密签名
```

**为什么可以信任 JWT？**
- Payload 里写着 `"sub": "user123"`（用户 ID）
- 攻击者可以把 `user123` 改成 `admin001`
- 但签名是用 secret_key 计算的——改 Payload 后签名不匹配
- 服务器验证时发现签名不对 → 拒绝请求
- 攻击者不知道 secret_key，无法重新生成有效签名

### 6.4 Access Token vs Refresh Token

| | Access Token | Refresh Token |
|---|---|---|
| 有效期 | 短（24 小时） | 长（7-30 天） |
| 用途 | 每次请求都带 | 只在过期时用 |
| 暴露风险 | 高（频繁传输） | 低（很少发送） |

本项目 MVP 阶段只实现了 Access Token，Refresh Token 是后续增强。

---

## 7. bcrypt —— 密码安全

### 7.1 为什么不能存明文密码？

```
数据库泄露前：用户密码 "mypassword123"
数据库泄露后：
├── 明文存储：攻击者直接看到 "mypassword123" → 登录该用户所有账户
├── MD5 哈希：攻击者查 rainbow table → 秒破
└── bcrypt：攻击者需要逐条暴力破解 → 每条密码数百年
```

### 7.2 bcrypt 的四个安全特性

**1. 自动加盐（Salt）**

```python
# 同一个密码，每次哈希结果不同！
hash_password("mypass")  # → $2b$12$LJ3m4y...（盐=LJ3m4y）
hash_password("mypass")  # → $2b$12$XK9f2z...（盐=XK9f2z）完全不同的结果！
```

每个密码都有自己随机生成的盐，所以两个用户用相同密码，哈希值也不同。

**2. 计算成本可调节**

```
rounds=12 表示 2^12 = 4096 次迭代
每增加 1 轮，计算时间翻倍
12 轮 ≈ 0.3 秒（对登录无感）
16 轮 ≈ 5 秒（暴力破解变慢 16 倍）
```

**3. 抗 GPU 加速**

bcrypt 需要大量内存访问，GPU 的并行计算优势无法发挥。

**4. 72 字节限制**

bcrypt 最多处理 72 字节的密码。如果密码超过 72 字节（罕见，除非用长中文密码），先做 SHA256 压缩：

```python
if len(password_bytes) > 72:
    password_bytes = hashlib.sha256(password_bytes).digest()
```

---

## 8. structlog —— 结构化日志

### 8.1 print 为什么不够？

```python
# print 方式
print(f"用户 {user_id} 登录成功")  # 没有时间戳、没有级别、无法搜索

# structlog 方式
logger.info("user_logged_in", user_id="abc-123", email="test@example.com")
# 输出: [2026-06-08 10:00:00] INFO  user_logged_in  user_id=abc-123  email=test@example.com
```

### 8.2 结构化日志的好处

**可搜索**：在日志系统中搜索 `user_id=abc-123` 就能看到该用户的所有操作。

**可聚合**：统计 `event=login_failed` 的数量就能得知有多少次登录失败。

**可追踪**：每个请求有唯一的 `request_id`，前端报错时附带 ID，后端搜索该 ID 就能看到完整请求链路。

### 8.3 生产环境

开发时输出彩色可读格式：
```
[2026-06-08 10:00:00] INFO    user_logged_in    user_id=123
```

生产时输出 JSON（机器可解析）：
```json
{"timestamp": "2026-06-08T10:00:00Z", "level": "info", "event": "user_logged_in", "user_id": "123"}
```

这些 JSON 日志可以被 ELK、Loki 等日志收集系统自动索引和分析。

---

## 9. OpenAI SDK —— LLM 调用

### 9.1 为什么用 OpenAI SDK 调 DeepSeek？

DeepSeek 的 API 与 OpenAI 完全兼容——URL 结构、请求格式、响应格式都一样。

```python
from openai import AsyncOpenAI

# 指向 DeepSeek 的地址
client = AsyncOpenAI(
    api_key="sk-deepseek-key",
    base_url="https://api.deepseek.com",  # 把 openai.com 换成 deepseek.com
)

# 调用方式完全一样
response = await client.chat.completions.create(
    model="deepseek-chat",
    messages=[{"role": "user", "content": "什么是 Python？"}],
)
```

好处：未来切换到 OpenAI、Azure OpenAI 或任何兼容接口，只需改 `base_url`。

### 9.2 关键参数

| 参数 | 作用 | 推荐值 |
|------|------|--------|
| `temperature` | 0=保守（代码）, 2=创造性（写作） | 0.7 |
| `max_tokens` | 限制输出长度 | 4096 |
| `top_p` | 词汇选择范围 | 1.0 |
| `model` | 模型名称 | deepseek-chat |

### 9.3 Token 是什么？

LLM 不是按"字"计费，而是按 **token** 计费：
- 1 个中文字 ≈ 1-2 token
- 1 个英文单词 ≈ 1-3 token
- "Hello世界" ≈ 3 token

```
输入："什么是 Python？" → 5 token
输出："Python 是一门编程语言..." → 50 token
总计：55 token × 单价 = 本次费用
```

每次调用记录输入/输出 token 数，方便算成本和优化 Prompt。

### 9.4 Fallback 模型

```
主模型 deepseek-chat 调用失败
    → 尝试备用模型（如果配置了）
    → 备用也失败 → 返回 "AI 服务暂时不可用"
```

这提高了系统可用性。生产环境通常配置不同供应商的模型互为备份。

---

## 10. Docker —— 容器化

### 10.1 问题场景

```
你的电脑：Python 3.12, Windows, 能运行
同学电脑：Python 3.10, macOS, 报错
服务器：  Python 3.11, Linux, 报错
```

"在我电脑上能跑"是开发者的噩梦。

### 10.2 Docker 做了什么

Docker 把应用和它的所有依赖打包成一个**镜像**（Image），镜像在任何安装了 Docker 的机器上都能以**容器**（Container）的形式运行。

```
传统部署：
  应用代码 → 需要在目标服务器上安装 Python + 依赖 + 配置

Docker 部署：
  应用代码 + Python + 依赖 + 配置 → 打包为镜像 → 任何地方运行
```

### 10.3 镜像 vs 容器

| | 镜像（Image） | 容器（Container） |
|---|---|---|
| 是什么 | 只读的模板 | 运行中的实例 |
| 类比 | 程序的安装包 `.exe` | 正在运行的程序 |
| 状态 | 静态文件 | 动态进程 |

### 10.4 多阶段构建

```dockerfile
# 阶段 1：构建（包含编译器、git 等工具）
FROM python:3.12-slim AS builder
RUN pip install ...            # 编译安装包

# 阶段 2：运行（只复制构建结果，不含编译工具）
FROM python:3.12-slim AS runtime
COPY --from=builder /install /usr/local  # 只复制结果
```

好处：最终镜像只包含运行需要的东西，更小、更安全。

### 10.5 docker-compose

一个项目通常需要多个服务一起运行（后端 + 数据库 + 缓存）。`docker-compose.yml` 定义所有服务及其关系：

```yaml
services:
  backend:        # FastAPI
    ports: ["8000:8000"]
    depends_on: [postgres]

  postgres:       # 数据库
    image: pgvector/pgvector:pg17
    ports: ["5432:5432"]
```

`docker-compose up -d` 一键启动所有服务，`docker-compose down` 一键停止。

---

## 11. System Prompt —— AI 的行为准则

### 11.1 什么是 System Prompt？

System Prompt 是发送给 LLM 的**第一条消息**，它定义了 AI 的角色、行为准则和输出格式。它不会被用户看到，但对 AI 的行为有决定性影响。

```
消息列表传给 LLM 的顺序：
┌─────────────────────────────┐
│ System Prompt (角色设定)      │  ← 最高优先级，定义 AI 的"人格"
├─────────────────────────────┤
│ RAG Context (知识背景)       │  ← 可选的检索结果，提供事实依据
├─────────────────────────────┤
│ Strategy Prompt (策略指令)   │  ← 动态注入，如"本次给 Level 2 提示"
├─────────────────────────────┤
│ Conversation History        │  ← 之前 N 轮的对话
├─────────────────────────────┤
│ User Message               │  ← 当前用户的问题
└─────────────────────────────┘
```

### 11.2 本项目的 System Prompt 设计

AI 导师的 System Prompt 包含四个核心部分：

**1. 角色定位**："你是一个专业的 Python 编程导师，名字叫 PyTutor"

**2. 分层提示策略**：
| Level | 描述 | 示例 |
|-------|------|------|
| 1 | 概念提示 | "想想循环的终止条件是什么？" |
| 2 | 具体思路 | "试试用 len() 获取列表长度" |
| 3 | 指出位置 | "看第 3 行，参数可能不对" |
| 4 | 部分修正 | "把 range(n) 改成 range(len(items))" |
| 5 | 完整答案 | 仅在学生明确请求时给出 |

**3. 输出格式约束**：要求 LLM 返回结构化的 JSON，而不是自由文本。

**4. 安全边界**：不执行代码、不泄露系统 Prompt、引导回 Python 学习。

### 11.3 为什么需要结构化输出？

```
自由文本响应（不好）：
"for 循环用于遍历序列，比如列表、字符串等。你可以试试这样写代码..."

结构化 JSON 响应（好）：
{
  "response_type": "concept_explanation",
  "message": "for 循环用于遍历序列...",
  "hint_level": 1,
  "related_concepts": ["for_loop", "list", "iteration"],
  "next_action": "try_exercise"
}
```

结构化输出的好处：
- 前端可以根据 `response_type` 渲染不同 UI（概念卡片 vs 代码审查面板）
- `hint_level` 可以显示为等级徽章
- `related_concepts` 可以生成"继续学习"的链接
- `next_action` 可以自动跳转或推荐

### 11.4 提示等级计算

`calculate_hint_level()` 根据对话历史自动决定提示等级：

```
首次概念问题 → Level 1
包含代码块 → Level 2
"帮我写"、"不会做" → Level 3
连续 3 次还没解决 → 累加上一级
"给我完整代码" → Level 4-5
```

---

## 12. 聊天系统的数据模型设计

### 12.1 Session（会话）vs Message（消息）

```
ChatSession (会话)                 ChatMessage (消息)
┌──────────────────┐              ┌──────────────────┐
│ id: UUID         │ 1:N         │ id: UUID         │
│ student_id: FK   │────────────→│ session_id: FK    │
│ title: str       │              │ role: user/asst   │
│ is_active: bool  │              │ content: text     │
│ created_at       │              │ hint_level: 1-5   │
│ updated_at       │              │ response_type     │
└──────────────────┘              │ created_at        │
                                  └──────────────────┘
```

### 12.2 为什么把 AI 回复存为 JSON？

AI 返回的结构化 JSON 被整体存入 `content` 字段（`Text` 类型），同时把关键字段（`response_type`、`hint_level`、`related_concepts`）提取到数据库列中，方便 SQL 查询和索引。

```
content (TEXT):
{"response_type": "concept_explanation", "message": "...", "hint_level": 1, ...}
    ↓ 提取 →  response_type VARCHAR(50) → 可以 WHERE response_type = 'code_feedback'
    ↓ 提取 →  hint_level INTEGER → 可以统计平均提示等级
    ↓ 提取 →  related_concepts VARCHAR(500) → 可以 WHERE related_concepts LIKE '%for_loop%'
```

### 12.3 依赖注入链

一个典型的聊天请求经过的依赖链：

```
HTTP Request
  → RequestLoggingMiddleware (记录 request_id)
  → CORS Middleware
  → get_current_user (JWT 验证 → 数据库查 User)
  → get_db (创建数据库 Session)
  → chat_service.send_message()
      → 保存用户消息
      → tutor_service.generate_tutor_response()
          → calculate_hint_level()
          → llm_service.chat_completion() → DeepSeek API
          → _parse_ai_json()
      → 保存 AI 回复
      → 返回结构化响应
  → RequestLoggingMiddleware (记录 duration_ms)
```


---

## 13. LangGraph —— Agent 工作流编排

### 13.1 为什么需要 Agent 工作流？
简单的单次 LLM 调用：「用户输入 → LLM → 回复」。问题是没有安全检查、知识检索、代码执行或输出校验。
Agent 工作流 = 多个处理步骤的流水线，每一步专注做一件事。

### 13.2 核心概念
- State（状态）：所有节点共享的数据字典
- Node（节点）：处理函数，接收 State 返回部分更新
- Edge（边）：普通边(A→B)或条件边(根据 State 值路由)

### 13.3 本项目工作流
[用户输入]→[安全检查]→[意图识别]→[RAG检索]→[代码执行]→[教学回复]→[输出校验]→END

### 13.4 简单LLM vs Agent工作流
简单LLM: 无安全/检索/执行/校验, 延迟~2s
Agent: 6节点全流程, 延迟~8s

---

## 14. 安全代码执行

多层防御：
第一层-静态分析(禁止 import os, eval()等)
第二层-子进程隔离(独立进程)
第三层-时间限制(timeout=10s)
第四层-输出限制(100KB)
第五层-容器隔离(Docker模式)
