# PyTutor C 方向：质量与系统优化 — 实现说明书

> **作者**: clt | **日期**: 2026-07-27 | **版本**: v1.0  
> **项目**: PyTutor AI 3.0 — 算法优化第二阶段

---

## 一、任务地图

```
C 方向 (质量与系统优化)
├── Task 1 ─ Multi-Judge 评分系统        [judge_service.py]
│   └── 3 评委并发评分 → 中位数聚合 → Kappa 一致性报告
│
├── Task 2 ─ Rubric 细化                 [同上]
│   └── 行为锚定 + Few-shot 校准 + CoT + 证据锚定 + 误区特定指导
│
├── Task 3 ─ 画像时间衰减 + 转移矩阵      [profile_decay_service.py]
│   ├── 弱项 severity 指数衰减 (半衰期 7 天)
│   └── 知识点转移矩阵 (贝叶斯平滑)
│
├── Task 4 ─ Hint Dependency 量化         [同上]
│   └── 纯计数器计算: score = hints/(exercises+hints)
│
├── Task 5 ─ Content-Based 练习推荐       [profile_service.py]
│   └── Jaccard 概念相似度 + 难度惩罚
│
└── Task 6 ─ 多模型路由                  [llm_service.py]
    └── 简单问题→chat(便宜) / 复杂问题→pro(强推理)
```

---

## 二、核心架构

```
┌─────────────────────────────────────────────────────────┐
│                   config.py (Feature Flags)              │
│  ENABLE_MULTI_JUDGE      ENABLE_TIME_DECAY               │
│  ENABLE_CONTENT_RECOMMEND  (全部默认 false)               │
└──────────────┬────────────────┬─────────────────────────┘
               │                │
    ┌──────────▼──────┐  ┌──────▼─────────────────────┐
    │ judge_service.py│  │ profile_decay_service.py    │
    │                 │  │                             │
    │ _single_judge() │  │ compute_decayed_severity()  │
    │ _aggregate_     │  │ decay_all_weaknesses()      │
    │   verdicts()    │  │ TransitionMatrix            │
    │ _compute_kappa()│  │ compute_hint_dependency()   │
    │ multi_judge_    │  │ update_hint_dependency()    │
    │   verify()      │  └──────────┬──────────────────┘
    └──────┬──────────┘             │
           │              ┌─────────▼──────────────────┐
    ┌──────▼──────┐      │ profile_service.py          │
    │ pedagogy_   │      │                             │
    │ service.py  │      │ get_weaknesses() → decay    │
    │             │      │ get_recommendation() →       │
    │ verify_     │◄─────│   decay + 转移矩阵 +        │
    │ response()  │      │   content recommend         │
    │             │      │ record_event() → hint dep   │
    └──────┬──────┘      └─────────────────────────────┘
           │
    ┌──────▼──────┐      ┌─────────────────────────────┐
    │ tutor_      │      │ llm_service.py               │
    │ service.py  │      │                             │
    │             │      │ classify_question_           │
    │ 调用 verify │      │   complexity()              │
    │ _response() │      │ chat_completion_routed()     │
    └─────────────┘      └─────────────────────────────┘
```

---

## 三、关键文件清单

### 新建文件 (3 个)

| 文件 | 行数 | 说明 |
|------|:--:|------|
| `backend/app/services/judge_service.py` | ~820 | Multi-Judge + Rubric V2 完整实现 |
| `backend/app/services/profile_decay_service.py` | ~660 | 衰减+矩阵+Hint Dep+预测准确率 |
| `evaluation/run_judge_eval.py` | ~280 | Multi-Judge 评估脚本 |

### 修改文件 (4 个)

| 文件 | +行数 | 说明 |
|------|:--:|------|
| `backend/app/core/config.py` | +24 | 3 个 Feature Flags |
| `backend/app/services/pedagogy_service.py` | +5 | `verify_response()` 开关路由 |
| `backend/app/services/profile_service.py` | +180 | 集成 Task 3/4/5 |
| `backend/app/services/llm_service.py` | +90 | 多模型路由 + 复杂度分类 |

### 文档文件 (8 个)

| 文件 | 类型 |
|------|------|
| `docs/implementation/C-Task1-multi-judge.md` | 实现文档 |
| `docs/implementation/C-Task2-rubric-refinement.md` | 实现文档 |
| `docs/implementation/C-Task3-profile-decay.md` | 实现文档 |
| `docs/logs/implementation/2026-07-27-C-Task1-multi-judge.md` | 实现日志 |
| `docs/logs/implementation/2026-07-27-C-Task2-rubric-refinement.md` | 实现日志 |
| `docs/logs/implementation/2026-07-27-C-Task3-profile-decay.md` | 实现日志 |
| `docs/logs/implementation/2026-07-27-C-Task4-hint-dependency.md` | 实现日志 |
| `docs/logs/debug/2026-07-27-C-code-review-fixes.md` | Debug 日志 (第 1 轮) |
| `docs/logs/debug/2026-07-27-C-full-code-review.md` | Debug 日志 (第 2 轮) |

---

## 四、Task 详解

### Task 1 — Multi-Judge 评分系统

**目标**: 评分一致性 Kappa ≥ 0.80

**设计**:
- 3 个评委并发评分 (同模型, temperature 0.1/0.5/0.9)
- 中位数聚合 (抗极端值, RoPoLL 几何中位数策略)
- Fleiss' Kappa 评委间一致性报告
- 分歧 > 1 级自动标记人工复核 (`flagged=True`)

**Feature Flag**: `ENABLE_MULTI_JUDGE`

**调用链**:
```
tutor_service.py
  → pedagogy_service.verify_response()
    → [flag ON]  judge_service.multi_judge_verify()
    → [flag OFF] 原单评委逻辑
```

### Task 2 — Rubric 细化

**4 项增强**:

| 增强 | 来源 | 效果 |
|------|------|------|
| 行为锚定 | Rulers (2025) | 每级用可观测行为定义，消除模糊词 |
| Few-shot 校准 | FutureAGI (2026) | 3 例 (高/中/低)，提升 10-30% 一致性 |
| CoT + 证据锚定 | Rulers (2025) | "证据→分析→分数"三步法，降低 10-25% 方差 |
| 误区特定指导 | Phung et al. (2025) | M1-M8 各独立评判标准 |

### Task 3 — 画像时间衰减 + 转移矩阵

**时间衰减**:
```
severity_t = severity_0 × e^(-λ × t)
λ = ln(2) / 7 ≈ 0.099  (半衰期 7 天)
```

**转移矩阵**:
- 基于 LearningEvent 历史自动构建
- 贝叶斯平滑 Beta(1,1) 先验
- 预测风险概念: "学好 A 后 B 是否也会提高"
- TTL 30 分钟进程内缓存

**Feature Flag**: `ENABLE_TIME_DECAY`

### Task 4 — Hint Dependency 量化

**不需要 Feature Flag** (纯计数器, 零 LLM 调用):
```
score = hints_total / (exercises_total + hints_total)
阈值: low < 0.25 / medium 0.25-0.50 / high > 0.50
```
每次 `hint` 事件触发自动更新 `StudentProfile.hint_dependency`

### Task 5 — Content-Based 练习推荐

**算法**: Jaccard 概念相似度 × 难度匹配权重

**Feature Flag**: `ENABLE_CONTENT_RECOMMEND`

### Task 6 — 多模型路由

**路由规则**:
- 简单问题 (语法/概念查询) → `deepseek-chat` (便宜 ~70%)
- 复杂问题 (原理/算法/设计) → `deepseek-v4-pro` (强推理)
- 预计成本降低 ≥ 50%

---

## 五、运行指南

### 前置条件
```bash
# 1. 配置 API Key
cp backend/.env.example backend/.env
# 编辑 backend/.env, 填入:
#   DEEPSEEK_API_KEY=sk-your-real-key
#   DASHSCOPE_API_KEY=sk-your-real-key  (可选, RAG 用)

# 2. 安装依赖
cd backend
python -m venv .venv
source .venv/Scripts/activate
pip install fastapi uvicorn pydantic pydantic-settings sqlalchemy[asyncio] aiosqlite openai httpx bcrypt python-jose structlog pytest pytest-asyncio alembic

# 3. 启动后端
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# 4. 启动前端 (另一个终端)
cd frontend
npm install
npm run dev
```

### 开启 C 方向功能

编辑 `backend/.env`:
```bash
# C 方向 Feature Flags (全部默认 false)
ENABLE_MULTI_JUDGE=true        # Task 1+2: Multi-Judge 评分
ENABLE_TIME_DECAY=true         # Task 3: 时间衰减 + 转移矩阵
ENABLE_CONTENT_RECOMMEND=true  # Task 5: Content-Based 练习推荐
```

### 运行评估

```bash
# Task 1+2: Multi-Judge 评估 (需要 DEEPSEEK_API_KEY)
ENABLE_MULTI_JUDGE=true python evaluation/run_judge_eval.py

# 单评委基线对比
ENABLE_MULTI_JUDGE=false python evaluation/run_judge_eval.py

# 使用自定义测试集
python evaluation/run_judge_eval.py --cases my_test_cases.json
```

### 验收验证

```bash
cd backend && source .venv/Scripts/activate

# 全量回归测试
python -c "
from app.services.judge_service import *
from app.services.profile_decay_service import *
from app.services.profile_service import *
from app.services.pedagogy_service import *
from app.services.llm_service import *
from app.core.config import settings
print('所有模块导入成功')

# 验证 3 个 Flag 默认关
assert settings.ENABLE_MULTI_JUDGE == False
assert settings.ENABLE_TIME_DECAY == False
assert settings.ENABLE_CONTENT_RECOMMEND == False
print('Feature Flags 全部默认 OFF - 旧逻辑零影响')
"
```

---

## 六、指标目标

| Task | 指标 | 当前 | 目标 | 测量方法 |
|------|------|:--:|:--:|------|
| 1+2 | 回复评分 Kappa | 0 | ≥ 0.80 | 30 例人工标注 vs Multi-Judge |
| 3 | 弱项推荐命中率 | 0 | ≥ 70% | 推荐后 3 天内续错概率 |
| 4 | Hint Dependency 精度 | 硬编码 "low" | 真实量化 | hints/(exercises+hints) |
| 5 | 推荐练习完成率 | 未测 | 比随机高 35% | 推荐题 vs 非推荐题完成率 |
| 6 | 多模型成本降低 | 0 | ≥ 50% | 简单→chat (¥0.001/tok) vs 全部 pro (¥0.004/tok) |

---

## 七、文献参考

- **Rulers** (2025): Locked Rubrics and Evidence-Anchored Scoring — 行为锚定 + 证据锚定
- **RoPoLL** (Acharya 2026): Robust Panel of LLM Judges — 中位数聚合优于算术均值
- **Phung et al.** (2025): Bridging Gaps Between Student and Expert Evaluations — 误区特定 Rubric
- **Rao & Callison-Burch** (2026): Agreement Metrics for LLM-as-Judge — Kappa 唯一捕获边缘偏移
- **Zheng et al.** (2024): Judging LLM-as-a-Judge — self-enhancement bias 10-25pts
- **Ahtisham et al.** (2026) LAK: AI Annotation Orchestration — Cross-verification 提升 κ 37%
- **FutureAGI** (2026): Few-Shot Calibration — 校准示例提升 10-30% 一致性
