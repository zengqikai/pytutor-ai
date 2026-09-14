# B-AST 实现文档 · v3.2 增补（对抗性审查修复）

> 本文是对 `docs/implementation/B-AST-implementation.md` 的增补，只记录 2026-07-09
> 对抗性审查新发现的三簇假阳性 + F2 时序缺陷的算法设计、伪代码与评测方法。
> 背景/baseline/原有 M1–M8 设计见主实现文档，不重复。

## 1. 背景问题

v3.0 已实现 F5.1–F5.4（M4 字典豁免、M8 pop 豁免、M5 去循环论证、M7 顺序类型
推断），且这些修复经独立复核确实生效、无回归。但同一套 visitor 在**独立构造**
的对抗负例上仍暴露三簇系统性假阳性，且原有 48 项测试全部覆盖不到：

1. **M8 · len()/函数包裹条件**：F5.2 的 pop 豁免只处理「条件变量作为方法调用
   接收者」，未处理「条件被 len() 等函数包裹」。`while len(s)>0: s.pop()` 里
   `_extract_condition_vars` 把 `len` 当状态变量，永远"未更新"→ 误报。
2. **M4 · 非字面量 dict**：F5.1 的 dict 豁免集合只认 `{...}`/`dict()`，漏掉
   推导式、返回 dict 的函数、dict 形参、`d: dict` 注解。
3. **M6 · 展示函数**：从未被 F5 触及。判据「有 print 无 return」对任何
   `menu`/`main`/`show` 都成立 → 高敏感低精确。

外加横切缺陷 **F2 时序**：`chat_service` 在查历史前就记录了本次误区事件，
使 `has_history` 恒真，B-FR-13 的首次分支不可达（3.1 修了 has_history 取真值，
但没修写/读顺序）。

## 2. 方案设计

### 2.1 M8 条件变量提取（B-FR-14 / B-FR-15）

设计原则：**条件里"真正需要在体内收敛的状态变量"**，不包括被调用的函数名。

```
def _extract_condition_vars(test):
    callee = { n.func.id for n in walk(test)
               if n is Call and n.func is Name }        # len/range/... 被调用的名字
    ignore = {内置函数白名单} ∪ {True,False,None}
    return { name(n) for n in walk(test) if n is Name
             and n.id not in callee and n.id not in ignore }
```

场景 2 判据从「存在任一未更新变量即报」改为「**所有**条件变量都没被动过才报」
（假阴性优先）：

```
modified = _extract_modified_vars(while)          # 已含 Assign/AugAssign/For/方法接收者
if (cond_vars - modified) and not (cond_vars & modified):   # 全部未动才可疑
    ...报 M8...
```

这样 `while count<len(x): count+=1`（count 被动）、`while len(s): s.pop()`
（s 被动，且 len 已被排除出条件变量）都豁免；`while i<10: print(i)`
（i,i 都没动）仍报。

### 2.2 M4 dict 来源扩展（B-FR-16）

`_collect_dict_vars` 两遍扫描：

```
Pass1: 收集"返回 dict 字面量/推导式/dict() 的函数名" dict_funcs
Pass2: 对每个赋值/注解/形参：
  d = {…} | {k:v for…} | dict(…)            → dict_var
  d = f()  且 f ∈ dict_funcs                 → dict_var
  d: dict / d: Dict[…]                       → dict_var
  形参名像 dict（d/_map/counts/…）或带 dict 注解 → dict_var
```

判据函数 `_expr_is_dict` / `_annotation_is_dict` / `_param_name_looks_dict`。
形参名启发式是**弱信号且仅用于豁免**——宁可漏一个真 M4，不误伤写对的字典遍历。

### 2.3 M6 计算意图护栏（B-FR-17）

场景 1 只在有「计算意图证据」时才报：

```
printed_computed_value = print 的实参 ∈ {本函数赋过值的变量, BinOp 表达式}
looks_like_computation(name):
    if name ∈ 展示/入口名单(main,menu,show,display,render,draw,…): return False
    if name 以 print_/show_/display_ 开头: return False
    if printed_computed_value: return True          # 结构强证据
    return name ∈ 计算型名单(add,calc,get,sum,…)     # 命名弱证据
```

置信度：有结构证据 0.85，仅命名证据 0.70。场景 2（return 后不可达 print）不变。

### 2.4 F2 时序（B-FR-18）

`chat_service.handle_chat` 调用顺序改为：

```
诊断误区 → (查历史 get_misconception_history_count) → select_strategy
        → 生成回复 → record_misconception_event（延后到这里）
```

即"先读后写"，保证 `prior_count`/`has_history` 反映的是"本次之前"。

## 3. 改动文件与 Feature Flag

| 文件 | 改动 |
|---|---|
| analysis/ast_analyzer.py | `_collect_dict_vars` 扩展 + 三个判据函数 |
| analysis/ast_visitors.py | M8 条件/场景2、M6 护栏 + `_looks_like_computation` |
| services/chat_service.py | 事件记录延后 |

均在 `ENABLE_AST_DIAGNOSIS` 开关下（B 方向诊断本就受此开关控制）；时序修复
属于 chat 主链路，随开关生效。安全性不受影响（不触碰 D 方向）。

## 4. 评测方法

- 回归：`test_ast_analyzer.py`（48 例）必须全过。
- 对抗：`test_ast_adversarial_v31.py`（26 例 = 16 硬负例 + 10 真阳性回归）。
- 时序：断言 prior=0→progressive_hint，prior≥2→concept_explanation。

## 5. 结果对比

| 项 | 修复前 | 修复后 |
|---|---|---|
| 原有 48 测试 | 48/48 | 48/48（0 回归） |
| M8 len/收敛循环假阳性 | 复现 | 0 |
| M4 非字面量 dict 假阳性 | 复现 | 0 |
| M6 展示函数假阳性 | 复现 | 0 |
| B-FR-13 首次分支 | 不可达 | 可达 |

## 6. 已知问题与后续 TODO

- 形参名/函数名启发式非详尽，需真实数据校准（漏报风险，非误报风险）。
- `v2_eval_results.json` 仍是泄漏分布旧值，需按 B-EVAL-09~11 用独立对抗集重测。
- 建议把这 26 例对抗测试纳入 CI（`.github/workflows/ci.yml`），与 D-FR-12 合并。
