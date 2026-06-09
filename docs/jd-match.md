# PyTutor 项目 vs 快手 AI 应用开发 JD 对照

> 逐条映射：JD 要求 → 我们项目做了什么 → 面试怎么讲

---

## 一、职位描述（职责）

### JD1：参与 AI 应用的全栈开发

**我们做了什么**：PyTutor 是完整的全栈项目——60+ 文件，前后端分离：

| 层级 | 技术 | 文件数 |
|------|------|--------|
| 前端 | Next.js 16 + React + TypeScript | 15+ |
| 后端 | FastAPI + Python + SQLAlchemy | 40+ |
| AI | LangGraph + DeepSeek + RAG | 10+ |
| 部署 | Docker + Docker Compose | 3 |

**面试讲法**："我从零搭建了一个全栈 AI 编程教学平台，包含用户认证、AI 对话、RAG 知识库、代码沙箱、ACM 判题五大模块。前端用 Next.js App Router，后端用 FastAPI 异步架构。"

---

### JD2：开发 MultiAgent 系统，探索上下文工程最佳实践

**我们做了什么**：用 LangGraph 构建了 6 节点 Agent 工作流（`backend/app/agents/graph.py`）：

```
[安全检查] → [意图识别] → {
    concept → [RAG检索] → [教学回复]
    code    → [RAG检索] → [代码执行] → [教学回复]
    unsafe  → [拒绝回复]
} → [输出校验] → 回复
```

**上下文工程实践**：
- System Prompt 三次迭代（100 行 JSON → 20 行纯文本）
- 消息组装顺序优化（System → RAG → Strategy → History → User）
- Token 压缩：最近 20 轮截断 + RAG Top-3 限制

**面试讲法**："我用 LangGraph 构建了 6 节点 Agent，每个节点有独立职责和容错。上下文工程上经历了三次 Prompt 迭代——从强制 JSON 到纯文本 Markdown，发现少即是多。"

---

### JD3：探索前沿 AI 技术（多模态、Agent 架构、RAG 优化、工具调用）

**我们做了什么**：

| 技术方向 | 实现 |
|---------|------|
| **多模态** | 集成千问 VL 视觉模型（`vision.js`），实现识图功能 |
| **Agent 架构** | LangGraph 状态图 + 条件路由 + 节点容错 |
| **RAG 优化** | TF-IDF 中文分词 + 标题加分 + 难度过滤 + 砍掉 LLM 重排序（精度换速度） |
| **工具调用** | Agent 可调用：RAG 检索工具 + 代码执行工具 + 练习生成工具 |

**面试讲法**："多模态方面，我配置了千问 VL 模型做截图识别。Agent 架构用 LangGraph 的条件边实现意图路由。RAG 上我做了一个 tradeoff 决策——砍掉 LLM 重排序节省 1.6 秒延迟。"

---

### JD4：跟踪 AI 技术趋势，研究产品/开源项目/论文

**我们做了什么**：
- 调研 DeepSeek vs 千问，最终选 DeepSeek（成本低、中文好）
- 调研 LangChain vs LangGraph，选 LangGraph（可观测性更好）
- 参考 Claude Vision Skill 开源项目，集成识图能力
- 生产了 14 章技术文档 + 25 题面试指南

**面试讲法**："我持续关注 AI 开发工具链，项目里选了 LangGraph 而非 LangChain，因为它的可视化状态图更适合多步 Agent。还研究了阿里的千问 VL 做多模态。"

---

## 二、任职要求

### JD5：熟悉至少一种编程语言（Python），了解数据结构与算法

**我们做了什么**：

- Python 后端 40+ 文件：异步编程（`async/await`）、Pydantic 类型校验、SQLAlchemy ORM
- 算法相关：TF-IDF 检索算法（自己实现，没用现成库）、中文 2-gram 分词
- 数据结构：Agent 用 TypedDict 做共享状态、堆栈管理对话历史

**面试讲法**："项目全程用 Python 开发，后端是 FastAPI 异步架构。RAG 的 TF-IDF 检索是我自己实现的，包括中文分词和 IDF 估计。"

---

### JD6：熟悉 AI 产品的使用逻辑与应用场景

**我们做了什么**：

- 核心使用场景：学生问 Python 问题 → AI 检索知识库 → 分层提示 → 引导思考
- 设计理念：不是"给答案的聊天机器人"，而是"会教学的导师"
- 分层提示 1-5 级、ACM 判题、学习画像——都是教育场景的特化设计

**面试讲法**："我们的产品不是通用聊天，而是针对编程教学场景深度定制——分层提示鼓励思考、ACM 判题模拟竞赛、学习画像追踪薄弱点。"

---

### JD7：了解 Agent 核心组件（Chains、Agents、Memory）

**我们做了什么**：

| Agent 组件 | 项目实现 | 文件 |
|-----------|---------|------|
| **Chains** | LangGraph 6 节点链式处理 | `app/agents/graph.py` |
| **Agents** | AgentState + 工具调用 + 意图路由 | `app/agents/state.py` |
| **Memory** | 短期：chat_messages + 20 轮窗口；长期：student_profiles + weaknesses | `app/models/chat.py`, `app/models/profile.py` |

**面试讲法**："我深入用过这三个组件。Memory 分两层：短期是上下文窗口 + sliding window 截断，长期是数据库持久化的学习画像。Chains 用 LangGraph 的状态图实现，每个 Node 是链条的一环。"

---

### JD8：了解 Prompt Engineering 的基本原理

**我们做了什么**：三次迭代（`backend/app/services/tutor_service.py`）：

| 版本 | 方案 | 结果 |
|------|------|------|
| V1 | 100 行 + JSON 输出 | 频繁解析失败 |
| V2 | 纯文本 + HTML 注释标记 | 稳定但冗长 |
| V3 | 20 行极简 | 当前最优 |

**面试讲法**："我经历了三次 Prompt 迭代。关键教训是小模型不适合复杂 JSON 约束，用 HTML 注释做轻量结构化比 JSON 稳定。'少即是多'——每删一行 Prompt，稳定性就提一分。"

---

## 三、加分项

### JD9：有 AI 相关项目经验，特别是大模型应用、Agent 开发

**我们对应**：PyTutor 就是完整的大模型应用 + Agent 开发项目。

**面法**："我独立开发了一个基于 DeepSeek + LangGraph 的 AI 编程教学平台，包含 6 节点 Agent、RAG 知识库、代码沙箱、ACM 判题。全程 60+ 文件、22 次 Git 提交。"

---

### JD10：具备跨学科思维，将 AI 与其他领域结合

**我们对应**：AI + 教育的跨学科结合。

**面法**："我把 AI 技术和教育学理论结合——分层提示（Scaffolding）来自教育心理学，ACM 判题来自编程竞赛，学习画像来自自适应学习理论。不是简单套用 AI，而是针对教学场景深度定制。"

---

## 四、面试话术速查

### 1 分钟自我介绍

> 我叫XXX，XX大学XX专业。我独立开发了一个 AI 编程教学平台叫 PyTutor。
> 
> 技术栈是 **FastAPI + Next.js + LangGraph + DeepSeek + RAG**，包含 6 节点 Agent 工作流、TF-IDF 知识库检索、Docker 代码沙箱和 ACM 判题系统。
> 
> 全程 60+ 文件、22 次 Git 提交，从零搭建到完整可用。过程中踩了很多坑——比如 Prompt 迭代了三次才找到最优方案，中文编码问题排查了 10 轮。我对 Agent 开发、RAG 优化、Prompt Engineering 都有实战经验。

### 高频问题即答

- **"RAG 怎么做的"** → TF-IDF + 标题加分 + 砍掉重排序（精度换速度）
- **"Agent 怎么设计的"** → LangGraph 6 节点 + 条件路由 + 每节点容错
- **"Prompt 怎么写的"** → 三次迭代，小模型不适合 JSON
- **"最难的 Bug"** → 中文乱码 10 轮排查，根因是两个函数 UTF-8 设置不一致
