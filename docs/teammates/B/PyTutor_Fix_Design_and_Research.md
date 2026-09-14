# PyTutor 3.0 修复设计规格 + 科研方向

> 本文只做**设计**不做实现：每一项给出「改哪里 / 设计思路 / 接口签名 / 伪代码骨架 / 边界与测试用例」，你照着写代码即可。第二部分给出可发表的创新研究方向。
>
> 约定：所有伪代码是**设计草图**，标注了关键分支和数据结构，不是可直接运行的成品。

---

# 第一部分：修复设计

## Tier 0 — Critical（先做这三个，工作量都小）

### F1. 配置安全护栏：占位符密钥 / debug 生产拒绝启动

**改哪里**：`backend/app/core/config.py` 的 `Settings` 类（在 `settings = Settings()` 之前加校验器）。

**设计思路**：把「生产环境不能用占位符密钥、不能开 debug」从「文档提醒」升级为「启动时硬失败」。用 pydantic v2 的 `model_validator(mode="after")`，在实例化时就抛异常，让错误配置根本起不来，而不是运行到某个请求才暴露。

**接口/骨架**：

```python
# config.py  —— 设计草图
from pydantic import model_validator

_PLACEHOLDER_SECRETS = {
    "change-me-to-a-random-string",
    "change-me-to-a-random-string-at-least-32-chars",
    "", "secret", "changeme",
}

class Settings(BaseSettings):
    ...
    @model_validator(mode="after")
    def _enforce_prod_hardening(self):
        is_prod = self.app_env.lower() in {"production", "prod", "staging"}
        if is_prod:
            if self.secret_key in _PLACEHOLDER_SECRETS or len(self.secret_key) < 32:
                raise ValueError("生产环境 SECRET_KEY 必须是 >=32 位强随机串，且不能是占位符")
            if self.debug:
                raise ValueError("生产环境必须 debug=False")
            if self.log_level.upper() == "DEBUG":
                # 不致命，降级即可
                object.__setattr__(self, "log_level", "INFO")
        return self
```

**边界**：
- 开发环境（`development`/`testing`）完全放行，不影响本地调试。
- `staging` 也纳入强校验（预生产同样不该用占位符）。

**测试**：`app_env=production` + 占位符 key → 断言 `Settings()` 抛 `ValidationError`；`app_env=development` + 占位符 → 断言正常构造。

**严重程度 Critical｜工作量 Small**

---

### F2. 修复被短路的教学策略：`has_history` / `attempt_count` 传真值

**改哪里**：`backend/app/services/chat_service.py:397`（当前硬编码 `has_history=False`）+ 新增一个查询函数到 `misconception_service.py`。

**设计思路**：`select_strategy()` 的「重复误区 → 概念解释」分支是核心卖点，但输入永远是 False。要修就得在调用前，去 `MisconceptionEvent` 表查**这个学生 + 这个 misconception_id** 的历史命中次数，用真实计数驱动策略。

**新增接口签名**：

```python
# misconception_service.py —— 新增
async def get_misconception_history_count(
    db: AsyncSession, user_id: str, misconception_id: str
) -> int:
    """返回该学生该误区的历史命中次数（不含本次）。"""
    # SELECT count(*) FROM misconception_events
    # WHERE user_id=? AND misconception_id=?
```

**调用点改造（chat_service.py 伪代码）**：

```python
if misconception_result:
    mc_id = misconception_result["misconception_id"]
    prior_count = await get_misconception_history_count(db, user.id, mc_id)  # 新增
    strategy = select_strategy(
        misconception_id=mc_id,
        attempt_count=prior_count + 1,          # 真实累计次数
        has_history=(prior_count > 0),          # 真实历史
    )
    ...
```

**注意顺序**：`record_misconception_event()` 必须在 `get_misconception_history_count()` **之后**调用，否则本次会把自己算进去。确认调用链里是「先查历史 → 选策略 → 生成回复 → 再记事件」。

**边界**：老用户没有历史表数据时退化为首次逻辑（正确）。

**测试**：mock 历史 0 次 → 期望 `progressive_hint`；mock 3 次 → 期望 `concept_explanation`。这正好补上你目前 CI 里缺的策略集成测试。

**严重程度 Critical｜工作量 Small**

---

### F3. 沙箱：统一执行入口 + 生产强制隔离 + 拒绝静默降级

**改哪里**：
1. 新增统一分发函数（建议放 `sandbox/__init__.py` 或新建 `sandbox/runner.py`）；
2. `code_service.py:56-59` 改为调用统一入口，不再直接 import subprocess 版本；
3. `docker_executor.py:57` 的「Docker 不可用 → 静默回退 subprocess」改为「生产环境拒绝执行」；
4. `executor.py` 的 subprocess 版补 `rlimit` 内存限制（作为本地开发的兜底防线）；
5. `security.py` 把 `open()` 读也收紧（见 F4）。

**设计思路（核心是一张决策表）**：

| app_env | Docker 可用 | 行为 |
|---|---|---|
| production/staging | 是 | 走 Docker |
| production/staging | 否 | **拒绝执行**，返回 `status="unavailable"`，告警 |
| development/testing | 是 | 走 Docker（可选，默认走 subprocess 提速） |
| development/testing | 否 | subprocess（带 rlimit） |

**统一入口签名**：

```python
# sandbox/runner.py —— 设计草图
async def run_user_code(code: str, stdin_input: str = "") -> dict:
    """唯一对外执行入口。根据 app_env + Docker 可用性分发。"""
    is_prod = settings.app_env.lower() in {"production", "staging"}
    if is_prod:
        if await _docker_available():
            return await execute_in_docker(code, stdin_input)
        logger.error("sandbox_no_isolation_in_prod")     # 告警
        return {"status": "unavailable",
                "stderr": "代码执行服务暂不可用（隔离环境未就绪）",
                "exit_code": None, "stdout": "", "runtime_ms": 0,
                "memory_kb": None, "timeout_triggered": False}
    # 开发环境
    return await execute_python_code_with_input(code, stdin_input)
```

**subprocess 版补内存限制（executor.py）**：Linux 上用 `preexec_fn` 设 `RLIMIT_AS`：

```python
import resource
def _limit_resources():
    mem = 256 * 1024 * 1024  # 256MB 地址空间
    resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))  # CPU 秒兜底
# create_subprocess_exec(..., preexec_fn=_limit_resources)  # 注意 Windows 不支持，需按平台分支
```

> Windows 开发机没有 `preexec_fn`/`resource`，需 `if sys.platform != "win32"` 分支；这也是为什么生产必须走 Docker——Docker 的 `--memory 128m` 是跨平台的正解。

**边界**：`run_user_code` 要成为**唯一**入口，全仓 grep `execute_python_code` 确保没有旁路调用绕过分发。

**测试**：渗透测试断言（见 F4）+ 「production + Docker 不可用 → status==unavailable」。

**严重程度 Critical｜工作量 Medium**

---

## Tier 1 — Major

### F4. 静态安全检查：从「安全边界」降级为「UX 提示」，并堵住已知绕过

**改哪里**：`backend/app/sandbox/security.py`。

**设计思路**：黑名单原理上堵不完（已复现 `getattr(__builtins__,'ev'+'al')`、`().__class__.__bases__[0].__subclasses__()`、`open('/etc/passwd').read()`）。所以**架构定位要变**：真正的边界是 F3 的 Docker 隔离；`security.py` 只负责「在进沙箱前，对明显危险给友好提示」，不再假装是安全屏障。但仍要把当前几个低成本能堵的堵上：

1. `open()` 读也限制——初学者练习用不到读任意文件，直接**默认禁止所有 `open(`**（无论读写），需要文件练习时白名单专门开。
2. 增加对 `__subclasses__`、`__bases__`、`__globals__`、`__builtins__`、`getattr(` 的**告警级**匹配（不一定拦死，但标记 `suspicious=True` 记日志，供后续观测）。
3. 明确在函数 docstring 写清：**本函数不是安全边界**。

**签名调整**（返回值扩展，向后兼容）：

```python
def check_code_safety(code: str) -> tuple[bool, str]:
    """UX 层预检，非安全边界。真正隔离见 docker_executor。"""
    # 保留现有黑名单
    # 新增：open( 全禁（除非白名单）
    if re.search(r"\bopen\s*\(", cleaned):
        return False, "当前环境不支持文件读写"
    # 新增：反射逃逸告警（记日志，可选拦截）
    for probe in ["__subclasses__", "__bases__", "__globals__", "getattr(__builtins__"]:
        if probe in cleaned:
            logger.warning("sandbox_reflection_probe", probe=probe)
            # 生产可选择 return False；开发放行但记录
```

**关键认知**：不要在 F4 上追求「堵死所有绕过」——那是 F3（隔离）的活。F4 只做「常见误操作友好拦截 + 可疑行为观测」。

**渗透测试集**（新建 `tests/test_sandbox_security.py`，把这些做成必过断言）：

```
must_block = [
  "__import__('os').system('id')",
  "open('/etc/passwd').read()",
  "getattr(__builtins__,'ev'+'al')('1')",   # 需要 F4 增强才能拦
  "().__class__.__bases__[0].__subclasses__()",  # 靠隔离而非静态拦，测 Docker 层
]
must_allow = [
  "for i in range(10): print(i)",
  "d={'a':1}\nfor k in d: print(d[k])",     # 合法字典遍历，别误杀
]
```

**严重程度 Major｜工作量 Medium**

---

### F5. AST 误区诊断：消除已复现的四类假阳性

这是对外指标可信度的核心。**改哪里**：`backend/app/analysis/ast_visitors.py`。四个独立小改：

#### F5.1 M4 排除字典遍历
**问题**：`for k in d: d[k]` 被误报（`M4ValueAsIndexVisitor`，`ast_visitors.py:98`）。
**设计**：给 visitor 传入「已知是 dict 的变量集合」，若 iter 名在其中则不触发。dict 判定来源：上文赋值 `x = {...}`（`ast.Dict`）或 `x = dict(...)`。

```python
class M4ValueAsIndexVisitor:
    def __init__(self, dict_vars: set[str] = frozenset()):
        self._dict_vars = dict_vars
    def visit_For(self, node):
        iter_name = self._extract_iter_name(node.iter)
        if iter_name in self._dict_vars:     # 新增：字典遍历合法，跳过
            return self.generic_visit(node)
        ...
```
`dict_vars` 由 analyzer 预扫一遍模块得到（一个轻量 `_collect_dict_vars(tree)` 函数）。

#### F5.2 M8 排除 mutating-method 收敛循环
**问题**：`while items: items.pop()`、`while q: q.popleft()` 被误报（`M8WhileInfiniteVisitor`，`ast_visitors.py:660`）。
**设计**：`_extract_modified_vars()` 除了 `Assign/AugAssign/For`，再补一条——**若条件变量作为任意方法调用的接收者出现**（`Call(func=Attribute(value=Name(id=条件变量)))`），视为「可能被修改」，保守不报。

```python
@staticmethod
def _extract_modified_vars(while_node) -> set[str]:
    modified = set()
    for node in ast.walk(while_node):
        ... # 现有 Assign/AugAssign/For 逻辑
        # 新增：方法调用接收者
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            recv = node.func.value
            if isinstance(recv, ast.Name):
                modified.add(recv.id)     # items.pop() → items 视为被改
    return modified
```
宁可漏报（放过真无限循环）也别误伤合法 pop 循环——教学场景假阳性代价更高。

#### F5.3 M5 消除「题面循环论证」
**问题**：题面含「range/到」等词就 +0.6 过阈值（`M5RangeBoundaryVisitor.evaluate`，`ast_visitors.py:210`）。
**设计**：
- 关键词表**删掉 `"range"`**（它是题目必然出现的词，不是误解信号）。
- 外部信号权重 `0.6 → 0.3`，且**必须叠加** AST 结构信号（`stop_ref_in_body`）才过阈值。
- 分离参数语义：新增 `student_confusion: str` 参数专门接「学生表达困惑的原话」，不要再把 `exercise_context`（题面=期望）当困惑信号。

```python
def evaluate(self, stderr="", student_confusion="") -> dict | None:
    KEYWORDS = ["不到","不包含","为什么只到","少一个","边界","不包括","最后"]  # 去掉 range
    has_signal = any(k in (stderr+student_confusion).lower() for k in KEYWORDS)
    score = 0.0
    for rc in self.range_calls:
        if rc.get("stop_ref_in_body"): score += 0.5
    if has_signal: score += 0.3
    # 关键：纯外部信号不足以过阈值，必须有结构信号
    structural = any(rc.get("stop_ref_in_body") for rc in self.range_calls)
    if score >= 0.6 and structural:
        return {...}
    return None
```
调用链上把 `misconception_service.py:165` 的 `student_question = exercise_context or ""` 拆成两个来源：题面 → 不进信号；学生消息里的困惑句 → 进信号。

#### F5.4 M7 修复「重赋值不覆盖」+ 顺序敏感 + 补 `%`/`//`
**问题**：`x=input(); x=int(x); y=x*2` 因 `ast.walk` 无序遍历被误报（`_scan_assignments`，`ast_visitors.py:452`）。
**设计**：把类型收集从「无序 walk」改成「按语句顺序前向扫描」，后一次赋值覆盖前一次；`int()/float()` 结果登记为 `"num"`。

```python
def _scan_assignments_ordered(self, body: list[ast.stmt]):
    """按出现顺序更新 _var_types，后写覆盖先写。"""
    for stmt in body:                      # 顺序遍历顶层语句
        if isinstance(stmt, ast.Assign) and len(stmt.targets)==1 \
           and isinstance(stmt.targets[0], ast.Name):
            name = stmt.targets[0].id
            v = stmt.value
            if _is_input_call(v):                       self._var_types[name]="input"
            elif _is_call_to(v, ("int","float","len")):  self._var_types[name]="num"  # 关键修复
            elif isinstance(v, ast.Constant):
                self._var_types[name] = "str" if isinstance(v.value,str) else "num"
            # else: 未知类型，删除旧登记避免误判
            else: self._var_types.pop(name, None)
```
补运算符：算术分支加 `ast.FloorDiv`；`ast.Mod` 单独处理——左操作数是 str **字面量**时判为格式化（不报），是 input 变量时报 M7。

**F5 整体测试**：把上面每个假阳性用例加进 `test_ast_analyzer.py`，断言**不触发**；同时保留原有正例断言不回归。**并把 `test_ast_analyzer.py` 加进 CI**（见 F8）。

**严重程度 Major｜工作量 Medium**

---

### F6. LLM 不可用时用 AST 兜底（而非直接 503）

**改哪里**：`chat_service.py:410` 的 `except Exception → raise 503` 分支。

**设计思路**：误区诊断（AST）**不依赖** DeepSeek。当 LLM 生成挂掉但已经有 `misconception_result` 时，用模板把 `evidence` 渲染成一条确定性教学提示返回，degrade 而不 fail。

```python
except Exception as e:
    logger.error("ai_generation_failed", error=str(e))
    await db.commit()  # 用户消息仍要存
    if misconception_result:                      # 新增兜底分支
        fallback = render_static_hint(misconception_result)  # 见下
        assistant_msg = ChatMessage(..., content=fallback, hint_level=1)
        db.add(assistant_msg); await db.commit()
        return {..., "degraded": True}            # 标记降级，前端可提示
    raise HTTPException(503, "AI 服务暂时不可用")
```

```python
def render_static_hint(mc: dict) -> str:
    """无 LLM 时的模板化提示，只用 AST evidence，不编造。"""
    return (f"我注意到一个常见的思路点：**{mc['misconception_name']}**。\n\n"
            f"{mc['evidence']}\n\n"
            f"（AI 导师暂时繁忙，先给你这条基于代码结构的提示，"
            f"稍后可以再问我细节。）")
```

**边界**：只在有高置信度 AST finding 时兜底；纯 LLM 场景（无代码）仍走 503。

**严重程度 Major｜工作量 Small**

---

### F7. RAG 熔断 + 缩短超时

**改哪里**：`chat_service.py:300`（15s 超时）+ 新增一个进程内熔断器（可放 `rag_service.py`）。

**设计思路**：ChromaDB 持续挂时，每请求白等 15s 是雪崩。用一个轻量熔断器：连续 N 次超时后进入 `open` 状态，一段时间内直接跳过 RAG，周期性半开试探。

```python
# rag_service.py —— 进程内熔断器（够用即可，不必引重库）
class _Breaker:
    fail_count = 0; open_until = 0.0
    THRESHOLD = 3; COOLDOWN = 30  # 秒
    @classmethod
    def is_open(cls): return time.time() < cls.open_until
    @classmethod
    def record_fail(cls):
        cls.fail_count += 1
        if cls.fail_count >= cls.THRESHOLD:
            cls.open_until = time.time() + cls.COOLDOWN
    @classmethod
    def record_ok(cls): cls.fail_count = 0
```

调用点：

```python
if not _Breaker.is_open():
    try:
        result = await asyncio.wait_for(retrieve_context(...), timeout=3.0)  # 15→3
        _Breaker.record_ok(); ...
    except (asyncio.TimeoutError, Exception):
        _Breaker.record_fail()
# open 状态直接跳过 RAG，rag_context=None
```

**严重程度 Major｜工作量 Small**

---

### F8. 前端注册静默失败 + CI 补测试

**改哪里**：`frontend/src/app/register/page.tsx:18`（空 catch）+ `.github/workflows/ci.yml`。

**前端设计**：catch 里 set error state 并渲染；提交前做客户端邮箱正则预校验。

```tsx
const [error, setError] = useState("");
async function onSubmit() {
  setError("");
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    setError("邮箱格式不正确"); return;
  }
  try { await register(email, password, displayName); router.push("/"); }
  catch (e) { setError("注册失败：邮箱可能已被使用或格式不符"); }  // 不再空 catch
}
// JSX 里渲染 {error && <p className="text-red-500">{error}</p>}
```

**CI 设计**：现在只跑 `test_misconception.py test_pedagogy.py`。改为把 AST 测试、API 测试、沙箱渗透测试都纳入：

```yaml
- name: Unit tests
  run: python -m pytest tests/test_ast_analyzer.py tests/test_misconception.py \
       tests/test_pedagogy.py tests/test_sandbox_security.py tests/test_api.py -v
```

**严重程度 Major｜工作量 Small**

---

### F9. 并发安全：累积字段改事件表 append + 读时聚合

**改哪里**：`chat_service.py:335-360`（读 profile → 改 JSON → 写回的 read-modify-write）。

**设计思路**：`recent_misconceptions`/`weak_topics` 就地改 JSON 在 PostgreSQL 并发下会丢更新。改为**只往 `MisconceptionEvent` append**（本就有这张表），画像里的「最近误区」改为**读时** `SELECT ... ORDER BY created_at DESC LIMIT 5` 聚合，不再持久化冗余 JSON。

- 一次请求收敛为**一次** commit（当前有多次）。
- 若为性能保留缓存字段，用数据库端原子更新（`UPDATE ... SET col = <expr>`）或行锁，别在应用层读改写。

**严重程度 Major｜工作量 Medium**

---

### F10. Agent 链路每个外部依赖节点加超时

**改哪里**：`agents/nodes/rag_retrieval.py` 等无超时保护的节点。

**设计**：给每个调用外部服务（RAG、LLM）的节点包 `asyncio.wait_for`，超时后写入 state 的降级标志，让 `graph.py` 的条件路由能据此走兜底路径，避免整链 hang。与 F7 的熔断器共用同一套。

**严重程度 Major｜工作量 Medium**

---

## 修复顺序建议

先 F1/F2/F3（Critical，半天内可完成）→ 再 F5/F8（恢复指标可信度 + 让 CI 能拦回归）→ 然后 F4/F6/F7/F9/F10。F5 和 F8 要一起做：改完 visitor 立刻把对抗用例进 CI，否则改动本身也可能引入新回归。

---

# 第二部分：科研方向（创新性）

> 前提：上面 F5/F11 的假阳性和评测泄漏修完之后再谈发表，否则 reviewer 自己构造对抗样本就能推翻你的指标。以下方向按「新颖性 × 可行性」排序，标注了研究问题、为什么新、方法骨架、所需数据、目标会议、风险。

## R1.【最推荐】Notional Machine 反演：把学生的心智解释器建成可推断的扰动语义

**研究问题**：能否**从学生的错误输出反推出他大脑里运行的是哪一台「错误的 Python 解释器」**？

**核心洞察（也是新颖点）**：现有误区诊断都是「模式匹配 code → label」。但 du Boulay 的 notional machine 理论说，学生的 bug 源于他心里的**执行模型**与真实解释器有系统性偏差。把这个偏差**形式化**为对 Python 语义的一组可参数化「扰动算子」\(\delta\)，例如：
- \(\delta_{\text{range}}\)：range 右闭（`range(a,b)` 含 b）
- \(\delta_{\text{ret}}\)：`print` 等价于 `return`
- \(\delta_{\text{inplace}}\)：`append` 返回新列表
- \(\delta_{\text{idx}}\)：`for x in xs` 中 x 绑定为下标

给定学生代码 \(c\) 和他期望的输出 \(o_{\text{exp}}\)，求解

\[
\hat{\delta} = \arg\max_{\delta \in \Delta}\; P\big(o_{\text{exp}} \mid \text{eval}_\delta(c)\big)
\]

即：哪一台被扰动的解释器 \(\text{eval}_\delta\) 跑出来的结果最接近学生**以为**会得到的结果。这把「诊断」从分类问题变成**程序语义反演/搜索问题**。

**为什么新**：目前 CS 教育 + LLM 的论文几乎都停在「LLM 猜误区」或「规则匹配」。把 notional machine 做成**可执行的扰动解释器并做反演推断**，是 neuro-symbolic + 认知建模的交叉，据我所知没有直接先例。它天然可解释（输出的是一个语义算子，不是黑箱标签），且能**预测**学生在**新代码**上会犯什么错（用 \(\hat\delta\) 前向模拟）——这是分类器做不到的。

**方法骨架**：
1. 用 Python `ast` + 一个可插拔的解释器（如基于 `sys.settrace` 或自建 mini-interpreter）实现每个 \(\delta\) 算子。
2. 学生「期望输出」的获取：从对话里学生说的「我以为会打印 X」抽取，或从他修改前后的代码 diff 推断。
3. 反演搜索：\(\Delta\) 规模小（8-15 个算子 + 组合），可穷举或贪心。
4. 评测：与人工标注的误区标签比 Cohen's κ；关键新指标——**前向预测准确率**（用 \(\hat\delta\) 预测该学生下一段代码的错误类型，看命中率）。

**数据**：真实学生提交序列（含期望输出/困惑描述）。可先在 50-100 名学生上做。
**会议**：ICER / SIGCSE（CS 教育顶会，偏好这种有理论根基的）；neuro-symbolic 角度可投 AIED。
**风险**：期望输出难获取——需在 UI 里引导学生填「你以为会输出什么」（顺便是很好的教学干预）。可行性中等，新颖性极高。

---

## R2. AST 可验证的 LLM 解释：一个「解释忠实度」基准与协议

**研究问题**：LLM 生成的误区解释**有多少是它真在代码里看到的，有多少是幻觉**？能否用符号化 AST 证据**自动验证**解释的忠实度？

**新颖点**：你的系统已经有对称的双通道——`ast_features`（符号证据，如「第 3 行 Assign←Call←append」）和 LLM 自然语言解释。把二者组成一个**两阶段协议**：LLM 提议误区 → AST 验证器核对证据是否真实存在 → 不一致则驳回或标记。由此可定义一个新指标：

\[
\text{Faithfulness} = \frac{\#\{\text{LLM 解释中被 AST 证据支持的断言}\}}{\#\{\text{LLM 解释中的全部可验证断言}\}}
\]

**为什么值得做**：LLM-as-tutor 的幻觉在教育场景危害极大（教错学生比不教更糟），但目前**没有针对「代码误区解释」的忠实度基准**。你可以贡献：(1) 一个数据集，每条 = (code, 误区标签, AST 符号证据, LLM 解释, 人工忠实度标注)；(2) 一个自动忠实度评测器；(3) 证明「AST-grounded 解释」比「纯 LLM 解释」忠实度显著更高的对照实验。

**方法**：把 LLM 解释解析成断言（「第 N 行的 append 返回 None」），逐条去 AST features 里核验。可用另一个 LLM 做断言抽取 + 符号规则做核验。
**会议**：EMNLP/ACL（NLP 可解释性 track）或 AIED；数据集论文也可投 NeurIPS Datasets & Benchmarks。
**风险**：低。这个方向最容易落地成一篇扎实的实证论文，因为你已有两个通道的数据。**推荐作为第一篇**。

---

## R3. 误区知识追踪（MKT）：以「误区」而非「技能」为潜变量的结构化知识追踪

**研究问题**：能否把 BKT/DKT 从「追踪技能掌握」改造成「追踪误区的产生与消退」，并让潜变量之间带**因果/依赖结构**？

**新颖点**：标准 BKT 每个技能一个独立二态 HMM。但误区不独立——你的数据可挖出「有 M3 的学生更可能有 M6」（共享根因：函数执行后结果留在某处）。把误区依赖图 \(G\) 作为**结构先验**注入知识追踪：某误区被纠正会降低其**图上邻居**误区的先验概率。形式上是一个**带图结构的动态贝叶斯网络**。

对某误区 \(m\)，观测 \(x_t\)（本次是否命中），标准 BKT 更新：

\[
P(m\text{ 未掌握}\mid x_t) = \frac{P(x_t\mid \cdot)\,P(m\text{ 未掌握})}{P(x_t)}
\]

改造点：先验 \(P(m\text{ 未掌握})\) 不再固定，而是 \(f(\text{邻居误区状态}, G)\)。

**为什么新**：知识追踪文献里以「误区」为潜变量的极少，带**数据挖掘出的误区依赖图**做结构先验的更少。这把「误区因果链挖掘」和「知识追踪」两个方向缝合成一个模型。可解释性远好于 DKT（这也契合你项目的定位）。

**方法**：先关联规则（FP-growth）从 `MisconceptionEvent` 序列挖 \(G\)；再拟合结构化 BKT；对比独立 BKT / DKT 的**下一次误区预测 AUC**。
**会议**：LAK（学习分析顶会，最对口）/ EDM。
**风险**：需要一定量纵向数据（建议 ≥ 数千条误区事件）。中等可行性。

---

## R4. 把提示等级选择建模为离线强化学习：优化「长期独立解题」而非「即时解决」

**研究问题**：当前策略随失败次数**增加**帮助；但支架理论的核心是 fading（随能力**撤除**帮助）。能否从历史日志里**离线**学出一个提示策略，最大化学生的**长期迁移**（在无提示的新题上独立成功）？

**新颖点 + 方法**：把每次 tutoring 交互看成 contextual bandit / 离线 RL：
- 状态 \(s_t\) = 学生画像 + 当前误区 + 历史 hint 序列；
- 动作 \(a_t\) = 给的 hint level（1-5）；
- 奖励 \(r\) = **延迟奖励**：后续在**无提示**题目上的独立成功（而非当场解决）。

用**off-policy evaluation**（如 doubly-robust estimator）从已记录的 tutoring 日志评估新策略，无需在线实验就能估计「一个更倾向 fading 的策略」是否提升长期成果。这直接回答了你 5 级设计**能否证伪自己**的问题。

**为什么新**：ITS 里用 RL 调策略有先例（如 Cognitive Tutor），但**用离线 RL + 反事实评估**优化 LLM tutor 的 fading 策略、且奖励定义为**迁移而非即时解决**，是较新的组合。

**方法**：先补埋点 `(state, hint_level, 下一独立题是否成功)`；离线 RL（CQL/BCQ）或先做更稳的 contextual bandit + DR-OPE。
**会议**：AIED / EDM；方法侧可投 RL workshop。
**风险**：奖励信号稀疏、需要「无提示对照题」的埋点设计。可行性中等，理论卖点强。

---

## R5. 最小语义编辑作为「误区距离」：把程序修复用于诊断与提示生成

**研究问题**：给定学生 buggy 代码 \(c\)，求两个最小编辑——(a) 修好它的最小编辑 \(e_{\text{fix}}\)；(b) 从正确版本**复现**该误区的最小编辑 \(e_{\text{bug}}\)。用编辑的**语义距离**度量误区严重度，并据此生成**精确定位**的提示。

**新颖点**：把 program repair / minimal counterfactual 引入误区教学。\(e_{\text{fix}}\) 天然是「最该改的那一行」，比启发式 hint 定位精确；\(e_{\text{fix}}\) 与 \(e_{\text{bug}}\) 的对称性给出一个可量化的**误区距离**，可用于难度排序和迁移评估（在概念 A 学会后，概念 B 上同构误区的 \(e_{\text{bug}}\) 是否变小 = 迁移发生）。

**方法**：约束式 AST 编辑搜索（编辑脚本最小化）+ 用沙箱执行验证「修好/复现」。距离可用编辑脚本长度 + AST 树编辑距离。
**会议**：ICER / SIGCSE；program-repair 角度可投软件工程教育 track。
**风险**：搜索空间控制。中等可行性，工程量偏大。

---

## R6.【探索性】过程数据早期预警：提交前用编辑/运行时序检测「卡壳」

**研究问题**：能否在学生**提交之前**，从 Monaco 编辑器的击键/删除/运行时序中，用变点检测（change-point detection）**提前**识别学习困难并主动介入？

**新颖点**：多数系统在**提交后**才诊断。把「长停顿 + 反复删除重写 + 高频无变化运行」建模为困难的时序信号，做在线变点检测，实现**主动**而非被动的 tutoring。

**方法**：前端埋点编辑事件流；离线先做「困难 vs 顺利」会话的时序特征分析，再上轻量在线检测器。
**会议**：LAK（多模态学习分析正当红）。
**风险**：隐私与埋点成本高；建议作为后续工作而非首篇。

---

## 组合建议

- **第一篇（低风险、快出）**：R2（AST 可验证解释 + 忠实度基准）——你已有全部数据通道，改造小，实证扎实。
- **旗舰篇（高新颖、值得投入）**：R1（notional machine 反演）——理论根基 + neuro-symbolic + 可预测性，是能立住的差异化贡献。
- **数据积累后**：R3（误区知识追踪）和 R4（离线 RL fading 策略）依赖纵向数据，边收集边做。

R1 与 R2 天然互补：R1 产出「可执行的误区语义算子」，正好能当 R2 里 AST 验证器的**语义级证据**（不只是语法结构，而是「按这个扰动跑真会得到学生以为的结果」），两者可以合成一个更强的系统性工作。

---

*需要的话，我可以把 F1–F10 里任意一项展开成更细的实现级伪代码 + 完整测试用例清单；或把 R1/R2 展开成一页 research proposal（含 baseline、指标、实验设计）。*
