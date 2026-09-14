# 实现日志 — B-AST 修复 (SRS 3.1)

> 日期: 2026-07-09 | 方向: B | 负责人: 连哥
> 基于: PyTutor_Fix_Design_and_Research.md + SRS_3.1_Security_Robustness_Amendment
> 配套: PyTutor_问题清单.md + PyTutor_Ideas_and_Research_Plan.md

---

## 1. 今日目标

按 Critical → Major 顺序实施 F1-F8 修复，消除已知缺陷，提升系统稳健性。

## 2. 完成内容

### F1: Config 安全护栏 ✅
- 文件: `backend/app/core/config.py`
- 新增 `model_validator(mode="after")` `_enforce_prod_hardening()`
- 生产/staging 环境拒绝占位符密钥、强制 debug=False、DEBUG 日志降级为 INFO

### F2: 修复 has_history 硬编码 ✅
- `misconception_service.py`: 新增 `get_misconception_history_count()`
- `chat_service.py`: `select_strategy()` 调用改为使用真实历史数据
- `has_history` 从硬编码 False → 查询 MisconceptionEvent 表真实计数

### F5.1: M4 字典遍历排除 ✅
- `ast_visitors.py`: M4ValueAsIndexVisitor 接受 dict_vars 参数
- `ast_analyzer.py`: 新增 `_collect_dict_vars()` 预扫描，传给 M4
- 解决 CLEAN16 dict 遍历误报

### F5.2: M8 mutating-method 收敛 ✅
- `ast_visitors.py`: `_extract_modified_vars()` 新增方法调用接收者检测
- `items.pop()`/`q.popleft()` 视为变量被修改，不报 M8

### F5.3: M5 去循环论证 ✅
- 关键词表删除 `"range"`（题目必然词）
- 外部信号权重 0.6 → 0.3
- 新增结构性要求：必须有 `stop_ref_in_body` 才过阈值

### F5.4: M7 有序类型传播 ✅
- `_scan_assignments` 从无序 walk → 有序 body 扫描
- `int()/float()/len()` 结果登记为 `"num"`
- 后写覆盖前写，未知类型清除登记
- 算术分支新增 `ast.FloorDiv`, `ast.Mod`
- `%` 对字符串字面量 → 格式化（不报），input 变量 → M7

### F6: LLM 不可用 AST 兜底 ✅
- `chat_service.py`: except 分支新增 misconception_result 模板化兜底
- 返回 `degraded: true` 标记，前端可提示

### F7: RAG 熔断器 ✅
- `rag_service.py`: 新增 `RAGBreaker` 进程内熔断器
- `chat_service.py`: 超时 15s → 3s，连续 3 次失败后熔断 30s

### F8: 前端注册静默失败 ✅
- `register/page.tsx`: 空 catch → 客户端邮箱预校验 + 错误提示

## 3. 修改文件

| 文件 | 操作 | 改动 |
|------|------|------|
| `backend/app/core/config.py` | 修改 | +25 行 model_validator |
| `backend/app/services/misconception_service.py` | 修改 | +20 行 get_misconception_history_count |
| `backend/app/services/chat_service.py` | 修改 | F2: ~6 行 / F6: +20 行 / F7: ~8 行 |
| `backend/app/services/rag_service.py` | 修改 | +30 行 RAGBreaker |
| `backend/app/analysis/ast_visitors.py` | 修改 | F5.1-F5.4: ~50 行改动 |
| `backend/app/analysis/ast_analyzer.py` | 修改 | +25 行 _collect_dict_vars |
| `backend/tests/test_ast_analyzer.py` | 修改 | 更新 3 个 M5 测试 |
| `frontend/src/app/register/page.tsx` | 修改 | +5 行 邮箱验证 + 错误提示 |

## 4. 验证

```bash
python -m compileall -q backend/app    # ✅ (仅预存 docker_executor 报错)
pytest backend/tests/test_ast_analyzer.py -q  # ✅ 48 passed
```

### F3: 沙箱统一入口 ✅
- 文件: `backend/app/sandbox/runner.py` (新建)
- 根据 app_env + Docker 可用性决策表分发
- 生产无 Docker → 拒绝执行 + 告警
- `code_service.py` 改为调用统一入口

### F4: 安全静态检查 ✅
- 文件: `backend/app/sandbox/security.py`
- `open()` 全禁（学习场景不需要文件读写）
- 新增反射逃逸探针检测（__subclasses__/__bases__/__builtins__）
- docstring 明确标注"非安全边界"

### F9: 并发安全 ✅
- 文件: `backend/app/services/chat_service.py`
- profile JSON read-modify-write → record_misconception_event() append
- 画像字段改为读时从事件表聚合

### F10: Agent 节点超时 ✅
- `agents/nodes/rag_retrieval.py`: retrieve_context → asyncio.wait_for(5s)
- `agents/nodes/tutor_node.py`: chat_completion → asyncio.wait_for(60s)

## 5. 全部完成项

| # | 严重程度 | 内容 | 工作量 |
|---|:---:|------|:---:|
| F1 | Critical | Config 安全护栏 | Small |
| F2 | Critical | has_history 硬编码修复 | Small |
| F3 | Critical | 沙箱统一入口 + 生产隔离 | Medium |
| F4 | Major | 安全静态检查 + 反射探针 | Medium |
| F5.1-F5.4 | Major | AST 四类假阳性修复 | Medium |
| F6 | Major | LLM 不可用 AST 兜底 | Small |
| F7 | Major | RAG 熔断器 | Small |
| F8 | Major | 前端注册错误处理 | Small |
| F9 | Major | 并发安全修复 | Medium |
| F10 | Major | Agent 节点超时 | Medium |

## 6. 验证

```bash
python -m compileall -q backend/app    # ✅ (仅预存 docker_executor 报错)
pytest backend/tests/test_ast_analyzer.py -q  # ✅ 48 passed
```

## 7. 问题清单对照

基于 `docs/PyTutor_问题清单.md`，F1-F10 已解决以下问题：

| 问题编号 | 问题 | 修复 | 状态 |
|---------|------|------|:---:|
| A4 | 假阳性（dict遍历/mutating loop） | F5.1, F5.2 | ✅ |
| A4 | M5 题面循环论证 | F5.3 | ✅ |
| A4 | M7 重赋值不覆盖 | F5.4 | ✅ |
| B1 | has_history 硬编码 False | F2 | ✅ |
| D1 | 沙箱隔离未接入 | F3 | ✅ |
| D2 | SECRET_KEY 占位符 | F1 | ✅ |
| D3 | 安全黑名单可绕过 | F4 | ✅ |
| D4 | LLM/RAG 故障不优雅 | F6, F7, F10 | ✅ |
| D5 | 评测集分布泄漏 | 已记录，待后续 | ⚠️ |
| A1 | M1-M8 覆盖面不够 | 研究方向（三层诊断架构） | 🔬 |
| A2 | 只看症状不看根因 | 研究方向（根因层） | 🔬 |
| A3 | 置信度硬编码 | 研究方向（真置信度） | 🔬 |
| B2 | 学习路径死顺序 | 研究方向（架桥） | 🔬 |
| B3 | 诊断与路径不connect | 研究方向（架桥） | 🔬 |
| B4 | 推荐系统未实现 | C 方向负责 | ⏳ |
| C1 | 权重机制对 M 外错误隐形 | 研究方向（三层诊断第0/1层） | 🔬 |

> 🔬 = 研究级问题，见 `docs/PyTutor_Ideas_and_Research_Plan.md`

## 8. 新文档索引

| 文档 | 路径 | 内容 |
|------|------|------|
| 问题清单 | `docs/PyTutor_问题清单.md` | 全项目 14 个问题（A-D 四类） |
| 构思与科研计划 | `docs/PyTutor_Ideas_and_Research_Plan.md` | 工程改造构思 + 科研方向分析 + 主线研究计划（绿-2） |
| SRS 3.1 修正案 | `docs/PyTutor_SRS_3.1_Security_Robustness_Amendment.docx` | 安全/稳健性/评测完整性修正 |

## 9. 下一步

按 `PyTutor_Ideas_and_Research_Plan.md` §1.9 推进顺序：
- [ ] 真置信度（替换硬编码 0.85/0.5）
- [ ] 第 1 层错误大类检测（读 stderr 报错类型）
- [ ] 权重底座（知识点掌握概率 + 衰减）
- [ ] 架桥（误区诊断回流学习路径）
- [ ] 绿-2 科研：AST 符号裁判检验 LLM 解释忠实度

---

## 10. v3.2 对抗性审查整合 (2026-07-09 第二批)

基于 `LOCAL_INTEGRATION_GUIDE.md` + `pytutor-review-deliverables.zip`。

### 应用策略

策略 A（git apply）：三个 diff 均干净应用，无冲突。

### 整合内容

| 类别 | 文件 | 说明 |
|------|------|------|
| 核心补丁 | `ast_analyzer.py` | `_collect_dict_vars` 扩展为六类 dict 来源 + 三个判据函数 |
| | `ast_visitors.py` | M8 条件变量排除 Call.func + 内置白名单；M8 场景2 任一更新即豁免；M6 `_looks_like_computation` 护栏 |
| | `chat_service.py` | F2 时序修复：record 延后到查历史之后（先读后写） |
| 对抗测试 | `test_ast_adversarial_v31.py` | 26 项（M4 dict 豁免/M6 展示豁免/M8 修正/正例回归） |
| 研究原型 | `research/faithfulness/` | R2 AST 符号裁判 + 忠实度验证器 + 实验脚本 |
| 评测探针 | `evaluation/adversarial_probe.py` | 对抗样本自动探针 |
| | `evaluation/verify_fixes_probe.py` | 修复验证探针 |
| 文档 | `B-AST-implementation-v3.2-addendum.md` | v3.2 设计增补 |
| | `PyTutor_SRS_3.2_Adversarial_Amendment.docx` | SRS 3.2 对抗性修正案 |
| | 审查日志 + Debug 日志 | 实现 + Debug 记录 |

### 验证

```bash
pytest test_ast_analyzer.py test_ast_adversarial_v31.py -v  # ✅ 74 passed (0 regression)
时序断言                                                     # ✅ progressive_hint → concept_explanation
```

### 分支

`integrate/adversarial-review-v3.2` → 待用户确认后合并回 main。

---

## 11. SRS 3.2 补充件整合 (2026-07-09 第三批)

基于 `srs32-supplement-impl.zip` + `docs/PyTutor_SRS_3.2_Supplement_II_Borrowed_Ideas_Design.docx`。

### 整合文件

| 文件 | 说明 |
|------|------|
| `backend/app/analysis/confidence.py` | 近似置信度引擎（log-odds 累加，替换硬编码 0.85/0.5） |
| `backend/app/services/prompts/misconception_anchored.py` | 误区锚定提示 + 答案泄露检测 |
| `backend/evaluation/faithfulness/eval_sample.py` | EvalSample schema + 许可证闸门 + 覆盖面报告 |
| `backend/evaluation/faithfulness/mcmining_import.py` | McMining 数据集导入器 |
| `backend/evaluation/dict_harness/pytutor_adapter.py` | TRAVER 评测台适配器 |
| `backend/tests/test_srs32_supplement.py` | 24 项补充单测 |
| `docs/PyTutor_SRS_3.2_Supplement_II_Borrowed_Ideas_Design.docx` | 补充 II 设计文档 |

### 验证

```bash
pytest test_ast_analyzer.py test_ast_adversarial_v31.py test_srs32_supplement.py -q
# ✅ 98 passed (48 + 26 + 24)
```

### 待本地对齐（>>> 本地对齐点 <<<）

| 对齐点 | 位置 | 说明 |
|--------|------|------|
| McMinerLoader._parse_record() | `mcmining_import.py` | 需 McMining 原始数据 `--dry-run` 探查真实字段名 |
| TraverTutorShim | `pytutor_adapter.py` | 需 TRAVER `run_traver.sh` 的 tutor 注入点 |
| confidence.py TODO | `from_visitor_finding()` | 各 visitor 需补出 `ast_features` + `heuristic_only` 键 |
| confidence.py CALIBRATION | `fit_weights()` | 需 >=200 条人工标注后才能校准 |


## 12. SRS 3.2 E 方向整合 (2026-07-10)

基于 `pytutor-srs32-impl.zip`。

### 新增文件

| 文件 | 说明 | SRS |
|------|------|-----|
| `backend/app/analysis/error_class.py` | 三层诊断第1层（读stderr报错大类） | E-FR-02 |
| `backend/app/analysis/root_cause.py` | 薄根因层（数据驱动，严禁写死） | E-FR-04 |
| `backend/app/services/pedagogy/steering.py` | 教学转向状态机 | E-FR-01 |
| `backend/app/services/pedagogy/transition_graph.yaml` | 转向图配置 | E-FR-01 |
| `backend/tests/test_e_direction.py` | 30项E方向单测 | S4.3 |
| `docs/SRS_3.2_gaps_found_during_implementation.md` | 实现中发现5处SRS设计缺口 | -- |

### 关键修复

| 修复 | 说明 |
|------|------|
| Windows `/tmp` -> `tempfile.gettempdir()` | 跨平台修复 |
| 缺口2: `entry_on_misconception` | 首次误区自动以productive_failure为起点 |
| 缺口3: attempt=2空洞 | first_time语义放宽为attempt<3 |
| 缺口4: 超时/被杀隐形 | classify_error增加`not ran_ok -> runtime_other`分支 |

### 验证

```bash
pytest test_ast_analyzer.py test_ast_adversarial_v31.py test_srs32_supplement.py test_e_direction.py -q
# ✅ 128 passed (48 + 26 + 24 + 30)
```

### 分支

`integrate/adversarial-review-v3.2` 累积所有整合。
