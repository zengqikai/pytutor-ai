# 快手 AI 应用开发岗 · 面试准备指南

> 基于 PyTutor 项目，每题含：基础知识定义 + **项目具体实现（精确到文件路径和代码）**

---

## 一、Prompt Engineering

---

### Q1：讲一下你项目里的 Prompt 一般怎么写？

#### 基础知识

**Prompt** = 发给 LLM 的输入文本，决定输出质量。分 System Prompt（角色定义）和 User Prompt（具体问题）。

核心原则：① 明确角色 ② 给出约束 ③ 提供示例（Few-shot）④ 分步引导（CoT）⑤ 迭代优化。

#### 项目具体实现

**文件路径**：`backend/app/services/tutor_service.py` 第 47-63 行

经历了三次迭代：

**V1（失败——JSON 输出）**：100 行 Prompt，强制要求：
```json
{"response_type": "concept_explanation", "message": "...", "hint_level": 1}
```
→ DeepSeek 频繁返回非法 JSON（单引号、缺失括号），`_parse_ai_json()` 解析失败，用户看到乱码。
**记录在** `memory/issues-encountered.md` 问题 11。

**V2（改进——HTML 注释标记）**：取消 JSON，元数据放首行注释 `<!-- hint:1 concepts:x,y -->`，正文用 Markdown。

**V3（当前——极简版，第 47-49 行）**：
```python
SYSTEM_PROMPT = """你是 PyTutor，Python 编程导师。用中文回复，简洁明了。
规则：引导思考优先，不直接给答案。代码用 ```python 包裹。首行标注 <!-- hint:N concepts:x,y -->（N=1~5）。"""
```
只有 3 句话，不到 100 字。Prompt 越短，小模型越稳定。

**面试时强调**：这是"少即是多"的典型案例——每减少一行 Prompt，回复稳定性就提升一分。

---

### Q2：系统提示词和用户提示词有什么区别？能互换吗？

#### 基础知识

| | System Prompt | User Prompt |
|---|---|---|
| 位置 | 消息列表第一条，`role: "system"` | 最后一条，`role: "user"` |
| 权重 | 训练时特殊优化，最高优先级 | 普通 |
| 作用 | 定义角色、规则、输出格式 | 表达需求 |
| 持久性 | 整个对话不变 | 每轮变化 |

**不能互换**——System Prompt 在模型训练时有专门的 attention 权重分配，放到 User Prompt 中会被后续对话稀释。

#### 项目具体实现

**文件路径**：`backend/app/services/tutor_service.py` 第 219-230 行

消息组装顺序（面试重点——为什么这个顺序）：

```python
messages: list[LLMMessage] = [
    LLMMessage(role="system", content=SYSTEM_PROMPT),       # 1. 角色定义
]
if rag_context:
    messages.append(LLMMessage(role="system", content=rag_prompt))  # 2. RAG 知识
messages.append(LLMMessage(role="system", content=strategy_prompt)) # 3. 策略指令

for msg in history[-20:]:                                # 4. 最近 20 轮历史
    messages.append(...)
messages.append(LLMMessage(role="user", content=user_msg))       # 5. 用户问题
```

为什么 1→2→3→4→5 这个顺序：
- System Prompt 在最前面权重最高
- RAG 检索结果必须紧跟 System（让模型"先学知识再回答"）
- 策略指令（如 hint_level）在历史之前，影响本轮回复风格
- 最近 20 轮历史提供上下文连续性
- 用户输入在最后

**Agent 版 Prompt 组装**：`backend/app/agents/nodes/tutor_node.py` 第 30-48 行，增加了 `code_result` 和意图特定指令的注入。

---

## 二、RAG（检索增强生成）

---

### Q3：RAG 的核心流程是什么？

#### 基础知识

RAG = 检索 + 生成。解决 LLM"幻觉"问题——让模型先查知识库再回答。

流程：文档预处理 → 切分 → 向量化 → 存库 → 检索 → 重排序 → 注入 Prompt → 生成。

#### 项目具体实现

PyTutor 的 RAG 由 6 个文件组成：

**① 知识库数据**：`backend/scripts/seed_knowledge.py`——10 篇 Python 教程（变量、列表、for 循环、函数等）

**② 文档加载**：`backend/app/rag/loader.py`
- `load_markdown_file(path)` 读取单个 Markdown
- 自动提取 `# 标题` 作为文档标题

**③ 文档切分**：`backend/app/rag/splitter.py`
```python
MAX_CHUNK_SIZE = 2000
MIN_CHUNK_SIZE = 100

def split_markdown(content):
    # 步骤 1：按 ## 标题分段
    # 步骤 2：按 ### 标题分子段
    # 步骤 3：超长段落（>2000字）按空行再切
    # 步骤 4：太短的 chunk（<100字）合并到前一个
    return chunks  # 10 篇文档 → 41 个 chunk
```

**④ TF-IDF 检索**：`backend/app/rag/retriever.py`
```python
class HybridRetriever:
    def __init__(self):
        self._chunks: dict[str, dict] = {}  # 内存索引
        self._idf_cache: dict[str, float] = {}
    
    def search(self, query, top_k=5, difficulty_filter=None, concept_filter=None):
        # 1. 对查询分词（中文 2-gram + 英文单词 + Python 标识符）
        query_tokens = _tokenize(query)
        # 2. 计算每个 chunk 的 TF-IDF 得分
        # 3. 标题匹配加分（查询词出现在标题中 → +0.2）
        # 4. 按得分排序返回 Top-K
```

**⑤ 重排序（已砍掉）**：`backend/app/rag/reranker.py`
- 原本用 LLM 对初检索结果重排序（`rerank_with_llm()`）
- 每次加 ~1.6s 延迟，教学场景精度要求不高
- **最终在 `backend/app/services/rag_service.py` 第 76 行砍掉**：
  ```python
  # 之前：reranked = await rerank_with_llm(...)
  # 现在：reranked = candidates[:request.top_k]
  ```
- 这是精度换速度的工程 tradeoff，面试时强调！

**⑥ 索引管理**：`backend/app/services/rag_service.py`
- `ingest_document()`——导入文档（切分 + 入库 + 加入内存索引）
- `rebuild_index()`——服务重启时从数据库重建内存索引（`backend/app/main.py` 第 72-78 行，lifespan 启动时调用）

**⑦ 聊天集成**：`backend/app/services/chat_service.py` 第 219-235 行
```python
# 步骤 4：RAG 检索相关知识
retrieval_result = await retrieve_context(db, RAGRetrievalRequest(query=content, top_k=3))
if retrieval_result.results:
    rag_context = format_context_for_llm(retrieval_result.results)

# 步骤 5：传给 AI 导师
ai_response = await generate_tutor_response(..., rag_context=rag_context)
```

---

### Q4：长文档切片的粒度怎么选择？

#### 基础知识

| 策略 | 原理 | 适用场景 |
|------|------|---------|
| 固定长度 | 每 N 字符一刀 | 简单场景 |
| 语义切分 | 按标题/段落 | 文档问答（我们用的） |
| 递归切分 | 先大后小，超长再切 | 通用 |
| 滑动窗口 | 有重叠 | 防止漏信息 |

推荐范围：500-2000 字符；FAQ 用小 chunk，文档用大 chunk。

#### 项目具体实现

**文件路径**：`backend/app/rag/splitter.py`

```python
MAX_CHUNK_SIZE = 2000   # 最大 2000 字符
MIN_CHUNK_SIZE = 100    # 太小的合并到上一个

# 切分结果：10 篇 → 41 个 chunk
# 例如 "Python for 循环" 5 个 chunk：
#   [0] ## 什么是 for 循环
#   [1] ## for 循环的基本语法
#   [2] ## range() 函数
#   [3] ## 遍历列表
#   [4] ## 常见错误
```

每个 chunk 存到数据库的结构（`backend/app/models/rag.py`）：
```python
class RAGChunk(Base):
    content: str          # 文本内容
    heading: str          # 所属章节标题（如 "range() 函数"）
    tokens: str           # 分词后的 tokens（空格分隔，用于检索）
    difficulty: str       # 难度级别
    concepts: str         # 关联知识点标签
    retrieval_count: int  # 被检索次数（用于效果分析）
```

---

### Q5：既然向量检索已经算相似度了，为什么还要重排序？

#### 基础知识

| | Bi-Encoder（向量检索） | Cross-Encoder（重排序） |
|---|---|---|
| 原理 | Query 和 Doc 分别编码 | Query 和 Doc 一起输入 |
| 交互 | 无（各算各的向量） | 有（Attention 全交互） |
| 速度 | 快（可以预计算所有向量） | 慢（每对都要重新算） |
| 精度 | 较低 | 高 |
| 场景 | 初筛（召回） | 精选（精排） |

#### 项目具体实现

**文件路径**：`backend/app/rag/reranker.py`——LLM 做重排序：

```python
RERANK_PROMPT = """评估以下文档片段与查询的相关性。
查询：{query}
文档片段：{documents}
请对每个文档打分（0-10），选出最相关的 {top_n} 个。"""

async def rerank_with_llm(query, candidates, top_n=3):
    llm_response = await chat_completion(messages=[...], temperature=0.0)
    rankings = json.loads(llm_response.content)
    # 按得分排序返回 Top-N
```

**但我们在 `backend/app/services/rag_service.py` 第 76 行砍掉了它**：

```python
# 砍掉前：初检索 9 → LLM重排 → Top-3（总耗时 ~4.6s）
# 砍掉后：初检索 9 → 直接截断 Top-3（总耗时 ~3s）
reranked = candidates[:request.top_k]  # 省 1.6s
```

**原因**：教学场景的检索精度要求不高（不像法律/医疗），TF-IDF 直接 Top-K 已经满足需求。面试时要强调**"精度换速度"是合理的工程决策**，不是所有场景都需要重排序。

---

### Q6：Rerank 的 Top-K 数量怎么确定？

#### 项目具体实现

```python
# backend/app/services/rag_service.py
candidates = retriever.search(query, top_k=request.top_k * 3)  # 初检索 3 倍

# 最终取 Top-K（我们砍掉了 LLM 重排序后直接截断）
reranked = candidates[:request.top_k]
```

默认 `top_k=3` → 初检索 9 个 → 返回 3 个。3 个 chunk 足够覆盖一个知识点，又不会让 Prompt 太长。

**确定方法**：通过测试验证——3 个 chunk 的回答质量与 5 个无显著差异，但 Token 消耗少 40%。

---

### Q7：我们的知识库检索有什么亮点？

#### 项目具体实现

**亮点 1——TF-IDF 混合中文分词**（`backend/app/rag/retriever.py` 第 140-165 行）：

```python
def _tokenize(text):
    # 1. Python 标识符：提取 `反引号` 中的变量名
    # 2. 英文单词：3 个字母以上
    # 3. 中文 2-gram：两个连续汉字为一组
    # 去重后返回
```

**亮点 2——标题匹配加分**（第 120 行）：
```python
# 查询词出现在 chunk 的 heading 中 → 额外 +0.2 分
if qt.lower() in heading_lower:
    heading_bonus += 0.2
```

**亮点 3——内存索引 + 启动重建**（`backend/app/main.py` 第 72-78 行）：
```python
# 服务启动时从数据库加载 41 个 chunk 到内存
chunk_count = await rebuild_index(session)
```
→ 毫秒级检索速度，不需要外部向量数据库

**亮点 4——难度和知识点过滤**：
```python
retriever.search(query, difficulty_filter="beginner", concept_filter="for_loop")
# 初学者只检索入门级内容，教师可查看全部
```

---

### Q8：如何评估 RAG 的有效性？

#### 基础知识（Ragas 框架）

| 指标 | 含义 |
|------|------|
| Faithfulness | 回答是否基于检索内容（幻觉检测） |
| Context Relevance | 检索内容与问题是否相关 |
| Answer Relevance | 回答是否切题 |
| Context Recall | 检索是否覆盖了需要的信息 |

#### 项目具体实现

**文件路径**：`evaluation/golden_dataset.json`——8 个测试用例

```json
{
  "id": "g001",
  "input": "什么是 Python 中的变量？",
  "expected_concepts": ["variables", "assignment"],
  "expected_hint_level": 1,
  "expected_contains": ["变量", "赋值", "存储"]
}
```

**评测脚本**：`evaluation/run_eval.py`
```python
for case in golden_cases:
    result = await llm.chat(case["input"])
    # 维度 1：内容相关度（关键词包含检查）
    for keyword in case["expected_contains"]:
        if keyword not in result: fail()
    # 维度 2：格式有效性
    if not result.strip(): fail()
```

**当前局限**（面试时说改进方向）：用关键词匹配太粗糙，生产应接入 Ragas 做自动化四维评估。

---

## 三、Agent 架构与 LangGraph

---

### Q9：Agent 和普通 LLM 有什么区别？为什么用 LangGraph？

#### 基础知识

LLM = 只有嘴（能说话）。Agent = 有嘴 + 有手（能调工具）+ 有大脑（能规划）。

LangGraph 三个核心概念：State（共享状态）、Node（处理函数）、Conditional Edge（条件路由）。

#### 项目具体实现

**Agent 工作流定义**：`backend/app/agents/graph.py`

```
用户输入 → [安全检查] → [意图识别] → {
    concept_question → [RAG检索] → [教学回复]
    code_debug       → [RAG检索] → [代码执行] → [教学回复]
    general          → [教学回复]
    unsafe           → [拒绝回复]
} → [输出校验] → 回复
```

**6 个节点的实现文件**：
| 节点 | 文件 | 核心逻辑 |
|------|------|---------|
| 安全检查 | `app/agents/nodes/safety_check.py` | 关键词匹配拦截 Prompt Injection |
| 意图识别 | `app/agents/nodes/intent_router.py` | LLM 分类 + 关键词预判兜底 |
| RAG 检索 | `app/agents/nodes/rag_retrieval.py` | 调 `retrieve_context()` 获取知识 |
| 代码执行 | `app/agents/nodes/code_executor.py` | 调 `execute_python_code()` 沙箱执行 |
| 教学回复 | `app/agents/nodes/tutor_node.py` | 组装 Prompt → LLM → 解析回复 |
| 输出校验 | `app/agents/nodes/output_validator.py` | 检查必需字段、类型、范围 |

**共享状态**：`backend/app/agents/state.py`
```python
class AgentState(TypedDict):
    user_input: str
    intent: str                    # safet_check 写入，intent_router 更新
    rag_context: Optional[str]     # rag_retrieval 写入
    code_result: Optional[dict]    # code_executor 写入
    tutor_response: Optional[dict] # tutor_node 写入
    safety_result: str             # safety_check 写入
    is_valid_output: bool          # output_validator 写入
```
→ 每个节点读写同一个 State，就像流水线传递产品。

**条件路由**：`backend/app/agents/graph.py` 第 80-110 行
```python
def route_after_safety(state):
    if state["safety_result"] == "block":
        return "reject_response"   # 危险输入 → 拒绝
    return "intent_router"         # 安全 → 继续

def route_after_intent(state):
    intent = state.get("intent", "general")
    routes = {
        "concept_question": "rag_retrieval",
        "code_debug": "rag_retrieval",
        "general": "tutor_response",
    }
    return routes.get(intent, "tutor_response")  # 未知意图 → 兜底
```

**入口调用**：`backend/app/services/agent_service.py` → `backend/app/api/v1/agent.py`

---

### Q10：Agent 中的记忆怎么存储？

#### 基础知识

| | 短期记忆 | 长期记忆 |
|---|---|---|
| 内容 | 当前对话消息 | 用户画像、知识点掌握度 |
| 生命周期 | 单次会话 | 跨会话持久 |
| 存储 | 上下文窗口（最近 20 轮） | 数据库 |

#### 项目具体实现

**短期记忆**：`backend/app/models/chat.py`
```python
class ChatMessage(Base):
    session_id: str   # 属于哪个会话
    role: str         # user / assistant
    content: str      # 消息文本
    hint_level: int   # 提示等级（仅 assistant）
```
→ 每次 LLM 调用携带最近 20 轮消息（`tutor_service.py` 第 229 行 `history[-20:]`）

**长期记忆**：`backend/app/models/profile.py`
```python
class StudentProfile(Base):
    level: int                   # 能力等级 1-10
    concept_mastery_json: str    # {"variables": 0.8, "for_loop": 0.3}
    total_exercises_completed: int

class StudentWeakness(Base):
    concept: str    # 知识点标识
    fail_count: int # 连续失败次数
    severity: int   # 严重程度 1-5
```
→ 每次学习行为触发 `profile_service.py` 更新画像

---

### Q11：安全护栏是怎么设计的？

#### 项目具体实现

**两层防护**：

**第一层——输入安全检查**：`backend/app/agents/nodes/safety_check.py`
```python
UNSAFE_PATTERNS = ["ignore previous instructions", "system prompt", "jailbreak", ...]
# 关键词匹配拦截 Prompt Injection
```

**第二层——代码沙箱**：`backend/app/sandbox/security.py`
```python
def check_code_safety(code):
    cleaned = _remove_strings_and_comments(code)  # 先去掉注释和字符串！
    for module in FORBIDDEN_MODULES:
        if re.search(rf"\bimport\s+{module}\b", cleaned):
            return False, f"禁止导入模块: {module}"
```

**关键设计——去掉注释和字符串再检查**（`security.py` 第 80-88 行）：
```python
def _remove_strings_and_comments(code):
    code = re.sub(r"#.*$", "", code, flags=re.MULTILINE)   # 去注释
    code = re.sub(r'""".*?"""', '""', code, flags=re.DOTALL)  # 去三引号
    code = re.sub(r"'[^']*'", "''", code)   # 去字符串
    return code
```
→ 防止 `print("import os")` 这样的正常代码被误杀。面试时强调这个细节！

**第三层——子进程隔离**：`backend/app/sandbox/executor.py`
- `-X utf8` 强制 UTF-8 模式（修复了 10 轮的中文乱码问题）
- `PYTHONUTF8=1` 环境变量
- 超时 10 秒 + 输出限制 100KB

---

### Q12：如何防止 Agent 陷入死循环？

#### 项目具体实现

我们的 DAG 图结构本身无环——所有路径最终到 `output_validator` → `END`。

条件路由有兜底（`graph.py` 第 95 行）：
```python
return routes.get(intent, "tutor_response")  # 未知意图 → 默认处理
```

每个节点有容错（`tutor_node.py` 第 55-67 行）：
```python
try:
    llm_response = await chat_completion(...)
    return {"tutor_response": ...}
except json.JSONDecodeError:
    # JSON 解析失败 → Fallback 用原始文本
    return {"tutor_response": AIResponse(message=llm_response.content[:2000])}
except Exception:
    return {"error": "AI 回复生成失败"}
```

---

## 四、代码沙箱与 ACM 判题

---

### Q13：代码沙箱怎么做的？

#### 项目具体实现

**安全拦截**：`backend/app/sandbox/security.py`
- 正则匹配危险模块（os, subprocess, socket...）
- 先去掉注释和字符串再检查

**子进程隔离**：`backend/app/sandbox/executor.py`

两个执行函数：
- `execute_python_code(code)`——聊天编辑器用
- `execute_python_code_with_input(code, stdin_input)`——ACM 判题用

```python
# UTF-8 编码设置（修复了 10 轮的中文乱码）
env["PYTHONIOENCODING"] = "utf-8"
env["PYTHONUTF8"] = "1"
process = await asyncio.create_subprocess_exec(
    sys.executable, "-X", "utf8", str(tmp_path),
    stdin=asyncio.subprocess.PIPE,
    stdout=asyncio.subprocess.PIPE,
    stderr=asyncio.subprocess.PIPE,
    env=env,
)
```

**关键 Bug 修复记录**（面试时可以作为"解决复杂问题"的案例）：
- 两个执行函数的 UTF-8 设置不一致 → `execute_python_code` 少了 `-X utf8` → 中文乱码 10 轮排查
- `bytes` literal 不能含中文 → 改 `.encode("utf-8")`
- 空输入导致 `EOFError` → 空字符串加 `\n` 变成空行

---

### Q14：ACM 判题系统怎么实现的？

#### 项目具体实现

**判题入口**：`backend/app/api/v1/exercises.py` 第 65-135 行

```python
# 每个测试用例独立执行！
for tc in exercise.test_cases:
    exec_result = await execute_python_code_with_input(
        user_code,
        stdin_input=tc.input_data or "",  # stdin 传入测试数据
    )
    # 比较输出（.rstrip() 去末尾空白——ACM 标准）
    if exec_result["stdout"].rstrip() == tc.expected_output.rstrip():
        passed += 1
```

**与普通执行的关键区别**：
- 普通：只跑一次，不传 stdin → `input()` 报 `EOFError`
- ACM：每个测试用例独立跑一次，stdin 传入 `input_data`

---

## 五、面试模板

### 每个问题的回答结构

```
1. "这个技术是什么"（15 秒）—— 一句话定义
2. "我们在 PyTutor 里怎么用的"（1 分钟）—— 具体文件路径 + 代码逻辑
3. "遇到了什么问题，怎么解决的"（30 秒）—— 踩坑经验
4. "如果继续做，会怎么改进"（15 秒）—— 思考深度
```

### 必准备的亮点故事

1. **Prompt 迭代**：JSON → 纯文本，三次迭代的决策过程（`tutor_service.py`）
2. **砍掉 Reranker**：精度换速度，1.6s → 0ms（`rag_service.py` 第 76 行）
3. **LangGraph 条件路由**：6 节点 + 4 条条件边（`graph.py`）
4. **ACM stdin EOFError**：排查 3 轮的根因分析（`executor.py`）
5. **中文乱码 10 轮排查**：两个执行函数 UTF-8 设置不一致（`executor.py`）
