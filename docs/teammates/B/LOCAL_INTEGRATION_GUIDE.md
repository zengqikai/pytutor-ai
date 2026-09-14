# PyTutor 本地整合说明（供 Claude Code 执行）

> 用途：把对抗性审查交付包 `pytutor-review-deliverables/` 整合进本地 PyTutor 仓库。
> 使用方式：把本文件放到仓库根目录，连同解压后的交付包一起，然后对本地 Claude 说：
> **"请严格按 LOCAL_INTEGRATION_GUIDE.md 执行整合，每个阶段完成后向我汇报验证结果。"**

---

## 0. 前置条件（Claude 先自检，任一不满足则停下询问用户）

1. 当前目录是 PyTutor 仓库根目录，存在 `backend/app/analysis/ast_analyzer.py`、`backend/app/analysis/ast_visitors.py`、`backend/app/services/chat_service.py`。
2. 交付包已解压，路径为 `./pytutor-review-deliverables/`（若在别处，先记下实际路径并全程替换）。
3. 仓库是 git 管理的，且工作区干净（`git status` 无未提交改动）。若不干净，先让用户决定是提交、暂存（stash）还是放弃。
4. Python ≥ 3.10，能运行 `pytest`；若缺 `structlog`/`pytest`，按 `requirements.txt` 安装（正式环境不需要审查时用的占位 shim）。

## 1. 建立安全网（必做）

```bash
git checkout -b integrate/adversarial-review-v3.2
git tag pre-integration-backup
```

所有整合都在这个分支上做。任何阶段出问题，用 `git reset --hard pre-integration-backup` 回滚。

## 2. 整合三个核心补丁（二选一策略）

涉及文件：
- `backend/app/analysis/ast_analyzer.py`（M4 dict 来源扩展）
- `backend/app/analysis/ast_visitors.py`（M8 条件变量修复、M8 场景 2 豁免、M6 计算意图护栏）
- `backend/app/services/chat_service.py`（F2 时序：误区事件记录延后到查历史之后）

### 策略 A（首选）：应用 diff

```bash
git apply --check pytutor-review-deliverables/patches_ast_analyzer.diff
git apply --check pytutor-review-deliverables/patches_ast_visitors.diff
git apply --check pytutor-review-deliverables/patches_chat_service.diff
```

三个 `--check` 全部通过 → 去掉 `--check` 逐个正式应用。
注意：diff 的路径前缀可能是审查环境的绝对路径，若 apply 报路径错误，先用 `git apply -p<N>` 调整剥离层级，或用 `--directory` 指定，不要手改 diff 内容。

### 策略 B（diff 冲突时）：以补丁文件为基准手动合并

若 `--check` 失败（说明本地代码在审查快照之后有改动）：

1. **不要**直接用交付包里的整文件覆盖本地文件（会丢失本地新改动）。
2. 逐文件做三方对比：本地版本 vs 交付包版本（`pytutor-review-deliverables/backend/...` 下的对应文件）vs diff。
3. 按 `docs/implementation/B-AST-implementation-v3.2-addendum.md` 中的设计意图，把以下改动点手工移植进本地文件：
   - `ast_analyzer.py`：`_collect_dict_vars` 扩展为识别六类 dict 来源（字面量、`dict()`、字典推导式、返回 dict 的函数、`d: dict` 注解、dict 形参名启发式），并新增 `_expr_is_dict`、`_annotation_is_dict`、`_param_name_looks_dict` 三个判据函数。
   - `ast_visitors.py`：`M8WhileInfiniteVisitor._extract_condition_vars` 排除处于 `Call.func` 位置的名字与内置函数白名单；M8 场景 2 改为"任一条件变量在体内被更新即豁免"；`M6PrintReturnVisitor` 新增 `_looks_like_computation` 护栏，展示/入口函数名（main、menu、show、display 等）一律豁免。
   - `chat_service.py`：把 `record_misconception_event` 从诊断后（原步骤 4.5）移到 `get_misconception_history_count` + `select_strategy` 之后（先读后写）。
4. 移植时保留本地文件里补丁未涉及的所有其他改动。

## 3. 复制新增文件（不覆盖已有文件）

```bash
# 对抗测试
cp pytutor-review-deliverables/backend/tests/test_ast_adversarial_v31.py backend/tests/

# R2 研究原型
mkdir -p research
cp -r pytutor-review-deliverables/research/faithfulness research/

# 审查证据脚本
mkdir -p evaluation
cp pytutor-review-deliverables/evaluation/adversarial_probe.py \
   pytutor-review-deliverables/evaluation/verify_fixes_probe.py \
   pytutor-review-deliverables/evaluation/README.md evaluation/ 2>/dev/null || true

# 文档与日志
cp pytutor-review-deliverables/docs/PyTutor_SRS_3.2_Adversarial_Amendment.docx docs/
mkdir -p docs/implementation docs/logs/implementation docs/logs/debug
cp pytutor-review-deliverables/docs/implementation/B-AST-implementation-v3.2-addendum.md docs/implementation/
cp pytutor-review-deliverables/docs/logs/implementation/2026-07-09-B-AST-adversarial-and-R2.md docs/logs/implementation/
cp pytutor-review-deliverables/docs/logs/debug/2026-07-09-B-AST-adversarial-review-debug.md docs/logs/debug/
```

规则：若目标位置已存在同名文件，停下询问用户，不要静默覆盖。
`evaluation/` 下若本地已有 `README.md`，改为追加一节而不是替换。

## 4. 验证（三步全过才算整合成功）

```bash
# A) 回归 + 对抗：应为 48 + 26 = 74 项全过、0 回归
export PYTHONPATH=backend        # Windows: set PYTHONPATH=backend
pytest backend/tests/test_ast_analyzer.py backend/tests/test_ast_adversarial_v31.py -v

# B) F2 时序断言
python -c "from app.services.pedagogy_service import select_strategy as s; \
assert s('M3',1,False)['strategy']=='progressive_hint'; \
assert s('M3',3,True)['strategy']=='concept_explanation'; print('时序 OK')"

# C) R2 原型可运行
cd research/faithfulness
python ast_facts.py
python faithfulness_verifier.py
python run_experiment.py --demo
cd ../..
```

判定标准：
- A 中原有 48 项测试一项不能挂（挂了说明合并引入回归，回到第 2 步策略 B 重查）；26 项对抗测试全过。
- B 输出"时序 OK"。
- C 的 `--demo` 能产出 C1/C2 忠实度对比且 C2 > C1。

补充冒烟测试（如果本地能起服务）：启动 backend，走一次真实对话链路，确认误区诊断 → 首次命中返回 progressive_hint 策略，且 `misconception_events` 表中事件正常入库。

## 5. CI 纳入（可选但推荐）

若存在 `.github/workflows/ci.yml`，把 `backend/tests/test_ast_adversarial_v31.py` 加进测试命令，防止假阳性修复被后续提交回退。

## 6. 提交

验证全过后：

```bash
git add -A
git commit -m "integrate adversarial review v3.2: fix M4/M6/M8 false positives + F2 ordering; add adversarial tests + R2 faithfulness prototype + SRS 3.2"
```

然后向用户汇报：应用了哪种策略（A/B）、每个验证步骤的实际结果、以及是否有停下询问过的冲突点。合并回主分支的决定留给用户。

## 7. 已知边界（整合时不要"顺手修"）

以下是审查中明确"留出"的长尾工程，**不属于本次整合范围**，遇到相关代码不要改动，除非用户另行要求：
- D-FR-03 subprocess RLIMIT、D-FR-11 数据权利端点、F6 `chat_messages.degraded` 落库、D-EVAL-01 渗透测试。
- `evaluation/v2_eval_results.json` 的旧指标（0.96 / 0.974）不要写进任何对外材料，重测前保持原样即可（SRS 3.2 B-EVAL-11）。

## 8. 故障排查速查

| 症状 | 处理 |
|---|---|
| `git apply` 路径不匹配 | 调 `-p` 层级或 `--directory`；仍失败转策略 B |
| 原有 48 测试出现回归 | 合并引入问题，回滚该文件，按增补文档逐改动点重新移植 |
| 对抗测试个别失败 | 对照 `docs/logs/debug/` 中对应簇的根因分析，检查该改动点是否漏移植 |
| `import structlog` 失败 | `pip install -r backend/requirements.txt`，不要用审查时的占位 shim |
| `run_experiment.py` 报无 LLM 凭据 | 正常，加 `--demo` 即为离线桩模式；真实实验需在 `build_llm()` 接入模型 |
