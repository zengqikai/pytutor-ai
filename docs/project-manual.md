# PyTutor 项目技术手册

> 每个模块的实现细节、技术选型理由、文件路径、待优化点

---

## 项目概览

```
PyTutor — AI 驱动的 Python 编程学习平台
60+ 文件 | 35+ API | 10 张数据库表 | 6 节点 Agent | 41 个 RAG Chunk

架构：
  frontend/ (Next.js 16 + React + TypeScript)
      ↓ HTTP/SSE
  backend/  (FastAPI + Python 3.12)
      ↓
  ├── LangGraph Agent (6 节点工作流)
  ├── RAG 引擎 (TF-IDF 内存检索)
  ├── 代码沙箱 (子进程隔离)
  └── PostgreSQL/SQLite + Redis 预留
```

---

## 一、后端模块详解

---

### 1. 配置管理

**文件**: `backend/app/core/config.py`  
**技术**: pydantic-settings  
**核心逻辑**: 从 `.env` 读取配置 → Pydantic 强类型对象

```python
class Settings(BaseSettings):
    deepseek_api_key: str       # ← 自动匹配 .env 中的 DEEPSEEK_API_KEY
    database_url: str = "sqlite+aiosqlite:///./ai_tutor.db"
    llm_temperature: float = 0.7
    # 共 20+ 配置项
```

**为什么用 pydantic-settings**？环境变量 > .env > 默认值三级优先级，Docker/K8s 部署时可用环境变量覆盖，开发时用 .env。

**待优化**: 配置热更新（当前需重启）；敏感字段加密存储。

---

### 2. 日志系统

**文件**: `backend/app/core/logging_config.py`, `backend/app/observability/`  
**技术**: structlog + 标准 logging  
**核心逻辑**: 开发环境彩色控制台输出，生产 JSON 格式

```python
# 每个请求自动记录：
# request_id=uuid  method=POST  path=/api/v1/chat  status=200  duration_ms=45.2
```

**Windows 编码修复**（`logging_config.py` 第 55 行）：
```python
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
```

**待优化**: 接入 OpenTelemetry 做全链路追踪；输出到 Loki/ELK。

---

### 3. 数据库层

**文件**: `backend/app/database/session.py`, `backend/app/database/base.py`  
**技术**: SQLAlchemy 2.0 异步 + Alembic 迁移  
**核心逻辑**: 开发用 SQLite（aiosqlite），生产用 PostgreSQL（asyncpg）

```python
# 会话管理——每个请求独立会话
async def get_db():
    async with AsyncSessionFactory() as session:
        yield session
        await session.commit()        # 正常 → 提交
        # 抛异常 → 自动 rollback
```

**Base 模型**（`base.py`）：UUID 主键 + `created_at` + `updated_at`（server_default）
**Alembic 迁移**: 7 次，每次 `revision --autogenerate` 自动检测模型变化

**为什么用 UUID 而不是自增 ID**？分布式不冲突、不暴露数据量、前端可预生成。

**待优化**: 读写分离；慢查询监控；连接池调优。

---

### 4. 用户认证（JWT + bcrypt + RBAC）

**文件**: `backend/app/security/`, `backend/app/services/auth_service.py`

**密码哈希**（`security/password.py`）:
```python
# 直接用 bcrypt（不用 passlib——社区不维护，与 bcrypt 5.x 不兼容）
def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = hashlib.sha256(password_bytes).digest()
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt()).decode()
```

**JWT**（`security/jwt.py`）:
```python
# HS256 签名，24h 过期
def create_access_token(user_id: str, role: str) -> str:
    payload = {"sub": user_id, "role": role, "exp": expire, "iat": now}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")
```

**权限控制**（`security/dependencies.py`）:
```python
# 闭包工厂——require_role(ADMIN) 返回只允许管理员的依赖
def require_role(*allowed_roles):
    async def role_checker(current_user = Depends(get_current_user)):
        if current_user.role not in allowed_roles:
            raise HTTPException(403)
        return current_user
    return role_checker
```

**注册流程**（`services/auth_service.py`）:
```
邮箱格式校验 → 密码强度检查 → 查重 → bcrypt 哈希 → 入库 → 创建画像 → 签发 JWT
```

**登录安全**: 失败统一提示"邮箱或密码错误"（防枚举攻击）

**待优化**: Refresh Token；OAuth2 第三方登录；登录限流（当前仅内存实现）；密码重置

---

### 5. LLM 服务层

**文件**: `backend/app/services/llm_service.py`  
**技术**: OpenAI SDK → DeepSeek（兼容接口）  
**核心逻辑**: 统一的 `chat_completion()` 封装 + Fallback

```python
client = AsyncOpenAI(
    api_key=settings.deepseek_api_key,
    base_url="https://api.deepseek.com",  # 指向 DeepSeek
)

async def chat_completion(messages, model=None, temperature=None, max_tokens=None):
    # 主模型调用
    return await _call_llm(model, messages, ...)
    # 失败 → 切 fallback_model（如果配置了）
    # 都失败 → 返回友好错误
```

**Token 监控**: 每次调用记录 `prompt_tokens` + `completion_tokens` + `duration_ms`

**为什么用 OpenAI SDK 调 DeepSeek**？DeepSeek 完全兼容 OpenAI 格式，未来换模型只需改 `base_url`。

**待优化**: Token 消耗统计面板；流式输出（SSE）；请求队列限流。

---

### 6. Prompt 引擎（三次迭代）

**文件**: `backend/app/services/tutor_service.py`

| 版本 | 方案 | 行数 | 结果 |
|------|------|------|------|
| V1 | JSON 输出 | 100 | DeepSeek 频繁解析失败 |
| V2 | Markdown + HTML 注释 | 50 | 稳定但冗长 |
| V3 | 极简纯文本 | 3 | ✅ 当前最优 |

**当前 System Prompt**（第 47-49 行）:
```python
SYSTEM_PROMPT = """你是 PyTutor，Python 编程导师。用中文回复，简洁明了。
规则：引导思考优先，不直接给答案。代码用 ```python 包裹。
首行标注 <!-- hint:N concepts:x,y -->（N=1~5）。"""
```

**分层提示计算**（`calculate_hint_level()` 第 111 行）:
```
概念问题 → Level 1 | 含代码 → Level 2 | "帮我写" → Level 3
连续 3+ 失败 → 累加 | "给我完整代码" → Level 4-5
```

**消息组装顺序**（第 219-230 行）: System → RAG → Strategy → History → User

**待优化**: Prompt 版本化管理（已有 PromptTemplate 模型但未实际集成）；A/B 测试框架

---

### 7. RAG 知识库

**文件**: `backend/app/rag/`（4 个核心文件）

#### 7.1 文档加载 → 切分 → 入库

**加载**: `rag/loader.py`——支持 Markdown/纯文本  
**切分**: `rag/splitter.py`——按 ##/### 标题层级 + 2000 字符限制  
**入库**: `services/rag_service.py` 的 `ingest_document()`

```
10 篇 Markdown → 41 个 chunk → 数据库 + 内存索引
```

#### 7.2 检索（自己实现的 TF-IDF）

**文件**: `rag/retriever.py`  
**核心**: `HybridRetriever` 类——内存索引 + TF-IDF 计算

```python
class HybridRetriever:
    def search(self, query, top_k=5, difficulty_filter=None, concept_filter=None):
        query_tokens = _tokenize(query)  # 中文 2-gram + 英文单词 + Python 标识符
        for chunk in self._chunks.values():
            score = _tfidf_score(...)      # TF-IDF 得分
            heading_bonus = ...            # 标题匹配加 0.2
        return sorted_candidates[:top_k]
```

**为什么自己实现 TF-IDF 而不是用向量数据库**？MVP 阶段不需要外部依赖，41 个 chunk 内存检索 < 2ms。后续可升级 pgvector。

#### 7.3 重排序（已砍掉）

**文件**: `rag/reranker.py`——LLM 打分的重排序  
**砍掉原因**: `services/rag_service.py` 第 76 行，LLM 重排 +1.6s，教学场景精度要求不高，直接 Top-K 截断。

#### 7.4 索引生命周期

**启动重建**: `backend/app/main.py` 第 72-78 行，lifespan 启动时 `rebuild_index()` 从数据库恢复 41 个 chunk  
**手动重建**: `POST /api/v1/rag/rebuild`（管理员接口）

**待优化**: pgvector 向量检索；HyDE 查询改写；检索结果缓存

---

### 8. Agent 工作流（LangGraph 6 节点）

**文件**: `backend/app/agents/`（9 个文件）

#### 8.1 工作流图

**文件**: `agents/graph.py`  
**编译**: `workflow.compile()` 在应用启动时执行一次（单例）

```
safety_check → intent_router → {
    concept → rag_retrieval → tutor_response
    code    → rag_retrieval → code_executor → tutor_response
    general → tutor_response
    unsafe  → reject_response
} → output_validator → END
```

#### 8.2 各节点职责

| 节点 | 文件 | 输入 | 输出 | 容错 |
|------|------|------|------|------|
| `safety_check` | `nodes/safety_check.py` | user_input | safety_result | block → 直接终止 |
| `intent_router` | `nodes/intent_router.py` | user_input | intent + code | LLM 失败 → 关键词兜底 |
| `rag_retrieval` | `nodes/rag_retrieval.py` | user_input + intent | rag_context | 检索失败 → None |
| `code_executor` | `nodes/code_executor.py` | code_to_execute | code_result | 超时/拦截 → 标记 |
| `tutor_response` | `nodes/tutor_node.py` | 所有前置数据 | tutor_response | JSON 失败 → 原始文本 |
| `output_validator` | `nodes/output_validator.py` | tutor_response | is_valid_output | 缺字段 → 自动修复 |

#### 8.3 共享状态

**文件**: `agents/state.py`
```python
class AgentState(TypedDict):
    messages: list[dict]           # add_messages reducer
    user_input: str
    intent: str
    rag_context: Optional[str]
    code_result: Optional[dict]
    tutor_response: Optional[dict]
    safety_result: str
    is_valid_output: bool
```

#### 8.4 入口

**API**: `api/v1/agent.py` → `services/agent_service.py` → `graph.ainvoke(state)`

**待优化**: 节点并行执行（RAG 和 Code 可并行）；Human-in-the-loop；Checkpoint 持久化

---

### 9. 代码沙箱

**文件**: `backend/app/sandbox/`（2 个文件）

#### 9.1 安全检测

**文件**: `sandbox/security.py`  
**核心逻辑**: 去掉注释和字符串 → 正则匹配危险模式

```python
def check_code_safety(code):
    cleaned = _remove_strings_and_comments(code)  # 防误杀
    for module in ["os", "subprocess", "socket"]:
        if re.search(rf"\bimport\s+{module}\b", cleaned):
            return False, f"禁止导入: {module}"
```

**黑名单**: os, subprocess, socket, shutil, requests, ctypes, pickle  
**白名单**: input(), open() 只读, 所有标准库

#### 9.2 执行引擎

**文件**: `sandbox/executor.py`  
**两个函数**:

| 函数 | 用途 | stdin |
|------|------|-------|
| `execute_python_code()` | 聊天编辑器 | 无 |
| `execute_python_code_with_input()` | ACM 判题 | 有 |

```python
# 子进程执行（UTF-8 安全）
process = await asyncio.create_subprocess_exec(
    sys.executable, "-X", "utf8", str(tmp_path),
    stdin=PIPE, stdout=PIPE, stderr=PIPE,
    env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
)
# 超时 10s → kill；输出限制 100KB；错误路径匿名化
```

**关键 Bug**: 两个函数之前 UTF-8 设置不一致，`execute_python_code` 缺 `-X utf8`，导致中文乱码排查了 10 轮。

**待优化**: Docker 容器隔离（已预留）；gVisor 增强隔离；多语言支持

---

### 10. 练习 + ACM 判题

**文件**: `backend/app/api/v1/exercises.py`, `services/exercise_service.py`

#### 10.1 AI 出题

**文件**: `services/exercise_service.py`  
**核心**: LLM 生成 JSON 题目 → 解析 → 创建 Exercise + TestCase

```json
[{"title": "正数求和", "description": "...", "reference_solution": "# ...",
  "test_cases": [{"input_data": "1 -2 3", "expected_output": "4", "is_hidden": true}]}]
```

#### 10.2 ACM 判题（每个用例独立执行）

```python
for tc in exercise.test_cases:
    result = await execute_python_code_with_input(
        user_code, stdin_input=tc.input_data  # stdin 传入测试数据
    )
    if result["stdout"].rstrip() == tc.expected_output.rstrip():
        passed += 1
```

**关键设计**:
- 每个用例独立执行（不是所有用例跑一次代码）
- `stdout.rstrip()` 精确匹配（ACM 标准）
- 空输入 → 传空行 `\n`（不是关闭 stdin）
- 隐藏用例只显示通过/失败，不暴露具体数据

#### 10.3 提示 + 参考答案

```python
# POST /exercises/{id}/hint → LLM 生成分层提示（1-2 级）
# GET  /exercises/{id}/solution → 返回 reference_solution
```

**待优化**: 题库导入导出；题目难度自动校准；通过率统计分析

---

### 11. 学习画像

**文件**: `backend/app/models/profile.py`, `services/profile_service.py`

**知识依赖关系**（`profile_service.py` 第 16-30 行）:
```python
CONCEPT_PREREQUISITES = {
    "variables": [],
    "data_types": ["variables"],
    "for_loop": ["list", "string"],
    "function": ["for_loop", "if_statement"],
    ...
}
```

**推荐逻辑**（`get_recommendation()` 第 170 行）:
1. 有薄弱点 → 推荐最严重的复习
2. 无薄弱点 → 推荐路径上下一个前置完成的
3. 全部完成 → 推荐综合项目

**薄弱点检测**: 同知识点连败 3 次 → 标记；通过 → 解除

**待优化**: 知识图谱可视化；学习曲线分析；协作过滤推荐

---

### 12. 管理员后台

**文件**: `backend/app/api/v1/admin.py`  
**功能**: 系统统计 / 用户管理 / 题库管理 / 日志查看

**待优化**: 图表可视化；操作审计；批量导入

---

## 二、前端模块详解

---

### 1. 项目配置

**技术**: Next.js 16 + TypeScript + Tailwind CSS + Zustand  
**路由**: App Router，7 个页面（`/`, `/login`, `/register`, `/exercises`, `/profile`, `/admin`）

### 2. API 客户端

**文件**: `frontend/src/lib/api.ts`  
**设计**: 统一 `request<T>()` 函数——自动附加 JWT、401 拦截跳转、错误处理

```typescript
async function request<T>(path: string, options = {}): Promise<T> {
    const token = getToken();
    headers["Authorization"] = `Bearer ${token}`;
    return fetch(`${API_BASE}${path}`, { ...options, headers }).then(r => r.json());
}
```

### 3. 全局样式

**文件**: `frontend/src/app/globals.css`  
**设计系统**: 深空黑 `#06060f` + 玻璃拟态 `.glass` + 霓虹 glow + 5 种动画

### 4. 聊天页（最复杂页面）

**文件**: `frontend/src/app/page.tsx`（~350 行）

**布局**: 三栏——会话列表 | 聊天区 | 代码编辑器（Monaco）  
**消息组件**: `frontend/src/components/chat-message.tsx`——Markdown 渲染 + 语法高亮代码块 + 提示等级标签  
**状态持久化**: Zustand persist（sessionStorage）  
**模型切换**: 输入区上方 CHAT/REASONING 按钮

### 5. 练习中心（ACM 模式）

**文件**: `frontend/src/app/exercises/page.tsx`（~280 行）  
**布局**: 三栏——题库 | 题目描述 + 帮助 | 代码编辑器 + 判题结果  
**状态持久化**: Zustand persist

### 6. 其他页面

| 页面 | 文件 | 核心功能 |
|------|------|---------|
| 登录 | `app/login/page.tsx` | 沉浸式科幻设计 + 产品价值展示 |
| 注册 | `app/register/page.tsx` | 同上，青色主题 |
| 学习画像 | `app/profile/page.tsx` | 统计卡片 + 推荐 + 薄弱点 |
| 管理后台 | `app/admin/page.tsx` | 概览/用户/题库/日志 |

---

## 三、数据库 Schema

| 表名 | 用途 | 关键字段 |
|------|------|---------|
| `users` | 用户 | email(unique), password_hash, role(enum), is_active |
| `chat_sessions` | 聊天会话 | student_id(FK), title, is_active |
| `chat_messages` | 聊天消息 | session_id(FK), role, content, hint_level |
| `rag_documents` | 知识文档 | title, content, difficulty, concepts |
| `rag_chunks` | 文档片段 | document_id(FK), content, heading, tokens |
| `exercises` | 练习题 | title, description, difficulty, reference_solution |
| `test_cases` | 测试用例 | exercise_id(FK), input_data, expected_output, is_hidden |
| `code_submissions` | 代码提交 | user_id(FK), code, status |
| `execution_results` | 执行结果 | submission_id(FK), stdout, stderr, runtime_ms |
| `student_profiles` | 学习画像 | user_id(unique), level, concept_mastery_json |
| `student_weaknesses` | 薄弱点 | user_id(FK), concept, fail_count, severity |
| `learning_events` | 学习事件 | user_id(FK), event_type, concept |
| `prompt_templates` | Prompt 模板 | name, version, content, is_active |

---

## 四、API 接口清单（35+）

| 模块 | 端点 | 方法 | 功能 |
|------|------|------|------|
| 认证 | `/auth/register` | POST | 注册 |
| | `/auth/login` | POST | 登录 |
| 用户 | `/users/me` | GET | 当前用户信息 |
| 聊天 | `/chat/sessions` | GET/POST | 会话列表/创建 |
| | `/chat/sessions/{id}` | GET/PATCH/DELETE | 会话详情/重命名/删除 |
| | `/chat/sessions/{id}/messages` | POST | 发送消息 |
| Agent | `/agent/chat` | POST | Agent 工作流聊天 |
| 代码 | `/code/submit` | POST | 提交执行代码 |
| | `/code/analyze` | POST | 独立错误分析 |
| RAG | `/rag/documents` | GET/POST | 文档列表/导入 |
| | `/rag/search` | POST | 知识检索 |
| | `/rag/rebuild` | POST | 重建索引 |
| 练习 | `/exercises` | GET | 练习列表 |
| | `/exercises/generate` | POST | AI 生成练习 |
| | `/exercises/{id}` | GET | 练习详情 |
| | `/exercises/{id}/submit` | POST | 提交判题 |
| | `/exercises/{id}/hint` | POST | 获取提示 |
| | `/exercises/{id}/solution` | GET | 参考答案 |
| 画像 | `/profile/me` | GET | 学习画像 |
| | `/profile/me/weaknesses` | GET | 薄弱点 |
| | `/profile/me/recommendations` | GET | 学习推荐 |
| 管理 | `/admin/stats` | GET | 系统统计 |
| | `/admin/users` | GET/PATCH | 用户管理 |
| | `/admin/exercises` | GET/PATCH | 题库管理 |
| 系统 | `/health` | GET | 健康检查 |

---

## 五、关键设计决策

| 决策点 | 选项 | 选择 | 原因 |
|--------|------|------|------|
| Agent 框架 | LangChain vs LangGraph | LangGraph | 条件路由 + 可视化 |
| 检索方案 | pgvector vs 内存 TF-IDF | TF-IDF | MVP 简单，41 chunk 够用 |
| 重排序 | LLM vs 取消 | 取消 | 省 1.6s，教学场景够用 |
| JSON 输出 | 强制 vs 纯文本 | 纯文本 | DeepSeek 不稳定 |
| 前端状态 | useState vs Zustand persist | Zustand persist | 跨页面保持 |
| 数据库 | SQLite vs PostgreSQL | SQLite(dev) | 开发简单，预留 PG |
| LLM | DeepSeek vs OpenAI | DeepSeek | 便宜+中文好 |
| 切分策略 | 固定长度 vs 标题层级 | 标题层级 | 语义完整 |

---

## 六、已知问题与优化方向

| 问题 | 优先级 | 方向 |
|------|--------|------|
| 代码沙箱仅子进程 | 高 | Docker 容器 + gVisor |
| 流式输出未实现 | 高 | SSE 流式聊天 |
| RAG 仅 TF-IDF | 中 | pgvector + Embedding |
| 前端响应式不完善 | 中 | 移动端适配 |
| Token 消耗无面板 | 低 | 统计 + 可视化 |
| Prompt 版本管理未集成 | 低 | 已有模型，接 UI |
| 多语言支持 | 低 | 国际化 |
