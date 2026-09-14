# Debug 日志 — B 方向 AST 诊断对抗性审查

> 日期：2026-07-09
> 方向：B（数据结构 / AST）+ 横切（chat 时序）
> 负责人：外部审查（Claude）
> 关联：SRS 3.1 §3（B 方向修订）、§9 追溯矩阵 F2/F5/Q11

## 1. 问题现象

在 v3.0 已宣称修复 F5.1–F5.4 四类假阳性的实现之上，用**独立构造**（非照
visitor 反向构造）的对抗负例重跑 AST 诊断，复现出三簇**新的、原有 48 项
测试未覆盖**的假阳性，以及一处 chat 层的策略时序缺陷：

| 簇 | 触发代码 | 错误诊断 | 应为 |
|---|---|---|---|
| B-1 M8 | `while len(s) > 0: s.pop()` | M8@0.65 | clean |
| B-1 M8 | `while count < len(x): count += 1` | M8@0.65 | clean |
| B-2 M4 | `d = get(); for k in d: d[k]`（get 返回 dict） | M4@0.90 | clean |
| B-2 M4 | `def f(d): for k in d: d[k]`（dict 形参） | M4@0.90 | clean |
| B-2 M4 | `d = {k:1 for k in ...}; for k in d: d[k]` | M4@0.90 | clean |
| B-3 M6 | `def menu(): print(...)` / `def main(): ...` | M6@0.88 | clean |
| X F2 | chat 记录误区事件在查历史之前 | 首次即 has_history=True | 首次 has_history=False |

## 2. 复现步骤

```bash
# 用最小 shim（structlog/pytest）离线跑，仅依赖 stdlib ast
python research/../adversarial_probe.py   # 见报告附带脚本
# 关键断言：以下 clean 代码不得产生任何 finding
#   while len(s)>0: s.pop()
#   d=get(); for k in d: d[k]
#   def menu(): print('x')
```

## 3. 根因分析

### B-1（M8 len() 假阳性）
`_extract_condition_vars` 用 `ast.walk` 收集条件里的所有 `Name`，把
`len(s)` 里的 **`len`** 也当成"状态变量"。`len` 永远不会被"更新"，于是
`unchanged = {len}` 非空 → 误报无限循环。第二个变体
`while count < len(x)` 里，`count` 会更新但 `x`（len 的实参）不会，旧逻辑
"任一变量未更新即报"，仍误报。

### B-2（M4 dict 来源不全）
`_collect_dict_vars` 只认 `{...}` 字面量与 `dict()` 调用，**不认**字典推导式
（`ast.DictComp`）、返回 dict 的函数、dict 形参、`d: dict` 注解。这些合法
字典遍历的 iter 名不在 dict_vars 里，于是 `for k in d: d[k]` 命中
value-as-index 模式误报 M4。根因：豁免集合的证据来源不完整。

### B-3（M6 展示函数假阳性）
M6 场景 1 判据是"有 print 且无 return"，这对**任何**展示/入口函数都成立
（`menu`/`main`/`show`）。这是典型"高敏感低精确"——正是研究计划里引用的
"GPT 检测错误心智模型 Precision 0.24"同型问题：判据太弱。

### X（F2 时序）
`chat_service.py` 步骤 4.5 在诊断出误区后**立即** `record_misconception_event`，
而 `get_misconception_history_count` 在步骤 5 才调用。结果：查询历史时**本次
已入表**，`prior_count ≥ 1`，`has_history` 恒为 True，`attempt_count` 多计 1。
B-FR-13 想要的"首次→progressive_hint"分支被反向短路（这次是"永远当成有
历史"）。根因：写事件与读历史的先后颠倒。

## 4. 尝试过的方案

| 方案 | 结果 | 结论 |
|---|---|---|
| B-1：给 len() 特判 | 可行但脆 | 改为通用"排除 Call.func 位置的名字 + 内置白名单"，更稳 |
| B-1 场景2：逐变量判 | 仍误报 count<len(x) | 改为"任一条件变量被更新即豁免"（假阴性优先） |
| B-2：只补 DictComp | 覆盖不全 | 补齐推导式/函数返回/形参/注解四来源 + 形参名启发式 |
| B-3：直接删场景1 | 漏报真 M6 | 改为"计算意图护栏"：需 print 算出的变量/表达式，或计算型函数名，且豁免展示名单 |

## 5. 最终修复

- `ast_analyzer._collect_dict_vars`：扩展为识别 dict 字面量/推导式/`dict()`/
  返回 dict 的函数/`d: dict` 注解/dict 形参名启发式（新增 `_expr_is_dict`、
  `_annotation_is_dict`、`_param_name_looks_dict`）。
- `ast_visitors.M8WhileInfiniteVisitor._extract_condition_vars`：排除处于
  `Call.func` 位置的名字与内置函数白名单（`len`/`range`/... ）。
- `ast_visitors` M8 场景 2：`any(cond_vars & modified_vars)` 为真即豁免。
- `ast_visitors.M6PrintReturnVisitor`：新增 `_looks_like_computation`，
  场景 1 仅在有计算意图证据时触发，展示/入口函数名一律豁免。
- `chat_service.py`：把 `record_misconception_event` 从步骤 4.5 移到
  `get_misconception_history_count` + `select_strategy` **之后**。

## 6. 防回归测试

新增 `tests/test_ast_adversarial_v31.py`（26 例：16 硬负例 + 10 真阳性回归）。

```bash
pytest backend/tests/test_ast_analyzer.py \
       backend/tests/test_ast_adversarial_v31.py -v
# 结果：原有 48 全过（无回归）+ 对抗 26 全过（假阳性消除）
```

`select_strategy` 时序断言：prior=0→progressive_hint；prior≥2→concept_explanation。

## 7. 遗留风险

- dict 形参名启发式（`d`/`_map`/`counts`...）是弱信号，可能**漏报**极少数
  真 M4（形参恰好叫 `d` 但其实是 list）。按"假阳性代价更高"取舍，接受。
- M6 计算型函数名单是启发式，非详尽；`compute_and_show()` 这类混合命名可能
  漏判。可后续用真实数据校准。
- 评测集分布泄漏（Q11）**未在本次根治**：`v2_eval_results.json` 的 0.96/0.974
  仍建立在照 visitor 构造的样本上，需按 B-EVAL-05~08 引入独立来源的对抗集
  后重测——本次的 `test_ast_adversarial_v31.py` 是这一重建的第一批种子。
