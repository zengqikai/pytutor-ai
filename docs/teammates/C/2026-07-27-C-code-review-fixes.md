# C 方向 Task 1-2 代码审查修复日志

## 审查日期: 2026-07-27

## 发现的缺陷与修复

### Fix 1: 未使用的 import + 缺失的顶层 import
- 文件: `judge_service.py` L43, L699
- 问题: `field` 从 dataclasses 导入但未使用；`asyncio` 在函数内部导入
- 修复: 移除 `field`，将 `import asyncio` 移至模块顶层
- 严重度: 低 (代码规范)

### Fix 2: 无评委超时保护
- 文件: `judge_service.py` L705
- 问题: `asyncio.gather` 无单评委超时，一个评委卡住拖死全部 3 个
- 修复: 每个评委用 `asyncio.wait_for(..., timeout=30s)` 包装，超时自动降级为 fallback verdict
- 新增常量: `JUDGE_TIMEOUT_SECONDS = 30.0`
- 严重度: **高** (可能导致生产服务卡死)

### Fix 3: 全部 CANNOT_ASSESS 时报假分
- 文件: `judge_service.py` L534
- 问题: 3 个评委一致标记 CANNOT_ASSESS 时 fallback 为 `median=3`，误导下游以为"及格"
- 修复: 全 CANNOT_ASSESS 时报 `median=None, note="all judges marked CANNOT_ASSESS"`
- 影响: `max_range` 计算需排除 None 值 → 已同步修复
- 严重度: 中 (数据误导)

### Fix 4: raw_json 截断可能切断 JSON 结构
- 文件: `judge_service.py` L452
- 问题: `raw[:400]` 在 CoT 推理链较长时可能切断 JSON 闭合括号，debug 困难
- 修复: 扩大为 `raw[:800]`
- 严重度: 低 (仅影响调试)

### Fix 5: evaluate_judge_agreement 串行执行
- 文件: `judge_service.py` L776-789
- 问题: N 个 case 串行跑，总延迟 = N × 单例延迟，10 例可能 30s+
- 修复: 用 `asyncio.gather` 并发执行全部 case
- 严重度: 低 (工具函数，非生产路径)

## 验证结果

- ✅ 6 个修复全部编译通过 + 功能验证
- ✅ `ENABLE_MULTI_JUDGE` 仍然默认 false
- ✅ 全 CANNOT_ASSESS → median=None 而非 3
- ✅ 超时包装器正确注入
- ✅ asyncio 移至顶层
