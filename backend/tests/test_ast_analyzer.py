"""
AST 分析器单元测试
==================

覆盖：
- safe_parse() 成功/失败
- M3: 原地方法赋值
- M4: value/index 混淆
- M5: range 边界辅助
- M6: print/return 混淆
- M7: str + int
- M8: while 条件错误
- 干净代码不误报
"""

import ast
import sys
from pathlib import Path

import pytest

# 将 backend/ 加入 sys.path（基于当前文件位置，稳定可移植）
BACKEND_ROOT = str(Path(__file__).resolve().parents[1])
sys.path.insert(0, BACKEND_ROOT)

from app.analysis.ast_analyzer import analyze_misconceptions, safe_parse
from app.analysis.ast_visitors import (
    M3InplaceAssignmentVisitor,
    M4ValueAsIndexVisitor,
    M5RangeBoundaryVisitor,
    M6PrintReturnVisitor,
    M7TypeConversionVisitor,
    M8WhileInfiniteVisitor,
)


# =============================================================================
# safe_parse
# =============================================================================

class TestSafeParse:
    def test_valid_code(self):
        tree, err, lineno = safe_parse("x = 1")
        assert tree is not None
        assert err is None
        assert lineno is None

    def test_empty_code(self):
        tree, err, lineno = safe_parse("")
        assert tree is None
        assert err == "EmptyCode"

    def test_syntax_error(self):
        tree, err, lineno = safe_parse("if x = 3: pass")
        assert tree is None
        assert err == "SyntaxError"

    def test_indentation_error(self):
        tree, err, lineno = safe_parse("def f():\nprint('hi')")
        assert tree is None
        assert err == "IndentationError"

    def test_normal_code(self):
        code = "for i in range(10):\n    print(i)"
        tree, err, lineno = safe_parse(code)
        assert tree is not None
        assert err is None


# =============================================================================
# M3: append/sort 返回值误解
# =============================================================================

class TestM3InplaceAssignment:
    def test_append_assigned(self):
        tree = ast.parse("new_list = items.append(4)")
        v = M3InplaceAssignmentVisitor()
        v.visit(tree)
        assert v.found is not None
        assert v.found["misconception_id"] == "M3"
        assert v.found["confidence"] > 0.9

    def test_sort_assigned(self):
        tree = ast.parse("result = numbers.sort()")
        v = M3InplaceAssignmentVisitor()
        v.visit(tree)
        assert v.found is not None
        assert v.found["misconception_id"] == "M3"

    def test_reverse_assigned(self):
        tree = ast.parse("x = items.reverse()")
        v = M3InplaceAssignmentVisitor()
        v.visit(tree)
        assert v.found is not None

    def test_extend_assigned(self):
        tree = ast.parse("combined = list1.extend(list2)")
        v = M3InplaceAssignmentVisitor()
        v.visit(tree)
        assert v.found is not None

    def test_append_no_assignment(self):
        """直接调用不赋值 → 不应触发 M3"""
        tree = ast.parse("items.append(4)")
        v = M3InplaceAssignmentVisitor()
        v.visit(tree)
        assert v.found is None

    def test_sorted_not_inplace(self):
        """sorted() 返回新列表，可以赋值"""
        tree = ast.parse("new_nums = sorted(nums)")
        v = M3InplaceAssignmentVisitor()
        v.visit(tree)
        assert v.found is None


# =============================================================================
# M4: index/value 混淆
# =============================================================================

class TestM4ValueAsIndex:
    def test_value_used_as_index(self):
        tree = ast.parse("for i in items:\n    print(items[i])")
        v = M4ValueAsIndexVisitor()
        v.visit(tree)
        assert v.found is not None
        assert v.found["misconception_id"] == "M4"

    def test_cross_line_detection(self):
        """跨行循环体也能检测"""
        tree = ast.parse("for x in data:\n    y = x + 1\n    print(data[x])")
        v = M4ValueAsIndexVisitor()
        v.visit(tree)
        assert v.found is not None

    def test_range_len_not_m4(self):
        """range(len(items)) 中 items[i] 是正确的"""
        tree = ast.parse("for i in range(len(items)):\n    print(items[i])")
        v = M4ValueAsIndexVisitor()
        v.visit(tree)
        assert v.found is None

    def test_enumerate_not_m4(self):
        """enumerate 中 i 是有效下标"""
        tree = ast.parse("for i, item in enumerate(items):\n    print(items[i])")
        v = M4ValueAsIndexVisitor()
        v.visit(tree)
        assert v.found is None

    def test_different_variable_name(self):
        """不同变量名不应误判"""
        tree = ast.parse("for x in items:\n    print(other[x])")
        v = M4ValueAsIndexVisitor()
        v.visit(tree)
        assert v.found is None


# =============================================================================
# M5: range 右边界误解
# =============================================================================

class TestM5RangeBoundary:
    def test_no_signal_no_trigger(self):
        """纯 range(10) 不触发"""
        tree = ast.parse("for i in range(10):\n    print(i)")
        v = M5RangeBoundaryVisitor("")
        v.visit(tree)
        result = v.evaluate(stderr="", student_question="")
        assert result is None

    def test_with_question_signal(self):
        """学生提问含边界信号 + stop_ref_in_body 联合触发"""
        code = "for i in range(1, 5):\n    if i == 5:\n        print('got five')"
        tree = ast.parse(code)
        v = M5RangeBoundaryVisitor(code)
        v.visit(tree)
        result = v.evaluate(stderr="", student_question="为什么只到4不到5")
        assert result is not None
        assert result["misconception_id"] == "M5"

    def test_with_stderr_signal(self):
        """stderr 信号 + stop_ref_in_body 联合触发"""
        code = "for i in range(0, 10):\n    if i == 10:\n        print('found')"
        tree = ast.parse(code)
        v = M5RangeBoundaryVisitor(code)
        v.visit(tree)
        result = v.evaluate(stderr="range不包括最后一个", student_question="")
        assert result is not None


# =============================================================================
# M6: print/return 混淆
# =============================================================================

class TestM6PrintReturn:
    def test_print_without_return(self):
        tree = ast.parse("def add(a, b):\n    print(a + b)")
        v = M6PrintReturnVisitor()
        v.visit(tree)
        assert v.found is not None
        assert v.found["misconception_id"] == "M6"

    def test_return_without_print(self):
        """正确用法——不触发"""
        tree = ast.parse("def add(a, b):\n    return a + b")
        v = M6PrintReturnVisitor()
        v.visit(tree)
        assert v.found is None

    def test_print_before_return(self):
        """print 后 return 是正常的——不触发 M6"""
        tree = ast.parse("def greet(name):\n    print(f'Hello {name}')\n    return name")
        v = M6PrintReturnVisitor()
        v.visit(tree)
        assert v.found is None

    def test_unreachable_print_after_return(self):
        """return 后有不可达 print"""
        tree = ast.parse("def calc(x):\n    return x * 2\n    print('done')")
        v = M6PrintReturnVisitor()
        v.visit(tree)
        assert v.found is not None


# =============================================================================
# M7: 类型转换错误
# =============================================================================

class TestM7TypeConversion:
    def test_str_plus_int_with_typeerror(self):
        """有 TypeError 时高置信度——常量 str + 常量 int"""
        tree = ast.parse("print('I am ' + 20)")
        v = M7TypeConversionVisitor(stderr="TypeError: can only concatenate str")
        v.visit(tree)
        assert v.found is not None
        assert v.found["misconception_id"] == "M7"
        assert v.found["confidence"] >= 0.85

    def test_str_plus_int_without_typeerror(self):
        """无 stderr 时低置信度"""
        tree = ast.parse("s = 'hello' + 5")
        v = M7TypeConversionVisitor(stderr="")
        v.visit(tree)
        if v.found:
            assert v.found["confidence"] <= 0.70

    def test_fstring_no_m7(self):
        """f-string 是正确用法"""
        tree = ast.parse("print(f'I am {age}')")
        v = M7TypeConversionVisitor(stderr="")
        v.visit(tree)
        assert v.found is None


# =============================================================================
# M8: while 循环条件错误
# =============================================================================

class TestM8WhileInfinite:
    def test_while_true_no_exit(self):
        tree = ast.parse("while True:\n    print('loop')")
        v = M8WhileInfiniteVisitor()
        v.visit(tree)
        assert v.found is not None
        assert v.found["misconception_id"] == "M8"

    def test_while_true_with_break(self):
        tree = ast.parse("while True:\n    print('loop')\n    break")
        v = M8WhileInfiniteVisitor()
        v.visit(tree)
        assert v.found is None

    def test_while_true_with_return(self):
        tree = ast.parse("def f():\n    while True:\n        return 1")
        v = M8WhileInfiniteVisitor()
        v.visit(tree)
        assert v.found is None

    def test_while_condition_no_update(self):
        tree = ast.parse("n = 0\nwhile n < 5:\n    print(n)")
        v = M8WhileInfiniteVisitor()
        v.visit(tree)
        assert v.found is not None

    def test_while_condition_with_update(self):
        tree = ast.parse("n = 0\nwhile n < 5:\n    print(n)\n    n += 1")
        v = M8WhileInfiniteVisitor()
        v.visit(tree)
        assert v.found is None

    def test_while_condition_with_assign_update(self):
        tree = ast.parse("n = 0\nwhile n < 5:\n    print(n)\n    n = n + 1")
        v = M8WhileInfiniteVisitor()
        v.visit(tree)
        assert v.found is None


# =============================================================================
# clean code: 干净代码不误报
# =============================================================================

class TestCleanCodeNoFalsePositive:
    """保证正常 Python 代码不被误判。"""

    def test_simple_loop(self):
        code = "for i in range(10):\n    print(i)"
        results = analyze_misconceptions(code)
        assert len(results) == 0, f"False positive: {results}"

    def test_proper_function(self):
        code = "def add(a, b):\n    return a + b"
        results = analyze_misconceptions(code)
        assert len(results) == 0, f"False positive: {results}"

    def test_correct_list_usage(self):
        code = "items = [1, 2, 3]\nitems.append(4)\nprint(items)"
        results = analyze_misconceptions(code)
        assert len(results) == 0, f"False positive: {results}"

    def test_while_with_proper_exit(self):
        code = "n = 0\nwhile n < 10:\n    print(n)\n    n += 1"
        results = analyze_misconceptions(code)
        assert len(results) == 0, f"False positive: {results}"

    def test_fstring_not_m7(self):
        code = "name = 'Alice'\nprint(f'Hello {name}')"
        results = analyze_misconceptions(code)
        m7_results = [r for r in results if r.get("misconception_id") == "M7"]
        assert len(m7_results) == 0, f"False positive M7: {results}"


# =============================================================================
# analyze_misconceptions (unified entry)
# =============================================================================

class TestAnalyzeMisconceptions:
    def test_m3_detected(self):
        results = analyze_misconceptions("new_list = items.append(4)")
        ids = [r["misconception_id"] for r in results]
        assert "M3" in ids

    def test_m1_from_syntax_error(self):
        results = analyze_misconceptions("if x = 3:\n    print('hi')")
        ids = [r["misconception_id"] for r in results]
        assert "M1" in ids

    def test_empty_code(self):
        results = analyze_misconceptions("")
        assert len(results) == 0

    def test_returns_diagnosis_method(self):
        results = analyze_misconceptions("new = items.append(1)")
        assert len(results) > 0
        assert "diagnosis_method" in results[0]
        assert results[0]["diagnosis_method"] == "ast"

    def test_returns_ast_features(self):
        results = analyze_misconceptions("new = items.append(1)")
        assert len(results) > 0
        assert "ast_features" in results[0]
        assert results[0]["ast_features"] is not None


# =============================================================================
# 合并前强制测试用例
# =============================================================================

class TestM3PopNotFlagged:
    """M3 不应标记 pop() 赋值——pop() 有返回值。"""

    def test_pop_assignment_not_m3(self):
        code = "items = [1, 2, 3]\nx = items.pop()"
        results = analyze_misconceptions(code)
        m3_results = [r for r in results if r.get("misconception_id") == "M3"]
        assert len(m3_results) == 0, f"M3 false positive on pop(): {m3_results}"

    def test_pop_with_index_not_m3(self):
        code = "items = [1, 2, 3]\nx = items.pop(0)"
        results = analyze_misconceptions(code)
        m3_results = [r for r in results if r.get("misconception_id") == "M3"]
        assert len(m3_results) == 0, f"M3 false positive on pop(0): {m3_results}"

    def test_append_still_detected_after_pop_removal(self):
        """确保删了 pop 后 append 仍能检测"""
        code = "new = items.append(4)"
        results = analyze_misconceptions(code)
        m3_results = [r for r in results if r.get("misconception_id") == "M3"]
        assert len(m3_results) == 1, f"M3 should still detect append"


class TestM5RangeBodyScan:
    """M5 只扫描 for_node.body，不扫描整个 for_node。"""

    def test_range_argument_not_treated_as_body_reference(self):
        code = "for i in range(10):\n    print(i)"
        results = analyze_misconceptions(code, stderr="", student_question="")
        m5_results = [r for r in results if r.get("misconception_id") == "M5"]
        assert len(m5_results) == 0, f"M5 false positive on plain range(10): {m5_results}"

    def test_range_with_unrelated_break_not_m5(self):
        code = "for i in range(10):\n    if i <= 5:\n        break\n    print(i)"
        results = analyze_misconceptions(code, stderr="", student_question="")
        m5_results = [r for r in results if r.get("misconception_id") == "M5"]
        assert len(m5_results) == 0, f"M5 false positive on range with break: {m5_results}"

    def test_range_with_stderr_signal_still_detected(self):
        """有 stderr + stop_ref_in_body 时仍能触发 M5"""
        code = "for i in range(0, 10):\n    if i == 10:\n        print('found ten')"
        results = analyze_misconceptions(code, stderr="range不包括最后一个", student_question="")
        m5_results = [r for r in results if r.get("misconception_id") == "M5"]
        assert len(m5_results) == 1, f"M5 should trigger with stderr + body ref"
