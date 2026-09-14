"""
误区锚定提示 (Misconception-Anchored Prompt) —— SRS 3.2 补充 §3 的落地

它借的是什么
------------
MisconceptionTutor（SIGCSE'26 poster，无码）的可借鉴机制只有一条：
把反馈**锚定在已诊断的误区上**，给高层的、针对性的、不泄露答案的提示。

本系统本来就是误区锚定的（有 M1–M8 + AST 诊断），所以这里不是"复现其系统"，
只是把那条约束写成 prompt 的一部分。工作量极小，这也是它被定为 L2 的原因。

为什么答案泄露必须硬约束
------------------------
"不泄露答案"不是礼貌用语，是可被评测的行为。已有的对抗学生基准（2026）证明
学生会主动套答案，而 LLM 在压力下极易屈服。因此：
  - 约束写进 system prompt 的**否定式清单**，而不是"请尽量不要"；
  - 提供 leaks_answer() 做**输出侧检查**，双保险；
  - 置信度低时降级为提问而非断言（避免把错误诊断说得斩钉截铁）。
"""

from __future__ import annotations

import re
from typing import Any


# 误区编号 → 面向学生的高层描述（不含修正代码）
MISCONCEPTION_BRIEF: dict[str, str] = {
    "M1": "把赋值 = 当成了相等判断 ==",
    "M2": "缩进层级与代码块归属的对应关系没有对齐",
    "M3": "以为原地修改的方法（如 append）会返回一个新对象",
    "M4": "把遍历得到的元素值当成了索引下标",
    "M5": "对 range 的左闭右开区间理解有偏差",
    "M6": "把「打印出来」当成了「函数返回值」",
    "M7": "以为 input() 拿到的直接是数字，未做类型转换",
    "M8": "循环的终止条件在循环体内从未被推进",
}


_SYSTEM_TEMPLATE = """你是一位 Python 编程导师，面对的是初学者。

学生的代码命中了误区 {mc_id}：{brief}
诊断置信度：{confidence:.2f}（{confidence_stance}）

请给出锚定该误区的「高层提示」，聚焦两点：
  - 学生**为什么会这样想**（哪个心智模型与 Python 的实际语义不一致）
  - **哪个概念**需要重新对齐

硬性约束（违反任意一条即为失败）：
  1. 不要给出修正后的代码，一行也不行；
  2. 不要逐行讲解学生的代码；
  3. 不要直接说出最终答案或让学生照抄的写法；
  4. 不要使用「你应该把 X 改成 Y」这类句式。

允许并鼓励：提出一个能让学生自己发现问题的问题；请学生预测某一行的输出；
用一个与其代码无关的小例子做类比。
"""

_LOW_CONFIDENCE_STANCE = (
    "置信度偏低——请以提问而非断言的语气展开，"
    "先确认学生的意图，不要把诊断结论当成既定事实"
)
_HIGH_CONFIDENCE_STANCE = "置信度较高——可以直接锚定该误区展开"

CONFIDENCE_THRESHOLD = 0.60


def build_system_prompt(mc_id: str, confidence: float) -> str:
    """构造误区锚定的 system prompt。

    置信度在这里**真的被用上了**：低置信度改变的是语气（提问 vs 断言），
    这正是近似置信度（confidence.py）落地的直接价值——否则那个数字只是
    展示给用户看的装饰。
    """
    brief = MISCONCEPTION_BRIEF.get(mc_id, "（未登记的误区）")
    stance = (
        _HIGH_CONFIDENCE_STANCE if confidence >= CONFIDENCE_THRESHOLD
        else _LOW_CONFIDENCE_STANCE
    )
    return _SYSTEM_TEMPLATE.format(
        mc_id=mc_id, brief=brief, confidence=confidence, confidence_stance=stance
    )


# =============================================================================
# 输出侧检查：答案泄露检测
# =============================================================================

# 结构性泄露信号。刻意保守：宁可漏检也不误杀正常教学表达，
# 因为误杀会让导师无法解释概念（"return 的作用是…"是合法的）。
_CODE_BLOCK = re.compile(r"```")
_FIX_PATTERN = re.compile(
    # 跨距取 60：中间常插一整段代码（"把 new = items.append(5) 改成 …"），
    # 20 字符跨不过去。用 [^。\n]* 限制不跨句，避免跨越两个无关句子误匹配。
    r"(把[^。\n]{0,60}改成|应该写成|正确的写法是|改为[:：]?\s*\S|直接写[:：])"
)
_ASSIGNMENT_LINE = re.compile(r"^\s*[A-Za-z_]\w*\s*=\s*.+$", re.MULTILINE)


def leaks_answer(reply: str, min_code_lines: int = 2) -> tuple[bool, str]:
    """检查导师回复是否泄露了答案。返回 (是否泄露, 原因)。

    这是**输出侧**的第二道闸门。第一道是 system prompt 里的否定式清单；
    模型偶尔会屈服于学生的套话，所以不能只靠 prompt。

    保守策略说明：单行赋值不算泄露（讲解 `x = 5` 是合法的），
    连续多行可执行代码才算。
    """
    if _CODE_BLOCK.search(reply):
        return True, "回复包含代码块"
    m = _FIX_PATTERN.search(reply)
    if m:
        return True, f"回复包含修正句式：{m.group(1)!r}"
    if len(_ASSIGNMENT_LINE.findall(reply)) >= min_code_lines:
        return True, "回复包含多行可执行代码"
    return False, ""


def build_messages(
    mc_id: str,
    confidence: float,
    student_code: str,
    student_message: str,
) -> list[dict[str, str]]:
    """组装完整的 messages。学生代码作为上下文给出，但 prompt 禁止逐行讲解。"""
    return [
        {"role": "system", "content": build_system_prompt(mc_id, confidence)},
        {
            "role": "user",
            "content": f"学生的代码：\n{student_code}\n\n学生说：{student_message}",
        },
    ]


if __name__ == "__main__":
    print(build_system_prompt("M3", 0.87))
    print("-" * 60)
    print(build_system_prompt("M6", 0.42))
    print("-" * 60)
    for reply in [
        "想一想：items.append(5) 执行完之后，它把什么交还给了你？",
        "你应该把 new = items.append(5) 改成 items.append(5)。",
        "```python\nitems.append(5)\n```",
    ]:
        leaked, why = leaks_answer(reply)
        print(f"{'泄露' if leaked else '通过'}: {reply[:40]!r} {why}")
