"""
Multi-Judge 评分服务 (C 方向 Task 1 + Task 2)
===============================================

基于 LLM-as-a-Judge 文献实现的 3 评委教学回复质量评估系统。

Task 1 (2026-07-27): 基础 Multi-Judge 框架
Task 2 (2026-07-27): Rubric 细化 — 行为锚定 + Few-shot 校准 + CoT + 证据锚定

核心设计决策（文献依据）：
1. **3 评委制**：文献表明单评委 Kappa 仅 0.3-0.5，3 评委中位数可达 0.7+
   - 同一模型，不同 temperature (0.1/0.5/0.9) → 避免 self-enhancement bias
2. **中位数聚合**：RoPoLL (Acharya 2026) 证明几何中位数优于算术平均
3. **行为锚定 Rubric (Task 2)**：每级用可观测行为定义，非抽象描述
   - Rulers (2025): rubric 应作为可执行规范，非灵活自然语言建议
   - 文献：边界示例 (borderline examples) 是降低方差的最强单一手段
4. **Few-Shot 校准 (Task 2)**：嵌入 3 个已评分示例 (高/中/低)
   - 文献：校准示例可提升 judge-human agreement 10-30%
5. **Chain-of-Thought (Task 2)**：评委先推理后评分，降低 10-25% 方差
   - 推理链即审计轨迹，可供后续人工抽查
6. **证据锚定 (Task 2)**：每维评分必须引用 AI 回复原文
   - Rulers: 高分在机械上不可能缺乏可验证证据
7. **误区特定指导 (Task 2)**：每种 M1-M8 有独立的教学质量评判标准
   - Phung et al. (2025): 泛用 rubric 34.5% 案例与学生感知不匹配

参考文献：
- Shi et al. (2025) "Towards a Human-in-the-Loop Framework" (Kappa 0.75)
- Acharya et al. (2026) "RoPoLL: Robust Panel of LLM Judges"
- Rao & Callison-Burch (2026) "Agreement Metrics for LLM-as-Judge Evaluation"
- Zheng et al. (2024) "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena"
- Phung et al. (2025) "Bridging Gaps Between Student and Expert Evaluations"
- Rulers (2025) "Locked Rubrics and Evidence-Anchored Scoring"
- FutureAGI (2026) "Few-Shot Calibration" & "LLM Judge Prompt Engineering Guide"

作者: clt (C 方向)
日期: 2026-07-27 (Task 1) / 2026-07-27 (Task 2 增强)
"""

import asyncio
import json
import re
import statistics
import time
from dataclasses import dataclass

from app.core.config import settings
from app.observability.logger import get_logger

logger = get_logger(__name__)

# 单个评委调用的超时（秒）
JUDGE_TIMEOUT_SECONDS = 30.0

# =============================================================================
# 5 维教学回复质量 Rubric V2 — 行为锚定增强版 (C 方向 Task 2)
# =============================================================================
#
# 改进点 (vs V1):
# 1. 每级用可观测行为定义，消除"基本遵循""部分适合"等模糊词
# 2. 要求 Chain-of-Thought：先引用证据 → 推理 → 再给分
# 3. 每维评分必须引用 AI 回复原文片段作为依据
# 4. 新增 CANNOT_ASSESS 选项处理边界情况

JUDGE_RUBRIC_V2 = """你是一位 Python 编程教学质量评估专家。请对以下 AI 助教的回复进行五维评分。

## 评估方法（必须严格遵循）

**第一步：逐维分析**。对每个维度：
1. 从 AI 回复中**摘录原文片段**作为证据（用引号标注）
2. 分析该证据说明了什么
3. 对照下方的行为锚定描述，确定最匹配的分数

**第二步：综合评分**。填写 JSON 输出。

## 评分维度与行为锚定

### D1. 提示等级遵循度 (Hint Level Adherence)
当前要求等级: Level {expected_hint_level}/5
（1=概念提示 2=方向提示 3=位置提示 4=部分代码 5=完整参考）

行为锚定：
- 5分: 回复信息量精确匹配要求等级。
  Level 1→只提概念名，不涉代码 | Level 2→指出方向但无行号/代码 | Level 3→指出具体行但无正确代码 | Level 4→给关键片段但保留缺口 | Level 5→给完整方案+解释
- 4分: 信息量接近要求等级，存在 1 处可容忍偏差（如 Level 2 说了"第3行"但不严重）
- 3分: 信息量明显偏离要求，但幅度有限（如 Level 1 给了方向，或 Level 4 给了几乎完整答案）
- 2分: 严重越级（Level 1 给了代码片段）或严重不足（Level 5 只给了概念提示）
- 1分: 完全无视等级（Level 1 直接给完整代码答案，或 Level 5 回复"自己想"）

### D2. 初学者适配度 (Beginner Appropriateness)
目标受众: Python 初学者（可能不知道"参数""返回值""迭代"等术语）

行为锚定：
- 5分: 所有术语都有解释或用类比替代（如"参数就像函数的'输入材料'")。句子短（≤20字/句），无嵌套从句。使用生活类比而非计算机概念。
- 4分: 大部分术语有解释，偶尔用了未解释的术语（1-2个）但不影响理解。
- 3分: 术语偏多（3-5个未解释），但整体仍可理解。可能需要学生自行查阅。
- 2分: 大量未解释术语（6+），或句子结构复杂，初学者需要反复阅读才能理解。
- 1分: 满篇专业术语 + 复杂句式，完全不适合初学者。或使用了嘲讽/居高临下的语气。

### D3. 无答案泄露 (No Answer Leakage)
核心原则: 学生应自己思考和修改，而非直接得到答案。

行为锚定：
- 5分: 回复纯引导。使用"你注意到...？""试试把...和...对比看看""如果...会发生什么？"等句式。没有任何代码或具体实现方向。
- 4分: 给了概念方向或类比，但没有可复制粘贴的代码。学生仍需自己思考如何实现。
- 3分: 给了具体概念解释（如"需要用 return 而不是 print"），但未给代码。学生知道改什么但不知道具体怎么写。
- 2分: 给了伪代码或接近可直接使用的代码片段。学生稍作修改即可通过。
- 1分: 给了完整可运行的代码答案。学生复制粘贴即通过，零思考。

### D4. 误区针对性 (Misconception Targeting)
目标误区: {misconception_name}

行为锚定：
- 5分: 精确定位误区并解释了**为什么**会产生这个错误认知（根因）。例如对 M3 不仅说"append 返回 None"，还解释"初学者常以为修改列表的方法会返回修改后的列表"。给出了具体的认知纠正路径。
- 4分: 正确定位误区并解释了现象，但未解释为什么学生会这样想。纠正是基于规则（"Python 就是这样设计的"）而非认知。
- 3分: 提到了相关概念（如"列表方法"），但与具体误区的关联不够紧密。学生可能不清楚这和自己的错误有什么关系。
- 2分: 只指出了语法/表面问题（如"这里有个错误"），未关联到具体的认知误区类型。
- 1分: 回复内容与目标误区完全无关，或给出了关于误区的错误信息。

### D5. 可操作性 (Actionability)
学生读完回复后，应该明确知道自己接下来该做什么。

行为锚定：
- 5分: 包含明确、可立即执行的下一步动作 + 验证方法。例："试试把第3行的 = 改成 ==，然后运行。看输出是否变成你期望的'five'。"
- 4分: 有下一步建议，但缺少验证方法。学生知道做什么但不知道如何确认做对了。
- 3分: 建议比较模糊，如"再想想""多练习"。学生不知从何入手。
- 2分: 只说了有什么问题，没说怎么办。
- 1分: 完全没有下一步指引，学生读完仍然迷茫。

## CANNOT_ASSESS 规则

遇到以下情况，将对应维度标记为 CANNOT_ASSESS：
- 回复太短（< 20 字）无法评判 → 该维填 0，issues 注明"Cannot assess: response too short"
- 回复与教学完全无关（如闲聊、问候）→ 该维填 0，issues 注明"Cannot assess: off-topic"
- CANNOT_ASSESS 的维度不参与 total/overall 计算。所有维度都是 CANNOT_ASSESS → overall = 0

## 评估对象

- AI 回复:
{ai_message}

## 输出格式

严格按以下 JSON 格式输出。先推理后出结果。

```json
{{
  "reasoning": {{
    "D1": "证据：「...」→分析→分数理由",
    "D2": "证据：「...」→分析→分数理由",
    "D3": "证据：「...」→分析→分数理由",
    "D4": "证据：「...」→分析→分数理由",
    "D5": "证据：「...」→分析→分数理由"
  }},
  "scores": {{
    "D1_hint_adherence": <0-5, 0=CANNOT_ASSESS>,
    "D2_beginner_appropriate": <0-5>,
    "D3_no_leakage": <0-5>,
    "D4_misconception_target": <0-5>,
    "D5_actionability": <0-5>
  }},
  "total": <0-25, CANNOT_ASSESS 的维度不计入>,
  "overall": <0-5, 基于有效维度的归一化分数>,
  "issues": ["具体问题描述"],
  "needs_revision": <true/false>,
  "cannot_assess_reason": "<如果有 CANNOT_ASSESS 维度，说明原因；否则为空字符串>",
  "brief_reason": "一句话总结评分理由"
}}
```"""

# 误区 ID → 中文名映射 (V2: 增加典型错误行为描述)
MC_NAMES: dict[str, str] = {
    "M1": "赋值与比较混淆 (if x = 3: — 把 = 当 == 用)",
    "M2": "缩进理解错误 (缺少缩进 — Python 用缩进表示代码块)",
    "M3": "append/返回值误解 (变量=None — 以为修改方法返回新对象)",
    "M4": "index/value 混淆 (用元素当下标 — for 循环中混淆了值和索引)",
    "M5": "range 右边界误解 (以为包含右边界 — range(1,5) 期望到 5)",
    "M6": "print/return 混淆 (只打不返 — 函数用 print 而不是 return)",
    "M7": "类型转换错误 (string + int — 不同类型不能直接运算)",
    "M8": "while 循环条件错误 (无限循环 — 忘记在循环体内改变条件)",
}

# =============================================================================
# 误区特定教学指导 (Task 2: Per-Misconception Rubric Addendum)
# =============================================================================
# Phung et al. (2025): 泛用 Rubric 在 34.5% 案例中与学生感知不匹配。
# 每种 M 有独立的"好教学"标准，评委需据此调整 D4 评分基准。

PER_MC_GUIDANCE: dict[str, str] = {
    "M1": """M1 特定评判标准（赋值与比较混淆）:
- 好教学: 引导学生发现 = 和 == 的语义差异（赋值 vs 比较），用 if 条件表达式举例
- 差教学: 直接说"把 = 改成 =="，不给概念解释
- 注意: Level 1-2 只能提"条件表达式里需要比较而非赋值"，不能给 == 这个符号""",

    "M2": """M2 特定评判标准（缩进理解错误）:
- 好教学: 解释缩进是 Python 表示"属于"关系的方式（如"循环体 = 要重复做的事"），
  用"想象一个大括号"类比帮助理解
- 差教学: 只说"加 4 个空格"，不解释为什么
- 注意: 缩进是初学者最大痛点之一，应特别关注 D2（初学者适配度）""",

    "M3": """M3 特定评判标准（append/返回值误解）:
- 好教学: 区分"修改原对象的方法"和"返回新对象的方法"。用对比示例：
  list.append(x) 返回 None（改原列表）vs sorted(list) 返回新列表
- 差教学: 只说"sort()返回 None，用 sorted()"，不解释为什么有两种设计
- 注意: M3 是关键拐点——理解可变对象就地修改 vs 返回新对象，是 Python OOP 基础""",

    "M4": """M4 特定评判标准（index/value 混淆）:
- 好教学: 用具体数值演示 for i in list 的 i 是元素而非下标。
  让学生 print 循环变量来"亲眼看到"它是什么
- 差教学: 只说"不要用 list[i]，用 i"，不解释为什么
- 注意: 这是概念性错误——学生可能不区分"列表的值"和"值的位置"，需耐心引导""",

    "M5": """M5 特定评判标准（range 右边界误解）:
- 好教学: 用"从 start 开始，到 stop 之前停止"或"range(n)产生 0 到 n-1 共 n 个数"
  等非技术类比解释。鼓励学生用 list(range(...)) 可视化 range 的结果
- 差教学: 只说"range 不包含右边界"，用技术术语解释技术术语
- 注意: M5 常与 M4 并发——在 range 配合 for 循环时同时出现两种误区""",

    "M6": """M6 特定评判标准（print/return 混淆）:
- 好教学: 用"打印到屏幕 vs 交给调用者"的对比（print 是"展示"，return 是"交出"）。
  建议学生做实验：有 return 和无 return 的函数调用结果对比
- 差教学: 只给 return 的代码，不解释 print vs return 的语义差异
- 注意: 这是函数式思维的门槛，一旦理解对后续学习影响巨大""",

    "M7": """M7 特定评判标准（类型转换错误）:
- 好教学: 解释不同类型像不同的"单位"（厘米 vs 米），不能直接加减。
  引导学生用 type() 函数查看变量类型来培养调试习惯
- 差教学: 直接给 int() 或 str() 的转换代码，不说为什么
- 注意: 类型系统是所有编程语言的基础概念，打好基础后续受益""",

    "M8": """M8 特定评判标准（while 循环条件错误）:
- 好教学: 引导学生画出循环的三要素：（1）初始条件（2）循环体内必须改变条件
  （3）终止条件。用生活类比（如"倒计时"）帮助可视化
- 差教学: 直接说"加 n += 1"，不解释为什么需要改变条件
- 注意: 无限循环是初学者最常见的运行时问题，教学时应侧重"为什么循环不会自己停"这一概念""",
}

# =============================================================================
# Few-Shot 校准示例 (Task 2: Behavioral Anchor Calibration)
# =============================================================================
# 文献：校准示例可提升 judge-human agreement 10-30%。
# 选择策略：高分/中分/低分各一例，覆盖"边界"——教评委分值边界在哪。
# 这些示例是精心构造的"锚"，每个分数都有明确的 evidence 关联。

FEW_SHOT_EXAMPLES = """
## 评分校准示例（请仔细学习以下评分基准）

### 示例 1 — 应得高分 (overall=4)

AI 回复: "你写的 `for i in range(1, 5)` 思路是对的！但我注意到你说'为什么只到 4'——这是因为 Python 的 range 有一个规则：它包含开始的数，但不包含结束的数。你现在的困惑很常见，很多初学者都会以为 range(1,5) 应该包含 5。你能想出一个生活中的例子，也是'包含开始但不包含结束'吗？试试用 `print(list(range(1, 5)))` 来验证你的理解——这会直接显示 range 实际产生的数字。"
期望等级: Level 2

- D1 (Hint Adherence): 5分 — 证据：「你能想出一个例子吗？」「试试用...来验证你的理解」→ 纯引导式提问 + 验证工具，没有给代码答案，完美匹配 Level 2。
- D2 (Beginner): 5分 — 证据：「包含开始的数，但不包含结束的数」→ 用日常语言解释，没有术语堆砌。
- D3 (No Leakage): 4分 — 证据：给了 `print(list(range(1, 5)))` 作为验证工具 → 给了一个 debug 技巧，但没有告诉学生"把 5 改成 6"这个答案。学生仍需自己推断出解决方案。扣 1 分因为给出了可复制的代码片段。
- D4 (Misconception): 5分 — 证据：「很多初学者都会以为 range(1,5) 应该包含 5」→ 不仅指出了误区，还肯定了学生的困惑是正常的，减少了挫败感。
- D5 (Actionability): 5分 — 证据：「试试用 print(list(range(...))) 来验证」「你能想出一个例子吗」→ 2 个明确的下一步行动 + 验证方法。

### 示例 2 — 应得中分 (overall=2)

AI 回复: "你的代码缩进有问题。在 Python 里 for 循环下面要缩进 4 个空格。正确写法是 for i in range(3):\\n    print(i)。你改一下试试。"
期望等级: Level 2

- D1 (Hint Adherence): 2分 — 证据：「正确写法是 for i in range(3):\\n    print(i)」→ Level 2 不应该给完整代码答案，严重越级。
- D2 (Beginner): 3分 — 证据：「缩进 4 个空格」→ 用了术语但简单解释了。但缺少对"为什么需要缩进"的概念解释。
- D3 (No Leakage): 1分 — 证据：直接给出了正确的完整代码 → 学生复制粘贴即可通过。
- D4 (Misconception): 2分 — 证据：只说了"缩进有问题"和怎么改 → 未解释缩进在 Python 中表示"代码块归属"的认知概念。
- D5 (Actionability): 2分 — 证据：「你改一下试试」→ 太模糊，没有具体的验证方法。

### 示例 3 — 应得低分 (overall=1)

AI 回复: "你的代码有问题，去查一下 Python 文档。"
期望等级: Level 2

- D1 (Hint Adherence): 1分 — 证据：全文 13 个字 → 对于 Level 2，给的信息严重不足。相当于什么都没说。
- D2 (Beginner): 1分 — 证据：「查一下 Python 文档」→ 对初学者来说这是不可能的任务（不知道查什么、在哪查、怎么看）。
- D3 (No Leakage): 5分 — 证据：全文无代码 → 虽然完全没泄题…但这只是因为什么都没说。
- D4 (Misconception): 1分 — 证据：没有提到任何与误区相关的内容 → 完全无效的回复。
- D5 (Actionability): 1分 — 证据：没有具体的下一步 → 比"再想想"还模糊。
"""


def _build_judge_prompt(
    ai_message: str,
    expected_hint_level: int,
    misconception_id: str | None,
) -> str:
    """
    组装完整的评委 prompt（Rubric V2 + 误区指导 + Few-shot 校准）。

    参数:
        ai_message: AI 回复
        expected_hint_level: 期望提示等级
        misconception_id: 误区 ID

    返回:
        str: 完整 prompt
    """
    misconception_name = MC_NAMES.get(misconception_id or "", "无特定误区")

    # 基础 Rubric
    prompt = JUDGE_RUBRIC_V2.format(
        expected_hint_level=expected_hint_level,
        misconception_name=misconception_name,
        ai_message=ai_message[:1200],
    )

    # 误区特定指导（如果有对应 M）
    if misconception_id and misconception_id in PER_MC_GUIDANCE:
        prompt += "\n\n" + PER_MC_GUIDANCE[misconception_id]

    # Few-shot 校准示例
    prompt += "\n\n" + FEW_SHOT_EXAMPLES

    # 结尾提醒
    prompt += """

---
**重要提醒**:
1. 先按「证据→分析→分数」三步法推理，再填 JSON
2. 每维评分必须基于 AI 回复原文，不能凭感觉
3. 注意区分「回复本身质量」和「回复是否满足教学要求」——两者可能不同
4. 如果回复短到无法评判某维度，填 0 (CANNOT_ASSESS)
5. 只输出 JSON，不要任何额外文字
"""

    return prompt


# 3 评委的 temperature 配置（同模型，不同温度 → 多样性）
JUDGE_TEMPERATURES = [0.1, 0.5, 0.9]


# =============================================================================
# 数据结构
# =============================================================================

@dataclass
class JudgeVerdict:
    """单个评委的评分结果 (V2 增强：+reasoning +evidence +cannot_assess)。"""
    judge_index: int
    temperature: float
    scores: dict[str, int]       # D1-D5 各维分数 (0=CANNOT_ASSESS)
    total: int                   # 5-25 (排除 CANNOT_ASSESS)
    overall: int                 # 1-5 归一化
    issues: list[str]
    needs_revision: bool
    brief_reason: str
    reasoning: dict[str, str]    # V2: 每维的「证据→分析→分数」推理链
    cannot_assess: list[str]     # V2: CANNOT_ASSESS 的维度列表
    raw_json: str                # LLM 原始返回（调试用）
    latency_ms: float


@dataclass
class MultiJudgeResult:
    """多评委聚合结果 (V2: +cannot_assess_summary +reasoning_consensus)。"""
    verdicts: list[JudgeVerdict]
    aggregated_score: float       # 中位数 overall (1-5)
    aggregated_total: float       # 中位数 total (5-25)
    scores_detail: dict[str, dict]  # 每维 {median, min, max, range, valid_count}
    needs_revision: bool          # 多数投票
    all_issues: list[str]         # 合并去重
    kappa_inter_judge: float      # Fleiss' Kappa
    agreement_level: str          # "high" | "substantial" | "moderate" | "low"
    flagged_for_review: bool      # 分歧 >1 级，建议人工复核
    cannot_assess_dims: list[str] # V2: 被多个评委标记 CANNOT_ASSESS 的维度
    total_latency_ms: float


# =============================================================================
# 核心：多评委评分
# =============================================================================

async def _single_judge(
    ai_message: str,
    expected_hint_level: int,
    misconception_id: str | None,
    temperature: float,
    judge_index: int,
) -> JudgeVerdict:
    """
    单个评委评分 (V2 增强版)。

    使用行为锚定 Rubric + 误区特定指导 + Few-shot 校准 + CoT + 证据锚定。
    max_tokens 提升至 600 以容纳 CoT 推理链。

    参数:
        ai_message: AI 回复内容
        expected_hint_level: 期望提示等级
        misconception_id: 目标误区 ID
        temperature: LLM temperature
        judge_index: 评委编号 (0-2)

    返回:
        JudgeVerdict: 含推理链 + 证据的完整评分
    """
    from app.services.llm_service import chat_completion
    from app.schemas.ai import ChatMessage

    prompt = _build_judge_prompt(ai_message, expected_hint_level, misconception_id)

    start = time.perf_counter()

    try:
        response = await chat_completion(
            messages=[ChatMessage(role="user", content=prompt)],
            temperature=temperature,
            max_tokens=600,  # V2 增加以容纳 CoT 推理链
        )

        elapsed = (time.perf_counter() - start) * 1000
        raw = response.content.strip()

        # 解析 JSON（从可能的 markdown 代码块中提取）
        json_match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not json_match:
            logger.warning("judge_v2_json_parse_failed",
                           judge_index=judge_index, temp=temperature,
                           raw_preview=raw[:100])
            return _fallback_verdict(judge_index, temperature, elapsed, raw)

        result = json.loads(json_match.group())
        scores_raw = result.get("scores", {})

        # 提取分数（处理 CANNOT_ASSESS = 0 的情况）
        dim_keys = [
            "D1_hint_adherence", "D2_beginner_appropriate",
            "D3_no_leakage", "D4_misconception_target", "D5_actionability"
        ]
        scores: dict[str, int] = {}
        cannot_assess: list[str] = []
        for key in dim_keys:
            val = int(scores_raw.get(key, 3))
            if val == 0:
                cannot_assess.append(key)
            scores[key] = val

        # 推理链（V2 新增）
        reasoning_raw = result.get("reasoning", {})
        reasoning: dict[str, str] = {}
        for dim_short in ["D1", "D2", "D3", "D4", "D5"]:
            reasoning[dim_short] = reasoning_raw.get(dim_short, "")

        return JudgeVerdict(
            judge_index=judge_index,
            temperature=temperature,
            scores=scores,
            total=int(result.get("total", 15)),
            overall=int(result.get("overall", 3)),
            issues=result.get("issues", []),
            needs_revision=result.get("needs_revision", False),
            brief_reason=result.get("brief_reason", ""),
            reasoning=reasoning,
            cannot_assess=cannot_assess,
            raw_json=raw[:800],  # V2: 截断 800 字以保留完整 JSON 结构
            latency_ms=elapsed,
        )

    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        logger.warning("judge_v2_call_failed",
                       judge_index=judge_index, temp=temperature, error=str(e)[:200])
        return _fallback_verdict(judge_index, temperature, elapsed, "")


def _fallback_verdict(
    judge_index: int, temperature: float, latency_ms: float, raw: str
) -> JudgeVerdict:
    """评委调用失败时的降级 verdict（V2: 保守全 3 分，标记异常）。"""
    return JudgeVerdict(
        judge_index=judge_index,
        temperature=temperature,
        scores={k: 3 for k in [
            "D1_hint_adherence", "D2_beginner_appropriate",
            "D3_no_leakage", "D4_misconception_target", "D5_actionability"
        ]},
        total=15,
        overall=3,
        issues=["评委 API 调用失败，使用默认分数"],
        needs_revision=False,
        brief_reason="评委 API 调用失败，自动降级",
        reasoning={dim: "API 调用失败，无推理" for dim in ["D1","D2","D3","D4","D5"]},
        cannot_assess=[],
        raw_json=raw[:200],
        latency_ms=latency_ms,
    )


def _aggregate_verdicts(verdicts: list[JudgeVerdict]) -> MultiJudgeResult:
    """
    聚合多个评委的评分 (V2: 处理 CANNOT_ASSESS 维度)。

    方法：中位数聚合（对标 RoPoLL 的鲁棒聚合策略）
    - overall/total 取中位数（非均值，抗极端值）
    - needs_revision 取多数投票
    - CANNOT_ASSESS 维度：从有效分数中排除（该维分数为 0 时跳过）
    - 各维度分别报 median / min / max / range / valid_count
    - 计算 inter-judge 一致性
    """
    n = len(verdicts)

    # overall 中位数（排除 0 = 完全无法评估的情况）
    overalls = sorted([v.overall for v in verdicts if v.overall > 0])
    totals = sorted([v.total for v in verdicts if v.total > 0])
    if not overalls:
        overalls = [3]
    if not totals:
        totals = [15]
    median_overall = float(statistics.median(overalls))
    median_total = float(statistics.median(totals))

    # needs_revision 多数投票
    revision_votes = sum(1 for v in verdicts if v.needs_revision)
    needs_revision = revision_votes > n / 2

    # 合并 issues（去重 + 保留推理链中的关键问题）
    seen = set()
    all_issues: list[str] = []
    for v in verdicts:
        for issue in v.issues:
            if issue and issue not in seen:
                seen.add(issue)
                all_issues.append(issue)
        # 从 CANNOT_ASSESS 中提取问题
        for ca_dim in v.cannot_assess:
            ca_issue = f"维度 {ca_dim}: 无法评估（回复信息不足或无关）"
            if ca_issue not in seen:
                seen.add(ca_issue)
                all_issues.append(ca_issue)

    # 各维度统计（排除 0 = CANNOT_ASSESS）
    dims = ["D1_hint_adherence", "D2_beginner_appropriate",
            "D3_no_leakage", "D4_misconception_target", "D5_actionability"]
    scores_detail: dict[str, dict] = {}
    for dim in dims:
        vals = sorted([v.scores.get(dim, 3) for v in verdicts if v.scores.get(dim, 0) > 0])
        if not vals:
            # 全部评委标记 CANNOT_ASSESS → 不造假分，报 None
            scores_detail[dim] = {
                "median": None,
                "min": None,
                "max": None,
                "range": None,
                "valid_count": 0,
                "note": "all judges marked CANNOT_ASSESS",
            }
        else:
            scores_detail[dim] = {
                "median": float(statistics.median(vals)),
                "min": min(vals),
                "max": max(vals),
                "range": max(vals) - min(vals),
                "valid_count": len(vals),
            }

    # 检测被多个评委标记 CANNOT_ASSESS 的维度
    ca_count: dict[str, int] = {}
    for v in verdicts:
        for dim in v.cannot_assess:
            ca_count[dim] = ca_count.get(dim, 0) + 1
    cannot_assess_dims = [
        dim for dim, count in ca_count.items() if count >= 2  # 至少 2 个评委一致认为无法评估
    ]

    # 一致性指标
    kappa = _compute_inter_judge_kappa(verdicts)
    # 仅计算有效维度的 range（排除 None = 全 CANNOT_ASSESS 的维度）
    valid_ranges = [d["range"] for d in scores_detail.values() if d["range"] is not None]
    max_range = max(valid_ranges) if valid_ranges else 0
    flagged = max_range > 1  # 任一维度分歧 >1 级 → 人工复核

    # 如果有 CANNOT_ASSESS，也应标记复核
    if cannot_assess_dims and not flagged:
        flagged = True

    if kappa >= 0.75:
        agreement_level = "high"
    elif kappa >= 0.60:
        agreement_level = "substantial"
    elif kappa >= 0.40:
        agreement_level = "moderate"
    else:
        agreement_level = "low"

    total_latency = sum(v.latency_ms for v in verdicts)

    return MultiJudgeResult(
        verdicts=verdicts,
        aggregated_score=median_overall,
        aggregated_total=median_total,
        scores_detail=scores_detail,
        needs_revision=needs_revision,
        all_issues=all_issues,
        kappa_inter_judge=kappa,
        agreement_level=agreement_level,
        flagged_for_review=flagged,
        cannot_assess_dims=cannot_assess_dims,
        total_latency_ms=total_latency,
    )


def _compute_inter_judge_kappa(verdicts: list[JudgeVerdict]) -> float:
    """
    计算评委间一致性 (近似 Fleiss' Kappa) — V2 支持 CANNOT_ASSESS。

    将 0 (CANNOT_ASSESS) 作为独立类别纳入计算，因此类别总数为 6:
    0=CANNOT_ASSESS, 1-5=正常评分。

    注：如果所有评委在所有维度上完全一致 (包括一致的 CANNOT_ASSESS)，
        Kappa 应为 1.0。如果 CANNOT_ASSESS 模式不一致，Kappa 会降低。
    """
    n_judges = len(verdicts)
    if n_judges < 2:
        return 1.0

    dims = ["D1_hint_adherence", "D2_beginner_appropriate",
            "D3_no_leakage", "D4_misconception_target", "D5_actionability"]
    n_subjects = len(dims)  # 5
    # V2: 0 = CANNOT_ASSESS, 1-5 = 正常评分
    n_categories = 6

    # 构建评分矩阵: judges × subjects
    ratings = []
    for v in verdicts:
        row = [v.scores[d] for d in dims]
        ratings.append(row)

    # 每 subject 每 category 的计数
    # 评分 0 → category index 0, 评分 1 → index 1, ...
    n_ij = [[0] * n_categories for _ in range(n_subjects)]
    for i in range(n_subjects):
        for j in range(n_judges):
            score = ratings[j][i]
            # 将 0-5 映射为 category index 0-5
            cat_idx = score  # score 0 → idx 0 (CANNOT_ASSESS), score 5 → idx 5
            if 0 <= cat_idx < n_categories:
                n_ij[i][cat_idx] += 1

    # P_i: 每个 subject 的 within-subject agreement
    P_i = []
    for i in range(n_subjects):
        total = sum(n_ij[i])
        if total <= 1:
            P_i.append(1.0)
            continue
        sum_sq = sum(c * (c - 1) for c in n_ij[i])
        P_i.append(sum_sq / (total * (total - 1)))

    P_bar = sum(P_i) / len(P_i) if P_i else 0.0

    # P_e: 期望 agreement (基于边缘分布)
    n_total = n_subjects * n_judges
    p_j = []
    for cat_idx in range(n_categories):
        col_sum = sum(n_ij[i][cat_idx] for i in range(n_subjects))
        p_j.append(col_sum / n_total)

    P_e = sum(p**2 for p in p_j)

    if P_e >= 1.0:
        return 1.0 if P_bar >= 1.0 else 0.0

    kappa = (P_bar - P_e) / (1.0 - P_e)
    return round(max(-1.0, min(1.0, kappa)), 4)


# =============================================================================
# 公开 API：替代 verify_response 的多评委入口
# =============================================================================

async def multi_judge_verify(
    ai_message: str,
    expected_hint_level: int,
    misconception_id: str | None,
) -> dict:
    """
    Multi-Judge 教学回复质量评估。

    使用 3 个评委（同模型，不同 temperature 0.1/0.5/0.9）独立评分，
    取中位数聚合。每个评委有独立的超时保护。

    参数:
        ai_message: AI 助教的回复内容
        expected_hint_level: 期望的提示等级 (1-5)
        misconception_id: 目标误区 ID (M1-M8) 或 None

    返回:
        dict: {
            "score": float,           # 聚合后的 overall 分数 (1-5)
            "is_valid": bool,         # 是否合格
            "issues": list[str],      # 问题列表
            "needs_revision": bool,   # 是否需要修正
            # Multi-Judge 专有字段
            "judge_count": int,
            "kappa": float,
            "agreement": str,
            "flagged": bool,
            "scores_detail": dict,
            "cannot_assess_dims": list[str],
            "latency_ms": float,
        }
    """
    if not settings.ENABLE_MULTI_JUDGE:
        # 降级路径（理论上不会走到这里，但保底）
        from app.services.pedagogy_service import verify_response as old_verify
        return await old_verify(ai_message, expected_hint_level, misconception_id)

    logger.info("multi_judge_start",
                hint_level=expected_hint_level,
                misconception=misconception_id,
                msg_length=len(ai_message))

    # 启动 3 个评委（并发 + 独立超时保护）
    async def _judge_with_timeout(temp: float, idx: int) -> JudgeVerdict | None:
        try:
            return await asyncio.wait_for(
                _single_judge(ai_message, expected_hint_level, misconception_id,
                              temp, idx),
                timeout=JUDGE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning("judge_timeout", judge_index=idx, temp=temp,
                           timeout_s=JUDGE_TIMEOUT_SECONDS)
            return _fallback_verdict(idx, temp, JUDGE_TIMEOUT_SECONDS * 1000,
                                     "TIMEOUT")
        except Exception as e:
            logger.warning("judge_unexpected_error", judge_index=idx,
                           temp=temp, error=str(e)[:200])
            return _fallback_verdict(idx, temp, 0, f"ERROR: {str(e)[:100]}")

    tasks = [
        _judge_with_timeout(temp, idx)
        for idx, temp in enumerate(JUDGE_TEMPERATURES)
    ]
    verdicts = await asyncio.gather(*tasks)

    # 过滤掉完全失败的（不太可能，但做防御）
    valid_verdicts = [v for v in verdicts if v is not None]

    if len(valid_verdicts) == 0:
        logger.warning("multi_judge_all_failed")
        return {
            "score": 3, "is_valid": True, "issues": ["所有评委调用失败"],
            "needs_revision": False,
            "judge_count": 0, "kappa": 0.0, "agreement": "low",
            "flagged": True, "scores_detail": {}, "latency_ms": 0.0,
        }

    # 聚合
    result = _aggregate_verdicts(valid_verdicts)

    logger.info("multi_judge_done",
                score=result.aggregated_score,
                kappa=result.kappa_inter_judge,
                agreement=result.agreement_level,
                flagged=result.flagged_for_review,
                cannot_assess=result.cannot_assess_dims,
                revision_votes=f"{sum(1 for v in valid_verdicts if v.needs_revision)}/{len(valid_verdicts)}",
                latency_ms=round(result.total_latency_ms, 0))

    # 如果评委分歧大或有 CANNOT_ASSESS，记录详细信息供后续分析
    if result.flagged_for_review:
        logger.info("multi_judge_flagged",
                    kappa=result.kappa_inter_judge,
                    details=result.scores_detail,
                    cannot_assess=result.cannot_assess_dims)

    return {
        "score": result.aggregated_score,
        "is_valid": result.aggregated_score >= 3 and not result.needs_revision,
        "issues": result.all_issues,
        "needs_revision": result.needs_revision,
        # Multi-Judge 专有字段
        "judge_count": len(valid_verdicts),
        "kappa": result.kappa_inter_judge,
        "agreement": result.agreement_level,
        "flagged": result.flagged_for_review,
        "scores_detail": result.scores_detail,
        "cannot_assess_dims": result.cannot_assess_dims,  # V2
        "latency_ms": round(result.total_latency_ms, 0),
    }


# =============================================================================
# 批量评估工具（用于 evaluation/ 脚本中对比单/多评委）
# =============================================================================

async def evaluate_judge_agreement(
    test_cases: list[dict],
    use_multi: bool = True,
) -> dict:
    """
    对评测集跑所有评委，报告一致性指标。并发执行以减少总延迟。

    参数:
        test_cases: [{"ai_message": str, "expected_hint_level": int,
                       "misconception_id": str | None}, ...]
        use_multi: True=多评委, False=单评委（对比基线）

    返回:
        {"per_case": [...], "summary": {"mean_kappa": float, ...}}
    """
    # 创建并发任务
    async def _eval_one(i: int, case: dict) -> dict:
        if use_multi:
            result = await multi_judge_verify(
                case["ai_message"],
                case.get("expected_hint_level", 1),
                case.get("misconception_id"),
            )
        else:
            from app.services.pedagogy_service import verify_response as old_verify
            result = await old_verify(
                case["ai_message"],
                case.get("expected_hint_level", 1),
                case.get("misconception_id"),
            )
        return {"case_index": i, "result": result}

    # 全部案例并发评估
    per_case = await asyncio.gather(*[
        _eval_one(i, case) for i, case in enumerate(test_cases)
    ])

    kappas = [pc["result"]["kappa"] for pc in per_case if "kappa" in pc["result"]]

    return {
        "per_case": per_case,
        "summary": {
            "total_cases": len(test_cases),
            "multi_judge": use_multi,
            "mean_kappa": round(sum(kappas) / len(kappas), 4) if kappas else None,
            "kappa_range": f"{min(kappas):.4f}-{max(kappas):.4f}" if kappas else "N/A",
        },
    }
