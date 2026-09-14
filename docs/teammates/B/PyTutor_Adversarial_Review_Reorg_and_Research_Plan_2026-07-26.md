# PyTutor 对抗式审查 + 代码重整设计 + 科研计划（2026-07-26）

> 输入：历史会话（B-AST 全程实现记录）、当前 `integrate/adversarial-review-v3.2` 分支全量代码、
> `docs/PyTutor_Ideas_and_Research_Plan.md`、`docs/SRS_3.2_gaps_found_during_implementation.md`、
> 本机实测（149 unit tests passed）。
> 方法：第一性原理审查（价值主张是否成立）+ 对抗式审查（声称的能力在真实链路上是否存在）。

---

## 第一部分：第一性原理审查

### 1.1 系统的价值主张拆到底

整条产品链是「诊断 → 策略 → 生成 → 画像」。第一性原理上，诊断只有两个价值来源：

1. **在真实学生代码分布上的准确率**——目前只在自造的 50+20 例上验证过（96% EM / 0.974 F1 / 5% FPR）；
2. **诊断结果是否改变下游教学行为**——策略层确实消费诊断（chat_service.py:378-388，
   `has_history` 硬编码已在 F2/F9 修复，用真实 DB 历史），这条链是通的。

结论：产品链主干成立，但准确率数字的外推性未经检验（见 2.3）。

### 1.2 科研的价值主张

`PyTutor_Ideas_and_Research_Plan.md` 已经做过一轮严肃的新颖性核查，结论正确且应当维持：

- **主线 = 绿-2**：用 AST 当符号裁判，量化 LLM 误区解释的忠实度（幻觉率），并测证据注入的缓解效果。
  纯离线、零学生数据、与产品链解耦——这是双约束（拿不到真实数据 + 11 月初截止）下唯一稳的主线。
- 子实验 A（hard negatives 假阳性研究）必做；4.3（三通道成本-延迟-准确率比较）作保底。

**但科研主线的基础设施目前是分裂的**（见 2.2 发现 2），这是当前对科研目标最大的实际威胁。

### 1.3 复杂度审计

当前系统承载了：8 类误区 × 4 条诊断通道（regex/AST/LLM/confidence）× 2 套忠实度评测框架 ×
3 人 feature flag × 5 个「已建成但未接线」的模块。对一个 FYP，**集成债务已经超过功能增量**。
重整的第一性原则只有一条：

> 每个模块要么在请求链路上，要么在论文流水线上。两者都不在的，接线、归档或删除。

---

## 第二部分：对抗式审查发现（按严重度排序）

### 2.1 发现 1【最严重】：SRS 3.2 的核心模块全部是孤岛代码

以下模块**只有测试文件引用，没有任何生产/评测链路调用**（grep 全仓验证）：

| 模块 | 声称的作用 | 实际状态 |
|---|---|---|
| `backend/app/analysis/confidence.py` | 证据折算的近似置信度，替换硬编码 | `from_visitor_finding()` 零调用；`_ast_diagnose` 返回的仍是 visitor 硬编码值（0.90/0.88/0.65…） |
| `backend/app/analysis/error_class.py` | 第 1 层错误大类，「M 之外的错误不再隐形」 | `classify_error()` 未接入 exercises 提交链路，错误仍然隐形 |
| `backend/app/analysis/root_cause.py` | 根因层 + 共现验证闸门 | 零调用 |
| `backend/app/services/pedagogy/steering.py` | 教学意图转移图（E-FR-01） | chat_service 仍用旧 `select_strategy()`，转移图从未在真实对话中求值 |
| `backend/app/services/prompts/misconception_anchored.py` | 锚定式 prompt | `_llm_classify()` 仍用旧的裸 prompt |

**对抗式结论**：「128 个测试通过」证明的是模块自身行为符合规格，不是系统行为。
commit 信息里的 "integrate SRS 3.2" 实际是「实现了但没 integrate」。任何答辩/审稿追问
「置信度引擎在系统里怎么工作」都会当场暴露。这不是造假，是接线债，但必须在对外声称前还清。

### 2.2 发现 2：忠实度评测框架存在两套平行实现

- `research/faithfulness/`（v3.2 对抗审查轮的 R2 原型：ast_facts / verifier / run_experiment / dataset_seed）
- `backend/evaluation/faithfulness/`（SRS 3.2 supplement 轮：eval_sample / mcmining_import，schema 带 `category` 字段）

两套 schema 不同、互不引用。**科研主线（绿-2）的地基现在裂成两块**，后续 150-200 条数据集
不知道该长在哪边。这是重整必须首先解决的问题。

### 2.3 发现 3：评测集同源偏置，96% EM 是过拟合上限

50 个误区例 + 20 个 clean 例全部由实现者（人 + LLM）构造，与检测规则同源共生——历史会话里
多轮「跑评测 → 看失败 case → 改规则/改标签（如 C41 pop 争议、C13 标签冲突）」的循环，
本质是在测试集上直接调参。**96.0%/0.974/5.0% 应表述为「内部一致性」，不可外推为泛化准确率**。
`hard_negative` 类别刚在 schema 中补上（gap 文档缺口 1），但根 `evaluation/` 目录下还没有
hard negatives 数据文件；研究计划要求的 150-200 条扩建还未开始。

### 2.4 发现 4：主打成果默认关闭

`ENABLE_AST_DIAGNOSIS: bool = Field(default=False)`（config.py:175）。指标已全面达标的 AST
通道在默认配置下不生效——演示、部署、队友整合跑的都可能是旧正则。三人隔离开发期的开关策略
已完成历史使命，该转为默认开 + 保留关闭回退。

### 2.5 发现 5：测试体系不可复现、且打真实 LLM API

- `pytest` 不在 `backend/.venv` 中（本次审查需手动安装才能跑）——「128 tests」对 clone 下来的人不可复现；requirements 缺 dev 依赖。
- 实测 149 passed，但过程中出现 `LiteLLM-Async Success Call`——**单元测试触发了真实计费 API 调用**（不稳定 + 花钱 + 需要密钥才能过）。
- 10 个测试（test_api.py / test_chat_api.py）要求活服务器，与单元测试混在一起，全量跑必红。

### 2.6 发现 6：仓库卫生——三份代码副本 + 二进制杂物被 git 追踪

被追踪的不应存在之物：`pytutor-review-deliverables/`、`pytutor-srs32-impl/`、
`srs32-supplement-impl/`（三个整合期临时文件夹，各含一整套**旧版本**代码副本，与主代码互相矛盾）、
`*.zip` 交付包、`ai_tutor.db`、`屏幕录制 2026-06-09.mp4`、`Untitled`、`claude-vision-skill-master/`、
根目录散落的 `B-AST-INTEGRATION*.md`。任何 reviewer clone 后会看到四个版本的 `ast_visitors.py`。
（已核查：历史会话中出现过的 API key 未进入仓库文件与 git 历史。）

### 2.7 发现 7：诊断只取 top-1，与自家根因层立论矛盾

`_ast_diagnose` 只返回 `findings[0]`（misconception_service.py:175），多误区共存信息在服务边界
被丢弃。而 `root_cause.py` 的整个立论是「多症状共现指向同一根因」——上游把共现信息扔了，
下游的根因层永远无米下锅。接线时必须让 diagnose 返回完整 findings 列表（向后兼容：保留 top-1 平铺字段，新增 `all_findings`）。

### 2.8 发现 8（小）：正则 M1 的 fallback 面

`_fallback_m1_regex` 在任何 parse 失败时都可能触发，`if f(a=1):` 这类含 kwargs 的行若因**其他**
语法错误进入 fallback，会被误报 M1。当前被「仅在 SyntaxError 时调用」部分缓解，属已知限制，
应记入 debug 日志的 known limitations 而非修复（教学场景下 M1 的先验极高，收益/风险比合理）。

---

## 第三部分：代码重整设计

原则：**不重构主干（研究计划 1.1 的红线不变），只做接线、合并、清理三类动作。**

### 3.1 清理（半天，先做，风险最低）

1. `git rm -r --cached` + 删除：三个整合文件夹、全部交付 zip、`ai_tutor.db`、mp4、`Untitled`、
   `claude-vision-skill-master/`、`pytutor.bundle`；同步补 `.gitignore`（`*.zip`、`*.db`、`*.mp4`、临时整合目录模式）。
2. `B-AST-INTEGRATION*.md`、`B-AST-README.md` → `docs/integration/`。
3. 测试分层：pytest markers `unit` / `integration`（需活服务器）/ `llm`（需真实 key，默认 skip）；
   `pytest -m unit` 必须离线全绿；`pytest`、`pytest-asyncio` 进 `requirements-dev.txt`。

### 3.2 评测框架合并（1 天，科研地基）

以 `backend/evaluation/faithfulness/` 的 **EvalSample schema（含 category/origin_label）为唯一标准**，
把 `research/faithfulness/` 的 ast_facts / verifier / run_experiment 迁移过来合成单一框架，
统一落位 `research/faithfulness/`（论文流水线归 research，产品评测归根 `evaluation/`，边界清晰）。
`dataset_seed.json` 按新 schema 迁移。删除旧位置，测试 import 路径同步更新。

### 3.3 接线冲刺（2-3 天，把孤岛并入大陆）

按依赖顺序：

1. **findings 全量返回**：`diagnose()` 新增 `all_findings` 字段（修发现 7）。
2. **confidence 接入**：`_ast_diagnose` 中对每个 finding 调 `from_visitor_finding(finding, stderr)`，
   用其结果覆盖 `confidence` 字段并附 `confidence_terms`（可解释性进 UI/日志）。同时完成
   confidence.py 里标注的 TODO：让 M4/M6 visitor 输出 `heuristic_only` 标记。
3. **error_class 接入**：exercises 提交链路（`exercises.py` 判题后）调 `enrich_diagnose_result`，
   画像的 weak_topics 用第 1 层错误大类兜底——这是「三层架构」构思一真正落地的一步。
4. **steering 接入**：chat_service 的 `select_strategy` 调用点加 flag
   `ENABLE_PEDAGOGY_STEERING`（默认关），开启时走 `steering.decide_intent`，两周灰度后转默认开。
5. **anchored prompt 接入**：`_llm_classify` 换用 `misconception_anchored` 模板（低风险，直接换）。
6. **flag 翻转**：`.env.example` 与部署配置中 `ENABLE_AST_DIAGNOSIS=true`；README 声明默认行为。

root_cause.py **不接线**：它的激活闸门要求「样本总量 ≥ 200 的真实共现数据」，数据未到位前接了也是空转。
保持为带闸门的休眠模块，在文档中明确标注「等待数据激活」。

### 3.4 指标口径修正（半天，诚信问题）

所有文档（README、实现日志、SRS 引用处）中 96%/0.974/5% 统一改口径为
「内部评测集（自建 50+20 例）一致性」，并注明置信度未校准（confidence.py docstring 的
诚实边界升格为对外口径）。这一步在任何对外展示前必须完成。

---

## 第四部分：科研计划（2026-07-26 → 11 月初，约 14 周）

主线维持绿-2（AST 符号裁判测 LLM 误区解释忠实度）+ 子实验 A（hard negatives）必做，
子实验 B（RAG 消融）或 C（双语）二选一，4.3 三通道比较作保底副产品。

### 4.1 与重整的依赖关系

第三部分 3.1 + 3.2 是科研的前置（评测框架必须先合一）；3.3 接线与科研并行不冲突
（绿-2 纯离线，不依赖产品链路）。

### 4.2 阶段计划

| 阶段 | 周 | 内容 | 硬产出 | 风控 |
|---|---|---|---|---|
| 0 地基 | W1（7/27-8/2） | 3.1 清理 + 3.2 评测框架合并 + 3.4 口径修正 | 单一 faithfulness 框架跑通 demo | — |
| 1 数据集 | W2-W4 | 扩建至 150-200 条：≥100 positive（M1-M8 均衡）、≥40 hard_negative、≥30 clean；来源三分：手工构造 / LLM 生成+人工筛（生成模型 ≠ 被测模型，防同源）/ 公开数据集映射（mcmining_import 已有雏形）。**预注册**：先冻结 faithfulness 指标定义与判定规则再看数据 | `dataset_v1.json` + 数据卡（来源/许可/构造方式） | 若队友可标注，安排第二人对 20% 抽样双标，报一致率 |
| 2 核验器 | W5-W6 | 解释 → 原子断言拆分（LLM）→ AST 事实集核对；断言分「可核验/不可核验」两类，只对前者计忠实度 | verifier v1 + 30 例人工抽查一致率 ≥ 85% | 拆分误差是最大风险，人工校验不可省 |
| 3 实验 | W7-W8 | C1 纯 LLM / C2 AST 证据注入 /（可选 C3 换模型）；同批数据顺手产出三通道成本-延迟-准确率表（保底 4.3） | 主结果表 + 混淆矩阵 + 幻觉类型分布 | C2 用 3.3 已接线的 anchored prompt，工程科研复用 |
| 4 子实验 | W9-W10 | 子实验 A：hard_negative 上三通道假阳性率与幻觉模式；时间富余则加 B 或 C 之一 | 子实验章节数据 | 若阶段 2 延误，砍 B/C 保 A |
| 5 写作 | W11-W14（→11 月初） | 初稿：数据集 + 方法 + 三组发现；人工校验章节如实报告 | 论文初稿 + 可复现代码包（干净 repo 直接充当） | 若主线受阻，4.3 三通道比较独立成保底短文 |

### 4.3 论文骨架（与研究计划 4.4 一致，此处冻结）

一个评测集（含 hard negatives 与数据卡）+ 一个核验方法（AST 符号裁判 vs 纯文本裁判的 delta）
+ 三组发现（幻觉率与类型分布、证据注入的缓解量、假阳性模式）。全程零学生数据、零重构。

### 4.4 明确不做

- root_cause 数据挖掘（绿-3）：无真实共现数据，闸门保持关闭；
- predict-then-run 人体实验（绿-4）：无被试渠道；
- 五级提示遵循度审计（4.2 备选）：离答案泄露红区太近，仅在导师明确把关 delta 时重启。

---

## 附：本次审查的验证方法记录

- 孤岛判定：`grep -rn "from app.analysis.(confidence|error_class|root_cause)|steering|misconception_anchored"` 全仓，排除 tests 后零命中；
- 测试实测：venv 安装 pytest 后 `pytest tests/ -q` → 149 passed / 2 failed + 8 errors（全部为需活服务器的 ConnectError）；测试期间观察到真实 LiteLLM API 调用；
- key 泄露核查：`git grep sk-8a0e…` 与全文件 grep 均为空；
- 双框架判定：`research/faithfulness/` 与 `backend/evaluation/faithfulness/` 并存，schema 不同且互不引用。
