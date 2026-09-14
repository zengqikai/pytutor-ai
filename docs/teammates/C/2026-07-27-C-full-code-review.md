# C 方向 全量代码审查 — Debug 日志

## 2026-07-27 深度审查

### 发现的缺陷（6 个）

| # | 严重度 | 文件 | 行 | 问题 | 修复 |
|---|--------|------|----|------|------|
| 1 | 中 | `judge_service.py` | 250-257 | Few-shot 示例 1 自相矛盾: D3 给 5 分但回复里包含了 `range(1,6)` （等于告诉答案） | 重写示例 1 为 overall=4，去掉泄题内容，D3 降为 4 分 |
| 2 | 高 | `judge_service.py` | 771 | `is_valid` 用 OR 逻辑: `score >= 3 OR not needs_revision` — 即使多数评委要求修正也判断为 valid | 改为 AND: `score >= 3 AND not needs_revision` |
| 3 | 高 | `profile_decay_service.py` | 466 | `other_improved = (other_state == "fail" and other_state != other_state)` — `other_state != other_state` 永远是 False。死代码。| 删除死代码行，保留正确逻辑 `to_improved = (other_state == "pass")` |
| 4 | 中 | `profile_decay_service.py` | 510-520 | `since` 变量计算了但查询未加时间过滤 | 添加 `LearningEvent.created_at >= since` |
| 5 | 中 | `llm_service.py` | 200 | `"def " in user_message` 误匹配 `"define "`, `"import "` 误匹配 `"important "` | 改为正则 `\bdef\s+\w+\s*\(` 和 import 语法匹配 |
| 6 | 低 | `judge_service.py` | 45 | `Optional` 从 typing 导入但从未使用 | 移除未使用的导入 |

### 已验证的无缺陷项

- ✅ 6 个文件全部语法编译通过
- ✅ Fleiss' Kappa 计算公式正确（支持 CANNOT_ASSESS 第 6 类别）
- ✅ CANNOT_ASSESS 全维度时 median=None 而非造假分
- ✅ 单评委超时 30s 保护正确（asyncio.wait_for）
- ✅ 转移矩阵贝叶斯平滑正确
- ✅ 时间衰减指数公式正确（半衰期 7 天）
- ✅ Hint Dependency 分级阈值正确
- ✅ Content-Based 概念 Jaccard 相似度正确
- ✅ 多模型路由成本估算 53% savings 达标
- ✅ 3 个 Feature Flag 全部默认 off
- ✅ `record_event()` 代码完整（事件创建 + profile 更新 + hint dep）
- ✅ `get_weaknesses()` / `get_recommendation()` 签名不变
