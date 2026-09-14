# B 方向：AST 代码结构分析 —— 实现说明

> 负责人：连哥（B 组） | 整合：2026-09 | 状态：完成并通过验收

---

## 1. 是什么

用 Python `ast` 模块解析学生代码，提取语法树结构，替代原先的纯正则匹配来诊断 8 类初学者误区（M1-M8）。通过 Feature Flag `ENABLE_AST_DIAGNOSIS` 控制开关，默认关。

## 2. 模块结构

```
backend/app/analysis/
├── __init__.py         # 模块入口
├── ast_analyzer.py     # AST 核心编排器（safe_parse + Visitor 调度 + M1/M2 正则 fallback）
├── ast_visitors.py     # 8 个 NodeVisitor（M3-M8 检测器，约 930 行）
├── confidence.py       # 置信度计算（多通道证据加权）
├── error_class.py      # 第 1 层错误大类（E-FR-02，beyond_misconception 归入画像）
└── root_cause.py       # 根因分析
```

集成点：`services/misconception_service.py` 的 `diagnose()` 顶部按 `ENABLE_AST_DIAGNOSIS` 分支到 `_ast_diagnose()`。

## 3. 最终指标（2026-09 实测，ast-only 模式）

| 指标 | 目标（MASTER-PLAN） | 实测 |
|------|------|------|
| Exact Match | ≥ 90% | **100.0%**（47/47） |
| Macro F1 | ≥ 0.88 | **1.000** |
| 误报率 | ≤ 8% | **0.0%**（0/22 干净代码） |

8 类误区 M1-M8 全部 Precision=1.0、Recall=1.0、F1=1.0。

## 4. 整合时修复的问题

| # | 问题 | 修复 |
|---|------|------|
| 1 | C39（`a='hello'; b=123; c=a+b`）漏判 M7 | `_is_likely_int` 类型映射不一致：`_scan_assignments` 存 `"num"` 但检查 `"int"`。改为接受 `("int","num")` |
| 2 | C17（`range(0,10,2)` 正确代码）误标 M5 | 移至 clean_code_cases.json（CLEAN21），正确返回 None |
| 3 | C41（`pop()` 有返回值，正确代码）误标 M3 | 移至 clean_code_cases.json（CLEAN22），正确返回 None |
| 4 | C13（for+break 被标 M8，无 while 循环） | 移除：代码无 M1-M8 范畴的明确误区 |

## 5. 测试

- `backend/tests/test_ast_analyzer.py`：48 单元测试
- `backend/tests/test_ast_adversarial_v31.py`：26 对抗性负例测试
- `evaluation/run_v2_eval.py --mode ast-only`：离线评测（47 正例 + 22 干净代码）

## 6. 已知限制

| 问题 | 原因 | 说明 |
|------|------|------|
| M4 dict 遍历误判 | AST 无运行时容器类型信息 | 已通过 `_collect_dict_vars` 从宽豁免，宁可漏报不可误伤 |
| M5 是意图型误区 | 需 stderr/学生提问外部信号 | 结构信号 + 提问信号门控，二者至少其一 |
