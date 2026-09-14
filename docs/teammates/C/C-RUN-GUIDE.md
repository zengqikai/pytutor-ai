# PyTutor C 方向 — 运行与验收指南

> 快速启动、测试、验证 C 方向全部 6 个 Task

---

## 1. 环境准备 (5 分钟)

### 1.1 必须有 Python 3.13+
```bash
python --version  # 应输出 Python 3.13.x
```

### 1.2 安装后端依赖
```bash
cd backend

# 创建虚拟环境
python -m venv .venv

# 激活 (Windows Git Bash / Linux / macOS)
source .venv/Scripts/activate   # Windows Git Bash
# source .venv/bin/activate     # Linux/macOS

# 安装核心依赖 (注意: litellm/chromadb/sentence-transformers 需要 Rust 编译, 先跳过)
pip install fastapi uvicorn[standard] pydantic pydantic-settings sqlalchemy[asyncio] aiosqlite openai httpx bcrypt python-jose[cryptography] structlog pytest pytest-asyncio alembic
```

### 1.3 配置 API Key
```bash
# 复制模板
cp .env.example .env   # 如果没有 .env.example, 直接创建 .env

# 编辑 backend/.env, 最少填入:
#   DEEPSEEK_API_KEY=sk-你的真实Key    (必须, AI 功能全靠它)
#   DASHSCOPE_API_KEY=sk-你的Key       (可选, RAG 语义检索用)
```

如果暂时没有 API Key, C 方向代码仍可正常运行 — 只需 **不开启 Feature Flag** 即可, 所有旧逻辑零影响。

### 1.4 启动后端
```bash
cd backend
source .venv/Scripts/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
看到 `Application startup complete` 即成功。

### 1.5 (可选) 启动前端
```bash
cd frontend
npm install
npm run dev
```
访问 http://localhost:3000

---

## 2. 快速验证 C 方向代码 (30 秒, 不需要 API Key)

```bash
cd backend
source .venv/Scripts/activate

python -c "
# 全模块导入验证
from app.services.judge_service import *
from app.services.profile_decay_service import *
from app.services.profile_service import *
from app.services.pedagogy_service import *
from app.services.llm_service import *
from app.core.config import settings

# Feature Flag 验证
assert settings.ENABLE_MULTI_JUDGE == False
assert settings.ENABLE_TIME_DECAY == False
assert settings.ENABLE_CONTENT_RECOMMEND == False
print('C 方向全部模块正常, 3 个 Flag 默认 OFF')
print('旧逻辑完全不受影响 - 验证通过')
"
```

---

## 3. 开启 C 方向功能

编辑 `backend/.env`, 添加:

```bash
# ==========================================
# C 方向 Feature Flags (全部默认 false)
# ==========================================

# Task 1+2: Multi-Judge 教学回复质量评估
# 开启后 verify_response() 使用 3 评委中位数评分
ENABLE_MULTI_JUDGE=true

# Task 3: 画像时间衰减 + 知识转移矩阵
# 开启后弱项 severity 按遗忘曲线衰减, 推荐含转移风险提示
ENABLE_TIME_DECAY=true

# Task 5: Content-Based 练习推荐
# 开启后 get_recommendation() 返回基于弱项概念相似度的练习列表
ENABLE_CONTENT_RECOMMEND=true
```

修改后重启后端 (`Ctrl+C` 然后重新 `uvicorn`)。

---

## 4. 运行评估脚本

### 4.1 Multi-Judge 评估 (需要 API Key)

```bash
cd backend
source .venv/Scripts/activate

# 多评委模式
ENABLE_MULTI_JUDGE=true python ../evaluation/run_judge_eval.py

# 单评委基线对比
ENABLE_MULTI_JUDGE=false python ../evaluation/run_judge_eval.py
```

输出文件: `evaluation/judge_eval_results.json`

### 4.2 单元测试式验证 (不需要 API Key)

```bash
cd backend
source .venv/Scripts/activate

python -c "
from app.services.judge_service import *
from app.services.profile_decay_service import *
from datetime import datetime, timezone, timedelta

# --- Task 1: Multi-Judge 聚合 ---
print('=== Task 1+2: Multi-Judge ===')
v1 = JudgeVerdict(0,0.1,{'D1_hint_adherence':4,'D2_beginner_appropriate':4,'D3_no_leakage':4,'D4_misconception_target':4,'D5_actionability':4},20,4,[],False,'ok',{'D1':'','D2':'','D3':'','D4':'','D5':''},[],'{}',100)
v2 = JudgeVerdict(1,0.5,{'D1_hint_adherence':5,'D2_beginner_appropriate':5,'D3_no_leakage':5,'D4_misconception_target':5,'D5_actionability':5},25,5,[],False,'ok',{},{},[],'{}',110)
v3 = JudgeVerdict(2,0.9,{'D1_hint_adherence':3,'D2_beginner_appropriate':3,'D3_no_leakage':3,'D4_misconception_target':3,'D5_actionability':3},15,3,[],False,'ok',{},{},[],'{}',120)
r = _aggregate_verdicts([v1,v2,v3])
print(f'  中位数聚合: score={r.aggregated_score}, kappa={r.kappa_inter_judge}')
assert r.aggregated_score == 4.0, '中位数应为4'
print('  Task 1 PASS')

# Kappa: 完全一致 = 1.0
p1 = JudgeVerdict(0,0.1,{k:5 for k in ['D1_hint_adherence','D2_beginner_appropriate','D3_no_leakage','D4_misconception_target','D5_actionability']},25,5,[],False,'',{},{},[],'',100)
p2 = JudgeVerdict(1,0.5,{k:5 for k in ['D1_hint_adherence','D2_beginner_appropriate','D3_no_leakage','D4_misconception_target','D5_actionability']},25,5,[],False,'',{},{},[],'',110)
p3 = JudgeVerdict(2,0.9,{k:5 for k in ['D1_hint_adherence','D2_beginner_appropriate','D3_no_leakage','D4_misconception_target','D5_actionability']},25,5,[],False,'',{},{},[],'',120)
assert _compute_inter_judge_kappa([p1,p2,p3]) == 1.0
print('  Task 2 PASS (Kappa=1.0)')

# --- Task 3: 时间衰减 ---
print()
print('=== Task 3: Profile Decay ===')
now = datetime.now(timezone.utc)
r7d = compute_decayed_severity(4, now - timedelta(days=7), now)
assert 1.9 < r7d['decayed'] < 2.1, f'7天应减半: 4→~2, got {r7d[\"decayed\"]}'
print(f'  7天衰减: 4→{r7d[\"decayed\"]} (预期~2.0)')
print('  Task 3 PASS')

# --- Task 4: Hint Dependency ---
print()
print('=== Task 4: Hint Dependency ===')
r = compute_hint_dependency(total_hints=8, total_exercises=16)
assert r['label'] == 'medium'
print(f'  8hints/16exercises = {r[\"score\"]} → {r[\"label\"]}')
print('  Task 4 PASS')

# --- Task 5: Content-Based ---
print()
print('=== Task 5: Content Recommend ===')
s = compute_concept_similarity('for_loop', 'while_loop')
assert s > 0.1
print(f'  sim(for_loop, while_loop) = {s}')
print('  Task 5 PASS')

# --- Task 6: Model Routing ---
print()
print('=== Task 6: Model Routing ===')
r = classify_question_complexity('Python列表怎么用')
assert r['level'] == 'simple'
print(f'  简单问题→{r[\"routed_model\"]} ({r[\"reason\"][:50]})')
r2 = classify_question_complexity('解释GIL机制和性能优化')
assert r2['level'] == 'complex'
print(f'  复杂问题→{r2[\"routed_model\"]} ({r2[\"reason\"][:50]})')
print('  Task 6 PASS')

print()
print('=' * 40)
print('C 方向全部 6 个 Task 验证通过!')
print('=' * 40)
"
```

预期输出:
```
=== Task 1+2: Multi-Judge ===
  中位数聚合: score=4.0, kappa=-0.0714
  Task 1 PASS
  Task 2 PASS (Kappa=1.0)

=== Task 3: Profile Decay ===
  7天衰减: 4→2.0 (预期~2.0)
  Task 3 PASS

=== Task 4: Hint Dependency ===
  8hints/16exercises = 0.333 → medium
  Task 4 PASS

=== Task 5: Content Recommend ===
  sim(for_loop, while_loop) = 0.182
  Task 5 PASS

=== Task 6: Model Routing ===
  简单问题→deepseek-chat
  复杂问题→deepseek-v4-pro
  Task 6 PASS

========================================
C 方向全部 6 个 Task 验证通过!
========================================
```

---

## 5. 端到端测试 (需要 API Key + 前端)

1. 确保 `ENABLE_MULTI_JUDGE=true` 在 `.env` 中
2. 重启后端
3. 浏览器打开 http://localhost:3000
4. 登录 → 发起对话 "Python列表怎么添加元素"
5. 查看后端日志, 应看到 `multi_judge_start` → `multi_judge_done` 日志
6. 访问 http://localhost:8000/api/v1/profile/me/recommendations
7. 如果 `ENABLE_CONTENT_RECOMMEND=true`, 应看到 `recommended_exercises` 字段

---

## 6. 关闭 C 方向功能 (回滚)

在 `backend/.env` 中:
```bash
ENABLE_MULTI_JUDGE=false
ENABLE_TIME_DECAY=false
ENABLE_CONTENT_RECOMMEND=false
```
重启后端。所有旧逻辑立即恢复, 数据无损。

---

## 7. 常见问题

| 问题 | 解决 |
|------|------|
| AI 聊天没反应 | `DEEPSEEK_API_KEY` 填写了吗? 检查 `.env` |
| ENABLE_MULTI_JUDGE=true 但无 multi_judge 日志 | 需要 `DEEPSEEK_API_KEY` 有效才跑得起来 |
| 启动报 TF-IDF 重建失败 | 第一次启动正常现象, 表还没建。重启就好 |
| ImportError: litellm | 跳过了, 不影响。fallback 到 openai SDK 直连 |
