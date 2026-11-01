# 完善清单执行状态

> 对应 `PyTutor_后续完善任务清单.md` 的 17 项。最后更新：2026-11-01。
> 状态只有三种：**完成**（代码 + 验证都有）、**部分**（工程已做，证据不足）、**阻塞**（需要人或数据，不能由代码补）。

## 总览

| # | 任务 | 状态 | 证据 / 缺口 |
|---|------|------|-------------|
| 01 | 固定基线并建立可复现配置 | 完成 | `docs/REPRODUCIBILITY.md`（基线、开关矩阵、数据集哈希、状态用词） |
| 02 | 关闭未鉴权初始化与用户枚举 | 完成 | `/setup/*` 令牌门 + `require_role`；`tests/test_authz.py` |
| 03 | 统一学生代码执行边界 | 完成 | `sandbox/runner.py`；生产无 Docker 拒绝执行；`tests/test_sandbox_runner.py` |
| 04 | 判题成功条件、答案策略、重复奖励 | 完成 | 前端校验 `res.ok`；服务端事件统计；`rewarded` 幂等；`tests/test_authz.py` |
| 05 | 误区事件主键与历史次数 | 完成 | 业务编号 → 主键解析；记录失败可观测；教师端与学生端同源 |
| 06 | 补齐学习事件与入门诊断 | 完成 | 诊断落 `StudentWeakness`；课程/弱项/提示依赖同步；`tests/test_onboarding_profile.py`、`test_learning_loop.py` |
| 07 | 创新功能在界面可见且前后一致 | 完成 | 误区+置信度+依据、真实策略、降级标记、质量分；`metadata` 刷新可还原 |
| 08 | Multi-Judge 失败处理与审核上下文 | 完成 | 失败/不可评估不参与聚合；真实误区透传；修订后重新审核；`tests/test_judge_service.py`、`test_tutor_review.py` |
| 09 | 首次启动、迁移与 CI | 完成 | lifespan 顺序；空库自动导入知识库；根依赖清单收敛；CI 全量离线测试 + 前端构建 |
| 10 | 修正忠实度核验器 | **部分** | 作用域/类型/循环判定已修正，16 个测试通过；抽取器 `rules_v2` 已清理 Markdown/代码块/表格噪声（断言总量 −55%）；已完成 30 例分层抽样表 [`faithfulness_spotcheck.csv`](../evaluation/faithfulness_spotcheck.csv)（3 判定 × C1/C2 各 5 条），填写方法与空白汇总见 [FAITHFULNESS-SPOTCHECK.md](FAITHFULNESS-SPOTCHECK.md)；**仍缺**人工填写抽取/判定两列 |
| 11 | 修正种子标注并冻结独立数据集 | **部分** | 10 条种子已修正并补 schema/来源；扩到 170 条需人工标注与双人核验 |
| 12 | 真实模型 + AST 证据消融 | **部分** | `build_llm()` 可用；10 条 × 2 条件 × 2 次真实运行（抽取器 `rules_v2`），token/延迟/CI 已记录；C2 两次都未优于 C1，规模不足以结论 |
| 13 | 修通 RAG 实际评估路径 | **部分** | 三路真实实现；Hit@K/Recall@K/MRR 分开；覆盖率与跳过原因；无答案查询单独统计；检索上下文 token 均值/最大值已写入结果文件（TF-IDF 251 / 向量 315）。查询已扩到 30 条（验收建议 ≥30），但仍是单作者标注；**仍缺**：检索器没有拒答能力 |
| 14 | 人工对照教学质量评估 | **阻塞** | 需 ≥30 条真实回复 + 人工盲评；无人工评分表前不能宣称 judge–human 一致 |
| 15 | 置信度与画像参数校准 | **阻塞** | 需 ≥200 条独立标注；当前置信度仍是启发式分数 |
| 16 | 演示、结果包与论文/PPT 对齐 | **完成** | `docs/DEMO.md`、`docs/DATA_CARD.md`、`docs/PPT-ALIGNMENT.md`、`docs/CLAIMS-EVIDENCE.md`（主张→算法→界面→证据）、结果 JSON + `evaluation/results_summary.csv` + 结果图 `docs/figures/`；PPTX 已按对齐文档改 4 处（10 案例、实测结果区、校准边界、负面分支）。论文正文不在仓库内，写作时按 §已验证的数字引用 |
| 17 | SSE 与普通聊天统一 | **完成**（决策：不启用） | 清单写明"如需流式体验"；当前无流式需求，主页走非流式入口。为避免同一问题出现两套诊断/元数据，`POST /sessions/{id}/stream` 明确返回 **501**，并删除未复用上下文的 `send_message_stream`；`tests/test_authz.py::TestStreamingDisabled` 守护 |

## 已验证的数字（截至 2026-11-01）

| 评测 | 结果 | 口径 |
|------|------|------|
| 后端离线测试 | 251 passed, 12 deselected | `cd backend && pytest tests/ -q` |
| 前端构建 | 通过 | `cd frontend && npm run build` |
| 误区诊断（同集） | exact match 1.000 / macro-F1 1.000 / 干净代码 FP 0/22 | 与规则同集，不是留出集 |
| 误区诊断（留出集） | exact match 0.833（25/30）/ macro-F1 0.883 / 干净代码 FP 0/15 | 单作者新写 30+15 条，未据此调规则；M5/M6 是主要缺口 |
| RAG TF-IDF | Hit@5 90.0% / Recall@5 40.7% / MRR 0.900 | 30 条查询；Top-5 上下文 251 token（估算） |
| RAG 向量 | Hit@5 93.3% / Recall@5 50.1% / MRR 0.890 | 30 条查询，延迟 ~636 ms；Top-5 上下文 315 token（估算） |
| RAG Hybrid | 与向量一致 | `ENABLE_HYBRID_WEIGHTS=false`，不能当作融合证据 |
| Multi-Judge | 均分 2.4 / 修订率 9/10 / κ 0.405 | 无人工对照 |
| 忠实度 C1/C2 | run1 0.683/0.647，run2 0.667/0.650；配对差 −0.127 / −0.090，CI 含 0 | 10 条种子，`rules_v2` 抽取器；C2 未见优势 |
| 结果包 | `docs/figures/results-overview.svg`（深色版同名 `-dark`） + `evaluation/results_summary.csv` | 图与表均由结果 JSON 生成；口径见 `docs/figures/README.md` |

## 仍需人来做的事

1. **二次标注**：诊断留出集（30 条 + 15 条干净代码）与 30 条 RAG 查询目前都是单作者；
   需要第二人复核或扩到 170 条忠实度数据集（任务 11）。
2. **人工抽查**：`evaluation/faithfulness_spotcheck.csv` 的 30 条抽取/判定两列（任务 10）。
3. **人工评估**：≥30 条回复的教学质量盲评，与自动评分对照（任务 14）。
4. **数据积累**：≥200 条独立标注后再谈概率校准（任务 15）。
5. **口径复核**：PPT 的 4 处措辞已按 [PPT-ALIGNMENT.md](PPT-ALIGNMENT.md) 改好；若之后重跑实验，需同时更新 PPT、CSV、结果图与本表，不能让页面上留下旧数字。

## 演示时可以直接用的说法

- "工程闭环已经打通：诊断、提示、判题、画像、教师看板读的是同一批事件。"
- "沙箱边界统一，生产环境隔离不可用时会拒绝执行而不是降级到宿主进程。"
- "误区诊断在同集上 100%，留出集上 exact match 83.3%（25/30）、干净代码零误报；主要缺口是 M5/M6。"
- "RAG 三路检索都能跑，30 条查询上向量 Hit@5/Recall@5 高于 TF-IDF，但 MRR 略低，且查询仍是单作者标注。"
- "忠实度实验链路已真实跑通，但当前样本量得不出 C2 更优的结论。"
