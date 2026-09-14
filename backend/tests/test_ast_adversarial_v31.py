"""
AST 诊断对抗性负例测试（SRS 3.1 · B-EVAL-05/07/08）
==================================================

背景
----
SRS 3.0 的 B 方向指标（exact_match 0.96 / macro-F1 0.974）是在"照 visitor
匹配模式反向构造"的评测集上测得，存在分布泄漏（Q11/Q33）。本文件是一次
**独立对抗性审查**的产物：这些用例**不是**照实现构造的，而是从"结构接近
误区但完全正确"的角度独立设计，用来暴露 visitor 的系统性假阳性。

本次审查在 v3.0 实现（含已宣称修复的 F5.1–F5.4）之上，仍复现了三簇新的
假阳性，均未被原有 48 项测试覆盖：

  1. M8 · len()/函数包裹的条件：`while len(s) > 0: s.pop()`、
     `while count < len(x): count += 1` —— 条件变量被 len() 包裹时，
     旧 `_extract_condition_vars` 把 `len` 当成状态变量，误报无限循环。
  2. M4 · 非字面量来源的 dict：dict 推导式、dict 返回的函数、dict 形参、
     dict 注解 —— 旧 `_collect_dict_vars` 只认 `{...}` 和 `dict()`，
     其余合法字典遍历一律误报 index/value 混淆。
  3. M6 · 展示/入口型函数：`def menu(): print(...)`、`def main(): ...` ——
     旧实现对任何"有 print 无 return"的函数一律 M6@0.88（高敏感低精确）。

修复见 ast_analyzer._collect_dict_vars（增强）、
ast_visitors.M8WhileInfiniteVisitor._extract_condition_vars（排除 callee/内置）
与 M8 场景2（任一条件变量被更新即豁免）、
ast_visitors.M6PrintReturnVisitor._looks_like_computation（计算意图护栏）。

评测诚信原则（B-EVAL-08）：教学场景**误报**（错怪写对的学生）代价高于
**漏报**，因此本文件以"clean 代码不得触发"为硬断言，真阳性回归单列。

运行：pytest backend/tests/test_ast_adversarial_v31.py -v
"""

import pytest

from app.analysis.ast_analyzer import analyze_misconceptions


def _ids(code: str, stderr: str = "", question: str = "") -> list[str]:
    return [r["misconception_id"] for r in analyze_misconceptions(code, stderr, question)]


# =============================================================================
# 硬负例集（must NOT fire）—— B-EVAL-05
# =============================================================================

class TestM4DictTraversalExemption:
    """M4：各种来源的 dict 合法遍历都不得误报。"""

    def test_dict_literal(self):
        code = "d = {'a': 1, 'b': 2}\nfor k in d:\n    print(d[k])"
        assert "M4" not in _ids(code)

    def test_dict_call(self):
        code = "d = dict(a=1, b=2)\nfor k in d:\n    print(d[k])"
        assert "M4" not in _ids(code)

    def test_dict_comprehension(self):
        code = "d = {k: k * k for k in range(3)}\nfor k in d:\n    print(d[k])"
        assert "M4" not in _ids(code)

    def test_dict_returned_by_function(self):
        code = (
            "def get_scores():\n    return {'a': 1}\n"
            "d = get_scores()\nfor k in d:\n    print(d[k])"
        )
        assert "M4" not in _ids(code)

    def test_dict_parameter(self):
        code = "def show(d):\n    for k in d:\n        print(d[k])"
        assert "M4" not in _ids(code)

    def test_dict_annotation(self):
        code = "d: dict = {}\nd['a'] = 1\nfor k in d:\n    print(d[k])"
        assert "M4" not in _ids(code)


class TestM8ConvergentLoopExemption:
    """M8：会收敛的循环不得误报无限循环。"""

    def test_while_len_gt_zero_pop(self):
        code = "s = [1, 2, 3]\nwhile len(s) > 0:\n    s.pop()"
        assert "M8" not in _ids(code)

    def test_while_len_truthy_pop(self):
        code = "s = [1, 2, 3]\nwhile len(s):\n    s.pop()"
        assert "M8" not in _ids(code)

    def test_while_counter_lt_len(self):
        code = "x = [1, 2, 3]\ncount = 0\nwhile count < len(x):\n    count += 1"
        assert "M8" not in _ids(code)

    def test_while_two_pointer(self):
        code = "lo, hi = 0, 10\nwhile lo < hi:\n    lo += 1"
        assert "M8" not in _ids(code)

    def test_while_truthy_container_pop(self):
        code = "stack = [1, 2]\nwhile stack:\n    stack.pop()"
        assert "M8" not in _ids(code)

    def test_while_flag_break(self):
        code = "done = False\nwhile not done:\n    done = True"
        assert "M8" not in _ids(code)


class TestM6DisplayFunctionExemption:
    """M6：展示/入口型函数只 print 不 return 是合法的，不得误报。"""

    def test_menu_function(self):
        code = "def menu():\n    print('1. Start')\n    print('2. Quit')"
        assert "M6" not in _ids(code)

    def test_main_function(self):
        code = "def main():\n    print('starting...')\nmain()"
        assert "M6" not in _ids(code)

    def test_show_side_effect(self):
        code = "def show(items):\n    for i in items:\n        print(i)"
        assert "M6" not in _ids(code)

    def test_display_prefix(self):
        code = "def display_board(b):\n    print(b)"
        assert "M6" not in _ids(code)


# =============================================================================
# 真阳性回归保护（must STILL fire）
# =============================================================================

class TestTruePositiveRegression:
    """确保修复假阳性没有把真误区一起放过。"""

    def test_m4_real_value_as_index(self):
        code = "items = ['a', 'b', 'c']\nfor i in items:\n    print(items[i])"
        assert "M4" in _ids(code)

    def test_m4_list_param_real(self):
        # items 是 list 形参（名字不像 dict）→ value-as-index 仍应报
        code = "def f(items):\n    for i in items:\n        print(items[i])"
        assert "M4" in _ids(code)

    def test_m8_no_update(self):
        code = "i = 0\nwhile i < 10:\n    print(i)"
        assert "M8" in _ids(code)

    def test_m8_while_true_no_break(self):
        code = "while True:\n    print('loop')"
        assert "M8" in _ids(code)

    def test_m6_compute_and_print(self):
        code = "def add(a, b):\n    print(a + b)"
        assert "M6" in _ids(code)

    def test_m6_compute_var_print(self):
        code = "def calc(x):\n    r = x * 2\n    print(r)"
        assert "M6" in _ids(code)

    def test_m6_unreachable_after_return(self):
        code = "def f(x):\n    return x\n    print('dead')"
        assert "M6" in _ids(code)

    def test_m3_append_assigned(self):
        code = "new = [].append(5)"
        assert "M3" in _ids(code)

    def test_m7_input_not_converted(self):
        code = "n = input()\nprint(n % 3)"
        assert "M7" in _ids(code)

    def test_m1_assignment_as_comparison(self):
        code = "if x = 3:\n    print('hi')"
        assert "M1" in _ids(code)
