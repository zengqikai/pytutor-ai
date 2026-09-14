# C 方向 Task 3：画像时间衰减 + 转移矩阵 — 实现文档

## 概述

解决两个核心问题：
1. **时间衰减**：弱项 severity 随时间指数衰减，防止"3 周前的错误"永久标记为弱项
2. **知识转移矩阵**：追踪知识点间掌握转移，预测"学好 A 后 B 是否也会提高"

**目标指标**：弱项识别准确率 ≥ 70%（推荐应复习的知识点后，学生续错的概率）

## 1. 时间衰减

### 模型

采用 Ebbinghaus 遗忘曲线的指数衰减模型：

```
severity_t = severity_0 × e^(-λ × t)
λ = ln(2) / HALF_LIFE
```

- 半衰期 7 天：7 天后 severity 降低一半
- 下限 0.1：彻底遗忘 ≠ 从未犯错
- 对弱项列表全部应用后重新排序

### 效果示例

| 场景 | 原始 severity | 天数 | 衰减后 severity |
|------|:-----------:|:----:|:-------------:|
| 刚才 | 5 | 0 | 5.0 |
| 3 天前 | 5 | 3 | 3.71 |
| 1 周前 | 5 | 7 | 2.5 |
| 2 周前 | 5 | 14 | 1.25 |

## 2. 知识转移矩阵

### 状态定义

| 状态 | 掌握度范围 | 中心值 |
|------|:-------:|:----:|
| weak (薄弱) | 0.0-0.3 | 0.15 |
| developing (发展中) | 0.3-0.6 | 0.45 |
| proficient (熟练) | 0.6-1.0 | 0.80 |

### 转移追踪

基于 `LearningEvent` 历史事件：
1. 按用户分组、按时间排序
2. 检测同一用户不同知识点间的状态同步变化
3. 记录 `from_concept → to_concept` 的"同向改善/恶化"

### 贝叶斯平滑

使用 Beta(α=1, β=1) 先验 (Laplace smoothing)：

```
P_smoothed = (count + α) / (total + α + β)
```

好处：小样本时偏向 0.5（不确定），大样本时接近真实比例。

### Cohen-like 效应量

相关性 = (p_improved - p_worsened) / √(p_pooled × (1-p_pooled))

返回 -1.0 到 1.0：正值 = 正向转移，0 = 无关系。

## 关键文件

| 文件 | 作用 |
|------|------|
| `backend/app/services/profile_decay_service.py` | 核心算法 (新建, ~400 行) |
| `backend/app/services/profile_service.py` | `get_weaknesses()` + `get_recommendation()` 接入 |
| `backend/app/core/config.py` | `ENABLE_TIME_DECAY` 开关 |

## 验收标准

- [x] 指数衰减公式正确：7 天 = 1 半衰期 = severity 减半
- [x] 弱项排序：最近的最优先
- [x] 转移矩阵贝叶斯平滑正确
- [x] 序列化/反序列化往返正确
- [x] 缓存 TTL 30 分钟
- [x] `ENABLE_TIME_DECAY=false` 时旧逻辑零改动
