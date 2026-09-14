# C 方向 Task 2：Rubric 细化 — 实现日志

## 2026-07-27 完成实现

### 完成内容

1. **行为锚定 Rubric V2** (`JUDGE_RUBRIC_V2`)
   - 5 维 × 5 级，每级用可观测行为定义
   - 消除了 V1 中的模糊词：「基本遵循→具体可观测行为」「部分适合→术语数量+句子结构」
   - 特别对齐 PyTutor 5 级渐进提示体系（Level 1-5 各对应具体行为）

2. **Few-shot 校准示例** (`FEW_SHOT_EXAMPLES`)
   - 3 例：overall=5 (完美引导), overall=2 (越级给答案), overall=1 (敷衍)
   - 每例含完整的 5 维评分 + 证据引用
   - 选择策略：覆盖边界而非典型——教评委分值边界在哪

3. **Chain-of-Thought + 证据锚定**
   - 输出格式新增 `reasoning` 字段：每维 "证据→分析→分数"
   - JudgeVerdict 新增 `reasoning: dict[str,str]` 字段
   - max_tokens 从 300 提升至 600 以容纳推理链

4. **误区特定指导** (`PER_MC_GUIDANCE`)
   - M1-M8 每类有独立的教学质量评判标准
   - 基于 Phung et al. (2025) 发现：泛用 rubric 在 34.5% 案例中与学生感知不匹配
   - 每种 M 标注了"好教学"和"差教学"的具体标准

5. **CANNOT_ASSESS 支持**
   - 明确规则：回复<20字 或 与教学无关 → 填 0
   - Kappa 计算将 0 作为独立第 6 类别
   - 聚合时排除 0 分维度，但保留审计标记
   - MultiJudgeResult 新增 `cannot_assess_dims` 字段

6. **`_build_judge_prompt()` 函数**
   - 组装完整 prompt：Rubric + 误区指导 + Few-shot + 结尾提醒
   - 只在有对应误区 ID 时附加 PER_MC_GUIDANCE

### 数据结构变更

```python
# JudgeVerdict 新增 2 字段
reasoning: dict[str, str]    # 每维推理链
cannot_assess: list[str]     # CANNOT_ASSESS 的维度

# MultiJudgeResult 新增 1 字段
cannot_assess_dims: list[str] # 多评委一致的 CANNOT_ASSESS
```

### 验证结果

- ✅ V2 prompt 4923 chars，包含全部 4 项增强 + CANNOT_ASSESS
- ✅ JudgeVerdict 新字段 (reasoning, cannot_assess) 正常工作
- ✅ 完全一致 Kappa=1.0，CANNOT_ASSESS 正确处理
- ✅ 所有 Feature Flag 默认关，旧逻辑不受影响
- ✅ MultiJudgeResult 聚合排除 0 分维度

### V1 → V2 差异总结

| 指标 | V1 | V2 |
|------|----|----|
| Prompt 长度 | 1295 chars | 4923 chars |
| Rubric 描述 | 抽象等级 | 行为锚定 |
| Few-shot 示例 | 0 | 3 (高/中/低) |
| 推理解释 | 无 | CoT 400字推理链 |
| 证据锚定 | 无 | 每维必须引用原文 |
| 误区独立指导 | 无 | 8 类各 4-7 行 |
| CANNOT_ASSESS | 无 | 2 种场景 + 第 6 类别 |
| max_tokens | 300 | 600 |

### 下一步

- 需要实际 DeepSeek API key 来跑 `evaluation/run_judge_eval.py` 获取 Kappa/方差数据
- 可以考虑迭代 Few-shot 示例：若特定分值区间分歧大，替换该区间的校准例
- 建议攒 30 例人工标注来验证 judge-human Kappa
