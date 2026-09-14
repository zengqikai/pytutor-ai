# 2026-07-26 · 接线冲刺（SRS 3.2 孤岛模块并入主链路）+ 仓库重整

> 背景：对抗式审查（见 `docs/PyTutor_Adversarial_Review_Reorg_and_Research_Plan_2026-07-26.md`）
> 发现 SRS 3.2 的五个核心模块只有测试引用、零生产调用（"造好未安装"），且忠实度评测
> 框架存在两套平行实现。本轮把孤岛并入大陆，并修复过程中暴露的评测漂移。

## 一、接线改动

| 模块 | 接入点 | 方式 |
|---|---|---|
| `analysis/confidence.py` | `misconception_service._ast_diagnose` | 每个 finding 经 `from_visitor_finding()` 折算；**排序仍用 visitor 规则先验**（保持诊断结论稳定），对外报告的 `confidence` 换成证据折算值，附 `confidence_terms` 供解释 |
| （同上） | `diagnose()` 返回值 | 新增 `all_findings`——多误区共存信息不再在服务边界丢弃（root_cause 层未来的数据来源） |
| `analysis/error_class.py` | `api/v1/exercises.submit_exercise_answer` | 未全过时计算第 1 层错误大类；进返回体（`error_class` / `beyond_misconceptions`）与画像失败事件 detail |
| `services/pedagogy/steering.py` | `chat_service`（新 flag `ENABLE_PEDAGOGY_STEERING`，默认关） | 开启时转移图决定教学意图 + 锚定 prompt 决定表达约束；失败自动回退旧 `select_strategy` 文案 |
| `services/prompts/misconception_anchored.py` | 同上 | `build_system_prompt` 注入（置信度调语气 + 不泄露答案否定式清单） |

Flag 变化：`ENABLE_AST_DIAGNOSIS` 默认 **False → True**（三人隔离开发期结束；AST 内部自带
regex/LLM fallback，设 false 可整体回退）。

**root_cause.py 明确不接线**：激活闸门要求 ≥200 条真实共现数据，数据未到位前保持休眠。

## 二、评测漂移的发现与修复（本轮最重要的产出）

**发现**：`evaluation/v2_eval_results.json` 最后一次生成于 SRS 3.1（commit 9c4a045），
其后 v3.2 对抗修复轮（54950ad）改了 M4/M6/M8 visitor 却未复跑评测。复跑实测：
**86% EM / 0.909 F1 / 0% FPR**——文档声称的 96%/0.974/5% 已过期两个提交。

**根因**（6 个回归 case）：
- M5×4（C05/C31/C43 等）：v3.2 把"循环体内引用 stop 值"设为唯一门控。对意图型误区，
  学生**亲口问出**"为什么只到4不到5"是最强证据，不应被结构信号一票否决。
- M6×1（C38）：`print(n % 2 == 0)` 的实参是 `ast.Compare`，"计算值"判定只认
  `Name`/`BinOp`，比较表达式漏判。

**修复**（`ast_visitors.py`，v3.3）：
- M5 门控改为「结构信号 **或** 提问信号」。提问信号分两档：强关键词直接成立；
  弱关键词（"最后"）须同时出现边界数值（stop 或 stop-1），防"最后输出是什么"类
  中性提问误触发。新增弱结构信号：循环变量在循环结束后被引用（+0.2）。
- M6 "计算值"判定扩展 `ast.Compare` / `ast.BoolOp`。

**修复后**：**94% EM / 0.972 F1 / 0% FPR**（47/50 + 0/20），147 单元测试全绿，
对抗探针 0 误报。剩余 3 个失败均为已记录的标签争议（C13 M5/M8 冲突、C41 pop 有
返回值、C17 中性提问弱标签），不为凑指标扭曲检测器。

**教训（写给下一次）**：改 visitor 必须复跑 `run_v2_eval.py` 并提交结果文件，
否则文档指标与代码脱钩。

## 三、仓库重整

- untrack + 删除：`pytutor-review-deliverables/`、`pytutor-srs32-impl/`、
  `srs32-supplement-impl/`（三份过时代码副本）、全部交付 zip、`pytutor.bundle`、
  `Untitled`、`claude-vision-skill-master/`；`.gitignore` 补齐对应模式。
- **忠实度评测框架合一**：`backend/evaluation/faithfulness/`（EvalSample schema +
  mcmining 导入）迁入 `research/faithfulness/`，与实验管线（ast_facts / verifier /
  run_experiment）同居一处。import 路径同步更新。
- 测试分层：新增 pytest markers `integration`（需活服务器：test_api / test_chat_api）、
  `llm`（打真实计费 API：test_llm / test_rag）；默认 `pytest` 只跑离线单元测试
  （147 个，~3s，零网络零费用）。pytest/pytest-asyncio 进 `requirements.txt`。

## 四、指标口径（对外表述统一为）

> 内部评测集（自建 50 误区例 + 20 clean 例）上：Exact Match 94%、Macro F1 0.972、
> 假阳性率 0%。该集合与检测规则同源，数字表示内部一致性，不可外推为真实分布准确率；
> 置信度未经校准（见 confidence.py 诚实边界）。
