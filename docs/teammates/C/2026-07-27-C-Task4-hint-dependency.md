# C 方向 Task 4：Hint Dependency 量化 — 实现日志

## 2026-07-27 完成实现

### 完成内容

1. **`compute_hint_dependency()`**: 基于实际数据计算依赖度
   - 核心公式: score = hints_total / (exercises_total + hints_total)
   - 范围 [0, 1]，有除法保护
   - 阈值: low < 0.25 / medium 0.25-0.50 / high > 0.50

2. **`compute_hint_dependency_trend()`**: 趋势判定
   - increasing: score 增加 > 5%
   - decreasing: score 减少 > 5%
   - stable: 变化 < 5%

3. **`update_hint_dependency()`**: 数据库更新
   - 从 `StudentProfile` 计数器实时计算
   - 自动对比上次值，输出趋势
   - 写入 `profile.hint_dependency` (JSON 格式: {score, label})

4. **`record_event()` 集成**
   - 每次 hint 事件后自动触发更新
   - 零 LLM 调用，纯计数器运算
   - 异常不影响主流程 (silent catch)

### 验证结果

- ✅ score 正确：2 hint + 20 exercise → 0.091 (low)
- ✅ 阈值正确：5+10 → medium, 15+10 → high
- ✅ 边界处理：0+0 → score=0, label=low
- ✅ 趋势：+30% → increasing, -30% → decreasing, +3% → stable
- ✅ record_event 集成完整

### 注意

- 不同于 Task 1-3，Task 4 无需 Feature Flag（纯计算，零成本）
- 旧 `hint_dependency` 字段从纯字符串升级为 JSON 存储，向后兼容（update 函数内部处理了降级解析）
