# C 方向 Task 1：Multi-Judge 评分系统 — 实现文档

## 概述

将 AI 教学回复质量评估从「单次 LLM 评分」升级为「3 评委独立评分 + 中位数聚合」，提升评分一致性和可靠性。

**目标指标**：回复评分 Cohen's Kappa ≥ 0.80（vs 人工 30 例）

## 文献依据

| 文献 | 关键发现 | 本实现采纳 |
|------|---------|-----------|
| Shi et al. (2025) | Rubric 驱动评估可达 Kappa 0.75 | 5 维 × 5 级详细 Rubric |
| Acharya et al. (2026) RoPoLL | 几何中位数优于算术平均 (breakdown 1/2) | 中位数聚合 |
| Zheng et al. (2024) MT-Bench | 同模型家族 self-enhancement bias 10-25pts | 同模型不同 temperature |
| Rao & Callison-Burch (2026) | Kappa 唯一能捕获边缘分布偏移 | 报告 Fleiss' Kappa |
| Ahtisham et al. (2026) LAK | Cross-verification 提升 κ 37% | 3 评委并发调用 |

## 架构设计

```
verify_response()  [pedagogy_service.py]
    │
    ├── ENABLE_MULTI_JUDGE=false (默认) → 单评委 (原逻辑)
    │
    └── ENABLE_MULTI_JUDGE=true → multi_judge_verify() [judge_service.py]
                                      │
                          ┌───────────┼───────────┐
                     Judge 0       Judge 1       Judge 2
                   (temp=0.1)    (temp=0.5)    (temp=0.9)
                          │            │            │
                          └────────────┼────────────┘
                                       │
                              _aggregate_verdicts()
                                  │ 中位数聚合
                                  │ Fleiss' Kappa
                                  │ 分歧检测 (>1级→标记)
                                       │
                                  MultiJudgeResult
```

## 5 维 Rubric 设计

| 维度 | 名称 | 评 1-5 分 | 对齐 PyTutor 概念 |
|------|------|-----------|------------------|
| D1 | Hint Level Adherence | 提示等级遵循度 | 5 级渐进提示体系 |
| D2 | Beginner Appropriateness | 初学者适配度 | 项目定位：中文初学者 |
| D3 | No Answer Leakage | 无答案泄露 | 禁止首次给答案原则 |
| D4 | Misconception Targeting | 误区针对性 | M1-M8 误区诊断 |
| D5 | Actionability | 可操作性 | 下一步操作建议 |

## 关键文件

| 文件 | 作用 |
|------|------|
| `backend/app/services/judge_service.py` | Multi-Judge 核心实现 (新增) |
| `backend/app/services/pedagogy_service.py` | `verify_response()` 增加开关路由 |
| `backend/app/core/config.py` | 新增 `ENABLE_MULTI_JUDGE` 开关 |
| `evaluation/run_judge_eval.py` | Multi-Judge 评估脚本 (新增) |

## 验收标准

- [ ] `ENABLE_MULTI_JUDGE=false` 时旧逻辑完全不受影响
- [ ] `ENABLE_MULTI_JUDGE=true` 时 3 评委并发评分
- [ ] 评委间 Fleiss' Kappa ≥ 0.60 (10 例内置测试)
- [ ] 分歧 >1 级的 case 被正确标记 `flagged=True`
- [ ] 不影响 tutor_service.py 中的现有调用方
