# 演示脚本（可复现）

> 对应完善任务清单 **16** 的"准备一条可重复演示"。
> 目标：一条主线走完「入门诊断 → 错误代码 → 结构证据 → 教学提示 → 修正通过 → 画像变化 → 教师统计」，
> 并保留三条分支：无误区、沙箱不可用、模型不可用。

## 0. 准备

```bash
# 后端
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 前端（另一个终端）
cd frontend && npm run dev
```

打开 http://localhost:3000 ，用学生账号登录。
确认 `backend/.env` 里 `ENABLE_AST_DIAGNOSIS=true`（默认演示配置已开），
`DEEPSEEK_API_KEY` 已配置。

> 如果使用一个全新数据库：首次启动会自动建表、写入 M1–M8、导入知识库，
> 日志里能看到 `misconceptions_seeded`、`knowledge_seeded_on_first_start`、`tfidf_index_rebuilt`。

## 1. 主线（约 4 分钟）

| # | 操作 | 预期看到 | 讲解点 |
|---|------|----------|--------|
| 1 | 首次登录，选择「学过一点」→ 完成 6 题诊断（故意答错 2 题） | 进入补习课程；诊断结果写入画像 | 引导按用户隔离；诊断不只是存个等级，薄弱点进了 `StudentWeakness` |
| 2 | 退出辅导（右上角），进入主对话页 | | |
| 3 | 在编辑器里输入并提交：<br>`items = []`<br>`new = items.append(5)`<br>`print(new)` | 回复带 🧠 M3 徽章 + 置信度 + 「依据：……」行；策略徽章显示「渐进提示」（若开了 steering 则带「· 转移图」） | AST 给出的是结构事实，不是模糊的"可能有问题" |
| 4 | 刷新页面 | 徽章、依据、策略仍在 | 诊断元数据存在 `message.metadata_json`，历史可还原 |
| 5 | 在对话里追问"那应该怎么写？" | 提示等级上升，但不直接给完整答案（Level 1–3） | 教学策略控制提示等级 |
| 6 | 打开练习中心，做一道 `list` 题：第一次提交错误版本 | 显示 Wrong Answer + 测试明细；提示按钮可用 | 判题只在用例全部通过时才算过 |
| 7 | 点一次「提示」，再提交修正版本 | 提交通过；首次奖励 EXP 只加一次 | 提示次数由服务端事件统计；重复提交不重复发奖励 |
| 8 | 打开画像页 | 薄弱点减少/更新，`completed_lessons`、`hint_dependency` 有值 | 学习闭环的数据都落在画像上 |
| 9 | 用教师账号打开 `/teacher` | 薄弱点排行出现刚才的知识点；学生列表显示最近误区；提示依赖分布不是全 low | 教师端与学生端读的是同一批事件 |

## 2. 分支：代码没有误区

输入：

```python
name = "Alice"
print("hello " + name * 3)
```

预期：**不出现**误区徽章，正常讲解字符串重复运算。
（这条以前会被误判成"类型错误"，是验证核验器修复的固定用例。）

## 3. 分支：执行服务不可用（生产语义）

```bash
# 模拟生产：强制隔离但 Docker 不可用
SANDBOX_REQUIRE_ISOLATION=true uvicorn app.main:app --port 8000
```

在练习中心提交任意代码：

- 后端返回 `sandbox_unavailable: true`，`score_pct: 0`
- 前端显示「执行服务不可用，未判定」，**不是** Accepted，也**不是** Wrong Answer
- 画像不新增失败记录，EXP 不增加

## 4. 分支：模型不可用

把 `DEEPSEEK_API_KEY` 改成一个无效值（或断网），在对话里发一段有误区的代码：

- 若 AST 已诊断出误区：返回模板兜底提示，消息上带「⚠️ 降级回复」徽章
- 若无误区可兜底：返回错误提示，不写一条"正常回复"到历史
- 后端日志：`ai_generation_failed`，不会出现 `PendingRollbackError`

## 5. 分支：审核不可用

保持 `ENABLE_MULTI_JUDGE=false` 时单评委失败，或打开 flag 后让评委全部失败：

- 不显示"质量 N/5"徽章
- 后端 `metadata_json` 中不写 `quality_score`
- 预期：**页面不会把一个失败显示成合格分**

## 6. 数据与结果

演示中会产生的数据位置：

| 内容 | 位置 |
|------|------|
| 学习事件 | `learning_events`（`detail_json` 含 `exercise_id` / `hint_level`） |
| 误区事件 | `misconception_events`（关联 `misconceptions.id`，不是业务编号） |
| 对话元数据 | `chat_messages.metadata_json` |
| 学生画像 | `student_profiles`（`weak_topics` / `recent_misconceptions` / `hint_dependency`） |

离线评测结果（不依赖演示环境）：

- `evaluation/v2_eval_results.json` —— 误区诊断
- `evaluation/rag_eval_results_{tfidf,vector,hybrid}.json` —— RAG 三路
- `evaluation/judge_eval_results.json` —— Multi-Judge
- `research/faithfulness/results_real_deepseek_run{1,2}.json` —— 忠实度试跑

## 7. 演示时不要说的话

- 不要说"AST 诊断准确率 100%"——那是在同一批规则用例上的结果，不是留出集。
- 不要说"混合检索比向量检索更好"——`ENABLE_HYBRID_WEIGHTS=false` 时两者结果一致。
- 不要说"证据注入让解释更忠实"——10 条种子的两次真实运行方向不一致。
- 不要说"系统能提升学习成绩"——没有参与者前后测。
