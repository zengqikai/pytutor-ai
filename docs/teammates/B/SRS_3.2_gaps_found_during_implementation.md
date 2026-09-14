# SRS 3.2 设计缺口备忘（实现过程中发现）

> 以下 5 处不是实现走样，是 SRS 3.2 自身的设计缺口。前 3 处会导致 §4.3 / R2 的
> 验收判定**不可能为真**，建议回填正文。

---

## 缺口 1 · §5.2 EvalSample 缺 `category` 字段 → R2 无法执行

**问题.** §5.2 的 schema 是 `{code, language, mc_labels, ast_evidence, source, license}`，
没有区分正例与硬负例的字段。而 R2（对抗负例假阳性研究，标为「推荐必做」）的
全部内容就是「加入结构接近误区但完全正确的 hard negatives」。

没有 `category`，hard negative 只能靠 `mc_labels == []` 隐式表达。这会撞上
第二个问题：普通正确代码与「刻意构造的、结构接近误区的」正确代码在统计上是
两类东西——前者是背景，后者才是测 precision 的探针。混在一起，R2 的假阳性率
就失去意义。

**实现中的处理.** `EvalSample` 增加 `category: positive | hard_negative | clean`。

**建议.** 回填 §5.2：

```
EvalSample = {
  ...,
  "category": "positive|hard_negative|clean",   # R2 必需
  "origin_label": "...",                        # 外部基准原始类目，供审计映射
}
```

**连带的真实 bug.** 早期 `validate()` 要求 `mc_labels` 非空——这会把所有 hard
negative（本就没有误区标签）判为校验失败并丢弃。已修 + 加回归测试。

---

## 缺口 2 · §4.2.1 的转移图无法满足 §4.3 的 E-FR-01 验收判定

**问题.** §4.3 要求「同一学生同一误区**第 1 次** → progressive_hint」。
但 §4.2.1 的示例图里，`progressive_hint` 只能从 `productive_failure` 转入：

```yaml
- {from: productive_failure, when: first_time_misconception, to: progressive_hint}
```

学生第一次提交带误区的代码时，`last_intent` 是 `None`，按 `start: elicit_prediction`
求值只会得到 `elicit_prediction`。**验收判定不可能为真**，除非强制要求学生
先走一次预测环节——但 E-FR-05 是「微机制」，不是必经关卡。

**实现中的处理.** YAML 增加 `entry_on_misconception: productive_failure`：
一旦诊断命中误区，直接以 `productive_failure` 为求值起点。理由是误区的出现
本身即是「有成效地卡住」的证据，不必再要求一次预测。

**建议.** 回填 §4.2.1 的 YAML 示例。

---

## 缺口 3 · `first_time_misconception` 与 `repeated_same_misconception` 之间有空洞

**问题.** 若 `repeated` 定义为 `attempt >= 3`（§4.3 的「第 ≥3 次」），
而 `first_time` 字面理解为 `attempt == 1`，则 **attempt == 2 没有任何规则命中**，
落入未定义行为。§4.2.1 的示例图也没有 `default` 键。

**实现中的处理.**
- `first_time_misconception` 语义定为「尚未达到重复阈值」（attempt < 3），
  attempt=2 仍走渐进提示，只是 `hint_level` 更高。名字沿用 SRS 但语义在
  docstring 里写明。
- YAML 增加 `default:` 键，无规则命中时显式兜底而非静默返回 `None`。

**建议.** 要么把谓词改名为 `below_repeat_threshold`，要么在 §4.2.1 注明其语义。

---

## 缺口 4 · §4.2.2 的 `classify_error` 会让超时/被杀的错误隐形

**问题.** SRS 伪代码：

```python
def classify_error(stderr, ran_ok, output_correct):
    if stderr: return ERROR_CLASS_MAP.get(_last_exc_type(stderr), "runtime_other")
    if ran_ok and output_correct is False: return "logic"
    return None
```

沙箱超时、被 RLIMIT 杀掉、段错误这几种情形下，`stderr` 可能为空且 `ran_ok=False`
→ 返回 `None`。而 E-FR-02 的整个立论是「**M 之外的错误不再隐形**」。
这里恰好让一整类错误隐形了。

**实现中的处理.** 增加分支：`if not ran_ok: return "runtime_other"`。
有 stderr 但解析不出异常类型时（C 层崩溃、沙箱杀进程信息）同样返回 `runtime_other`
而非 `None`——归不了类也要留痕。

**另一处.** `_last_exc_type` 必须取**最后一个**异常。异常链
（`During handling of the above exception...`）会打印多个，真正终结程序的是最后那个。
取第一个会把 `KeyError` 当成结论，而实际是 `TypeError`。已加测试钉死。

---

## 缺口 5 · 编号漂移（无害，但会影响引用）

早期交付文档把忠实度主线称作 **R2**，SRS 3.2 定为 **R1**（R2 是对抗负例子实验）。
以 SRS 3.2 为准。本包内代码注释已统一到 R1/R2 的 SRS 定义。

---

## 附：§4.2.4 的「严禁写死」如何在代码里落实

SRS 说根因映射「是假设，严禁写死」。这是一句话，注释里写它不会在 CI 里失败。
实现中把它变成一道闸门：

- `activate()` 只装入**通过共现验证**的假设（lift ≥ 1.5 且 support ≥ 20，
  且样本总量 ≥ 200）；
- 多症状假设要求**每一对**症状都通过，而非平均通过——三个症状里两个同根、
  一个不同根，整条假设就是错的；
- 单症状假设（`state_over_loop → [M8]`）无共现可验，视为结构性成立。
  这不是放水：它没有主张任何两个症状同根，因此没有可被证伪的内容；
- 想跳过验证只能显式传 `force=True`，且会打 WARNING。

自检输出印证了这道闸门有效：给定 `M3∧M6` 显著共现、`M4∧M5` 几乎不共现的数据，
`off_by_boundary` 被数据否决，权重为空。
