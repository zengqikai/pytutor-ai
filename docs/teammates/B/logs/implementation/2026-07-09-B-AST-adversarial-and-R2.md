# 实现日志 — 对抗性审查修复 + R2 研究原型

> 日期：2026-07-09
> 方向：B（AST 诊断）+ 横切（chat 时序）+ 研究（R2 忠实度基准）
> 负责人：外部审查（Claude）

## 1. 今日目标

1. 对整个项目做对抗性代码审查，独立复核 SRS 3.1 的修复声明。
2. 修复审查中新发现的假阳性与时序缺陷，写防回归测试。
3. 完善 SRS（→ 3.2），把新发现固化为可验收需求。
4. 落地最重要的一部分代码：AST 诊断加固 + R2 研究原型（忠实度核验器）。
5. 全程留痕：更新日志、Debug 日志、说明文档。

## 2. 完成内容

- **审查**：读完 backend 全量源码 + 三份 SRS + 修复设计 + 研究计划；用离线
  探针独立验证 F5.1–F5.4 已修复（无回归），并**新发现三簇假阳性 + 一处时序
  缺陷**（详见 Debug 日志）。
- **修复**：`ast_analyzer.py` / `ast_visitors.py` / `chat_service.py` 三处补丁，
  净增 ~180 行、删 ~35 行；48 原有测试 0 回归。
- **测试**：新增 `test_ast_adversarial_v31.py`（26 例全过）。
- **研究原型（R2）**：`research/faithfulness/` 下 4 个文件——AST 事实抽取器、
  忠实度核验器、种子数据集、C1/C2 对比实验编排器，离线可跑、指标可复现。
- **文档**：SRS 3.2 增补、B-AST 实现文档更新、本日志、Debug 日志、总说明文档。

## 3. 修改文件

| 文件 | 修改说明 |
|---|---|
| backend/app/analysis/ast_analyzer.py | `_collect_dict_vars` 扩展 dict 来源识别（+83/−6） |
| backend/app/analysis/ast_visitors.py | M8 条件变量提取、M8 场景2豁免、M6 计算意图护栏（+117/−28） |
| backend/app/services/chat_service.py | 误区事件记录延后到查历史之后（F2/F9 时序）（+24/−15） |
| backend/tests/test_ast_adversarial_v31.py | 新增：26 例对抗负例 + 真阳性回归 |
| research/faithfulness/ast_facts.py | 新增：AST 事实集抽取器 |
| research/faithfulness/faithfulness_verifier.py | 新增：忠实度核验器（R2 核心） |
| research/faithfulness/dataset_seed.json | 新增：R2 种子数据集（含 hard negatives） |
| research/faithfulness/run_experiment.py | 新增：C1/C2 对比实验编排器 |

## 4. 本地验证命令

```bash
# AST 诊断回归 + 对抗
pytest backend/tests/test_ast_analyzer.py backend/tests/test_ast_adversarial_v31.py -v
# 策略时序
python -c "from app.services.pedagogy_service import select_strategy as s; \
  assert s('M3',1,False)['strategy']=='progressive_hint'; \
  assert s('M3',3,True)['strategy']=='concept_explanation'; print('ok')"
# R2 离线演示
cd research/faithfulness && python run_experiment.py --demo
```

## 5. 指标变化

| 指标 | 修改前 | 修改后 | 备注 |
|---|---|---|---|
| 原有 AST 测试 | 48/48 | 48/48 | 0 回归 |
| 对抗负例（本次新增） | 未测 | 26/26 | 新发现假阳性全部消除 |
| M8 假阳性（len/收敛循环） | 复现 | 0 | — |
| M4 假阳性（非字面量 dict） | 复现 | 0 | — |
| M6 假阳性（展示函数） | 复现 | 0 | — |
| B-FR-13 首次→progressive_hint | 不可达 | 可达 | 时序修复 |
| R2 忠实度指标链路 | 无 | 可跑（demo Δ=+0.8） | 桩演示，非真实模型 |

> 注：`v2_eval_results.json` 的 0.96/0.974 仍是泄漏分布上的旧值，按 SRS 3.2
> 要求，重测前不得对外引用。

## 6. 下一步计划

1. 把种子集扩到 150–200 条，用真实 LLM 跑 C1/C2/C3，得到可发表的忠实度数据。
2. 接入子实验 A（三通道假阳性对比，复用本次对抗集）与 B（RAG 接地消融）。
3. 补 D 方向未落地项：`chat_messages.degraded` 落库、数据权利端点、subprocess
   RLIMIT、渗透测试 `test_sandbox_security.py`。
4. 把新增测试纳入 CI（`.github/workflows/ci.yml`）。
