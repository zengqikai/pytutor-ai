"""
E-FR-02 · 第 1 层：Python 报错大类（完整但粗）
=============================================

三层诊断底座里，这一层几乎免费：Python 崩溃时 traceback 末行自带异常类型。
它的价值不在精度，在**完整性**——

    第 0 层  概念/知识点        （已有，粗）
    第 1 层  报错大类           （本模块，完整：任何崩溃都能归类）
    第 2 层  M1–M8 误区         （已有，精但不全）

有了第 1 层，权重与教学路径就坐在一个"永不漏"的底座上，
**学生的错在不在 M1–M8 里，都不再致命**（SRS 3.2 §4.2.2）。

三种输入 → 三种结论
-------------------
    崩溃了            → 按 traceback 末行的异常类型归类
    跑通但输出不对    → "logic"（逻辑错误，不崩溃所以没有异常类型）
    跑通且输出正确    → None（没有错误可分类）

为什么不直接用 M1–M8 的 stderr 匹配
-----------------------------------
misconception 侧的 stderr 匹配是**定向的**：它问"这个报错是否佐证 M3"。
本层是**穷举的**：它问"这个报错属于哪一类"。两者目的不同，前者可以漏
（漏了只是少一条证据），后者不能漏（漏了整个错误就隐形了）。
所以本层对未知异常返回 "runtime_other" 而非 None——归不了类也要留痕。
"""

from __future__ import annotations

import re
from typing import Final


# SRS 3.2 §4.2.2 给出的映射，逐条保留；其余为补充。
ERROR_CLASS_MAP: Final[dict[str, str]] = {
    # --- 语法层：代码根本没跑起来 ---
    "SyntaxError": "syntax",
    "IndentationError": "syntax",
    "TabError": "syntax",

    # --- 运行时 ---
    "NameError": "runtime_name",
    "UnboundLocalError": "runtime_name",     # NameError 的子类，同类归一
    "TypeError": "runtime_type",
    "ValueError": "runtime_value",
    "IndexError": "runtime_index",
    "KeyError": "runtime_key",
    "ZeroDivisionError": "runtime_math",
    "OverflowError": "runtime_math",
    "AttributeError": "runtime_attr",

    # --- 资源/环境（沙箱里也会遇到）---
    "RecursionError": "runtime_recursion",
    "MemoryError": "runtime_resource",
    "ImportError": "runtime_import",
    "ModuleNotFoundError": "runtime_import",
}

LOGIC_ERROR: Final[str] = "logic"
OTHER_ERROR: Final[str] = "runtime_other"

# 归入 syntax 的都意味着"根本没执行"，教学上要走完全不同的路径
SYNTAX_CLASSES: Final[frozenset[str]] = frozenset({"syntax"})


# traceback 末行形如 `TypeError: unsupported operand ...` 或裸的 `KeyboardInterrupt`。
# 关键约束：必须**行首无缩进**——traceback 的正文行都带缩进或以 "File " 开头，
# 只有异常行顶格。这一条比匹配 "Error" 后缀更可靠，因为自定义异常可以叫任何名字。
_EXC_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_.]*)(?::\s?.*)?$")

# "Traceback (most recent call last):" 会被上面的正则拒绝（"Traceback" 后跟空格不是冒号），
# 但显式排除更稳妥，也自我说明。
_NOT_EXCEPTIONS: Final[frozenset[str]] = frozenset({
    "Traceback", "During", "The", "File",
})


def _last_exc_type(stderr: str) -> str | None:
    """取 traceback 中**最后一个**异常的类型名。

    为什么是最后一个：异常链（`raise ... from ...` 或 "During handling of the
    above exception, another exception occurred"）会打印多个异常，
    真正终结程序的是最后那个。逆序扫描第一个匹配即是它。

    限定名（如 `json.decoder.JSONDecodeError`）取最后一段。
    """
    for line in reversed(stderr.strip().splitlines()):
        line = line.rstrip()
        if not line or line[0].isspace():
            continue
        m = _EXC_LINE.match(line)
        if not m:
            continue
        name = m.group(1)
        if name in _NOT_EXCEPTIONS:
            continue
        return name.rsplit(".", 1)[-1]
    return None


def classify_error(
    stderr: str,
    ran_ok: bool,
    output_correct: bool | None,
) -> str | None:
    """把一次运行结果归入错误大类。

    参数语义（三者不冗余，缺一不可）：
      stderr          崩溃时的标准错误；空串表示没崩。
      ran_ok          进程是否正常退出（沙箱超时/被杀 → False 但 stderr 可能为空）。
      output_correct  跑通时输出是否与预期一致；未知/无预期时传 None。

    返回 None 只在一种情况：跑通、且输出正确或无从判断。
    """
    if stderr and stderr.strip():
        exc = _last_exc_type(stderr)
        if exc is None:
            # 有 stderr 却解析不出异常类型（如 C 层崩溃、沙箱杀进程的信息）
            return OTHER_ERROR
        return ERROR_CLASS_MAP.get(exc, OTHER_ERROR)

    if not ran_ok:
        # 没有 stderr 但异常退出：超时、被资源限制杀掉、段错误
        return OTHER_ERROR

    if output_correct is False:
        return LOGIC_ERROR

    return None


# =============================================================================
# 与第 2 层的关系：M 之外的错误不再隐形
# =============================================================================

def is_beyond_misconceptions(
    error_class: str | None,
    misconceptions: list[str] | None,
) -> bool:
    """有错误、但一个 M 都没命中 —— 这正是 E-FR-02 要让其可见的情形。

    E-FR-02 的验收判定就建立在这个函数上：提交触发 NameError 的代码，
    即使不命中任何 M，error_class 也非空。
    """
    return bool(error_class) and not (misconceptions or [])


def is_syntax_level(error_class: str | None) -> bool:
    """语法错误意味着代码从未执行，教学路径必须分叉：
    不能对一段没跑过的代码谈"你以为会输出什么"（E-FR-05 的 predict-then-run
    在此情形下无意义）。"""
    return error_class in SYNTAX_CLASSES


def enrich_diagnose_result(
    result: dict,
    stderr: str,
    ran_ok: bool = True,
    output_correct: bool | None = None,
) -> dict:
    """在既有 diagnose 结果上**新增可选字段**，不动既有键（向后兼容）。

    对应 SRS 3.2 §4.2.2 的 DiagnoseResult：
        concept_id / error_class(新增) / misconceptions / confidence
    """
    ec = classify_error(stderr, ran_ok, output_correct)
    out = dict(result)
    out["error_class"] = ec
    out["beyond_misconceptions"] = is_beyond_misconceptions(
        ec, out.get("misconceptions")
    )
    return out


if __name__ == "__main__":
    chained = (
        "Traceback (most recent call last):\n"
        '  File "<stdin>", line 2, in <module>\n'
        "KeyError: 'a'\n"
        "\n"
        "During handling of the above exception, another exception occurred:\n"
        "\n"
        "Traceback (most recent call last):\n"
        '  File "<stdin>", line 4, in <module>\n'
        "TypeError: unsupported operand type(s)\n"
    )
    cases = [
        ("NameError: name 'x' is not defined", True, None),
        ("  File \"<stdin>\", line 1\n    x = \n       ^\nSyntaxError: invalid syntax", True, None),
        (chained, True, None),
        ("json.decoder.JSONDecodeError: Expecting value", True, None),
        ("KeyboardInterrupt", True, None),
        ("", True, False),
        ("", True, True),
        ("", False, None),
    ]
    for stderr, ok, correct in cases:
        head = (stderr.splitlines() or ["<空>"])[-1][:44]
        print(f"{head:46} → {classify_error(stderr, ok, correct)}")
