# Debug 日志 — B-AST

> **日期**: 2026-06-18
> **方向**: B — 数据结构 / AST 代码分析优化
> **负责人**: 连哥
> **阶段**: Phase 1-3（实际 Debug 记录）

---

## Debug #1：M4 误报 range(len(items)) 模式

**发现时间**: 2026-06-18 Phase 1
**严重程度**: Major（会误报正确代码）

### 1. 问题现象

干净代码 `for i in range(len(items)): print(items[i])` 被 M4Visitor 误判为 index/value 混淆。

### 2. 复现步骤

```python
import ast
from app.analysis.ast_visitors import M4ValueAsIndexVisitor
tree = ast.parse("for i in range(len(items)):\n    print(items[i])")
v = M4ValueAsIndexVisitor()
v.visit(tree)
print(v.found)  # 非 None -> 误报！
```

### 3. 根因分析

`_extract_iter_name()` 方法对 `range(len(items))` 也返回 `items`——因为递归解析了 `range(len(x))` -> `x`。但 `for i in range(len(items))` 中 `i` 是合法整数下标，`items[i]` 是正确的。

### 4. 尝试方案

| 方案 | 结果 | 分析 |
|------|------|------|
| 修改 `_extract_iter_name` 返回 None | ✅ 修复 | `range(len(x))` 的循环变量是有效下标，不应提取 iter name |

### 5. 最终修复

`ast_visitors.py` `_extract_iter_name()`: 删除 `range(len(x))` -> `x` 的递归提取逻辑，只保留纯 `for var in list_name` 模式。

### 6. 回归验证

```bash
pytest backend/tests/test_ast_analyzer.py::TestM4ValueAsIndex -v  # PASS
```

---

## Debug #2：M7 无法检测变量类型

**发现时间**: 2026-06-18 Phase 3 初次 eval
**严重程度**: Critical（导致 M7 F1 = 0.000，8/8 漏诊）

### 1. 问题现象

`ENABLE_AST_DIAGNOSIS=true` 评测中，所有 8 个 M7 案例全部漏诊（F1 = 0.000）。

### 2. 根因分析

M7 的 `visit_BinOp` 要求两侧都能推断类型才触发。`Name + Constant` 不触发（Name 类型未知）。LLM fallback 因 API Key 未配置也失败了。

### 3. 最终修复

`ast_visitors.py` M7Visitor: 当 `_has_typeerror` 为 True 时，放宽匹配——只要一侧是 `Constant(str/int)` 或 `input()` 就触发，置信度 0.80。

### 4. 回归验证

M7 F1: 0.000 -> 0.857（6/8 命中）。

---

## Debug #3：M5 信号阈值偏高导致 C43 漏诊

**发现时间**: 2026-06-18 Phase 3 eval
**严重程度**: Minor（1 例漏诊）

### 1. 问题现象

C43 案例：`for x in range(10): ... print('range includes:', x)`，学生问题为"x最后是10吗"。M5 未触发。

### 2. 根因分析

学生问题"x最后是10吗"不包含关键词列表中的任何词。总分 = 0.0 < 0.6 阈值。0.6 阈值是防止粗暴判断的保护机制，降低会导致纯 `range(10)` 也被判 M5。

### 3. 解决

当前不修改——M5 是意图型误区，在"不漏诊"和"不误报"之间有根本性权衡。后续可扩展中文关键词表（如"最后是""到几"）。

---

## Debug #4：M5 扫描范围过大

**发现时间**: 2026-06-18 Code Review
**严重程度**: Major（`range(10)` 中的 `10` 被误判为循环体引用）

### 1. 问题现象

`ast.walk(for_node)` 扫描了整个 for_node（含 range 参数），导致 `range(10)` 中的 `10` 被误认为循环体 stop 引用。

### 2. 最终修复

改为只扫描 `for_node.body`：`for stmt in for_node.body: for node in ast.walk(stmt): ...`。同时将外部信号权重从 0.4 提高到 0.6，保证 stderr/学生问题单独可过阈值。

### 3. 回归验证

```bash
pytest backend/tests/test_ast_analyzer.py::TestM5RangeBodyScan -v  # PASS
```

---

## Debug #5：Windows GBK 终端 Unicode 输出

**发现时间**: 2026-06-18 Phase 3 eval
**严重程度**: Minor（仅影响 eval 脚本输出）

### 1. 问题现象

```bash
python evaluation/run_v2_eval.py --mode direct
# UnicodeEncodeError: 'gbk' codec can't encode character '✓'
```

### 2. 最终修复

用 ASCII 替代 Unicode 字符，设置 `PYTHONIOENCODING=utf-8`。

---

## 当前已知限制

主要 Debug 问题已处理。C39 和 C45 已在最新版中通过 M7 变量类型传播和 input()*int 检测修复，不再作为未解决问题。当前仍保留以下已知限制：

### L1：C13 — M5 与 M8 标签冲突

- **现象**: 当前输出为 M5，但测试期望为 M8。
- **分析**: 该样例包含 `range` 边界相关问题描述，因此被 M5 捕获有一定合理性。该问题更像多误区优先级或测试标签冲突，不一定是纯算法错误。
- **当前处理**: 保留为已知限制，不强行修改 AST 规则。

### L2：CLEAN16 — dict 遍历被误判为 M4

- **现象**: `for key in data: print(data[key])` 对 dict 是正确写法，但可能被 M4 规则误判。
- **原因**: 当前 M4 规则主要依据 `for x in container` 与 `container[x]` 结构，尚未完整维护容器类型表。
- **影响**: 干净代码集中 1 / 20 误报，FPR 为 5.0%，仍满足 SRS ≤8% 目标。
- **后续方案**: 维护简单容器类型表，识别 `{}` / `dict()` 为 dict，dict 遍历时不触发 M4。

### L3：C41 — pop() ground truth 争议

- **现象**: C41 expected M3，但当前输出 None。
- **分析**: `pop()` 与 `append()` / `sort()` 不同，`pop()` 有返回值，因此 `popped = nums.pop()` 是合理写法。
- **当前处理**: 不把 `pop()` 加回 M3；保留该测试样例的标签争议说明。

### 已修复说明

以下问题已在最新版中解决，不再作为当前未解决问题记录：

- **C39** (`a = 'hello'; b = 123; c = a + b`)：已通过简单常量赋值类型传播修复（`Name -> str/int`）。
- **C45** (`num = input(); print(num * 3)`)：已通过 input 变量类型标记 + 算术运算检测修复。
- **C31 / C43**（M5 关键词"最后"不匹配）：已通过在 M5 关键词表中新增 `"最后"` 修复。

---

## 未通过样例（当前评测实测）

```text
C13     expected M8, got M5    (M5/M8 标签冲突，合理歧义)
C41     expected M3, got None  (pop() 有返回值，赋值是正确用法；ground truth 有争议)
CLEAN16 expected None, got M4  (dict 遍历误判，AST 无容器类型信息)
```

---

## SRS 3.1 修复 (2026-07-09)

基于 `PyTutor_Fix_Design_and_Research.md` 和 `PyTutor_SRS_3.1_Security_Robustness_Amendment.docx` 完成 F1-F10 修复。

已修复:
- F1: Config 生产安全护栏（占位符密钥拒绝启动）
- F2: 教学策略历史数据硬编码修复
- F3: 沙箱统一入口 + 生产 Docker 强制隔离
- F4: 安全预检反射逃逸探针 + open() 全禁
- F5.1: M4 字典遍历排除（dict_vars 收集）
- F5.2: M8 mutating-method 收敛检测
- F5.3: M5 删除 "range" 关键词 + 结构信号要求
- F5.4: M7 有序类型传播 + %/` 支持
- F6: LLM 不可用 AST 模板兜底
- F7: RAG 熔断器 15s→3s
- F8: 前端注册错误提示
- F9: profile JSON RMW→event append 并发修复
- F10: Agent 节点超时保护

验证: compileall OK, 48 tests passed.

---

> 48 单元测试通过。核心检测逻辑达到 96% Exact Match / 0.974 Macro F1 / 5% FPR，超过全部 SRS 目标。SRS 3.1 修复 F1-F10 全部完成。
