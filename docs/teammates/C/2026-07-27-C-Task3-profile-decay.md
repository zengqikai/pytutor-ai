# C 方向 Task 3：画像时间衰减 + 转移矩阵 — 实现日志

## 2026-07-27 完成实现

### 完成内容

1. **`profile_decay_service.py`** (新建, ~430 行)
   - `compute_decayed_severity()`: 单弱项指数衰减
   - `decay_all_weaknesses()`: 批量衰减 + 重排序
   - `TransitionMatrix` 类: 完整转移矩阵实现
     - `record_transition()`: 记录跨概念转移
     - `get_correlation()`: 贝叶斯平滑 Cohen-like 效应量
     - `get_related_concepts()`: 发现相关概念
     - `predict_weakness_risk()`: 预测风险概念
     - `to_dict()` / `from_dict()`: 序列化往返
   - `build_transition_matrix()`: 从 LearningEvent 构建矩阵
   - `compute_weakness_prediction_accuracy()`: 弱项推荐命中率
   - `TRANSITION_MATRIX_CACHE`: TTL 30 分钟进程内缓存

2. **`profile_service.py` 集成**
   - `get_weaknesses()`: 当 ENABLE_TIME_DECAY=true 时自动衰减 + 重排序
   - `get_recommendation()`: 衰减后 severity < 1.5 跳过复习推荐 + 转移矩阵风险警告

### 设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 衰减模型 | 指数衰减 | Ebbinghaus 遗忘曲线，简单且效果最好 |
| 半衰期 | 7 天 | 编程技能遗忘曲线适中 |
| 衰减下限 | 0.1 | 防止完全归零（"犯过错"有价值） |
| 转移矩阵先验 | Beta(1,1) | Laplace 平滑，小样本保守 |
| 相关性效应量 | Cohen-like | 同时考虑方向和强度 |
| 缓存策略 | TTL 30min | 历史事件变化慢，无需实时 |

### 验证结果

- ✅ 指数衰减：7天 = 半衰期正确，14天 = 2半衰期
- ✅ 弱项排序：最新优先（function > list > for_loop）
- ✅ 转移矩阵：贝叶斯平滑正确，序列化往返一致
- ✅ 缓存：TTL 检查正常工作
- ✅ ENABLE_TIME_DECAY=false 时旧逻辑零改动

### 已知限制

1. **转移矩阵构建需要历史数据**：新项目无历史时矩阵为空，不影响降级路径
2. **仅基于 event_type 判定转移**：精细化需要概念掌握度数值（concept_mastery_json）
3. **未更新 concept_mastery_json**：当前衰减仅应用于弱项 severity，未驱动画像中的 mastery 值更新
