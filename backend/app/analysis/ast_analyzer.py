"""
AST 误码分析器（核心编排模块）
===============================

负责 AST 解析、各误区 Visitor 调度、结果合并、fallback 逻辑。

设计原则：
- 单一入口：`analyze_misconceptions(code, stderr, student_question)`
- 各 Visitor 独立运行，不互相依赖
- M1/M2 在 parse 阶段处理（SyntaxError/IndentationError）
- M5/M7 结合外部信号（stderr、学生问题）降低误报
- 返回统一格式，向后兼容现有 diagnose() 返回值
"""

import ast
import re
from typing import Optional

from app.analysis.ast_visitors import (
    M3InplaceAssignmentVisitor,
    M4ValueAsIndexVisitor,
    M5RangeBoundaryVisitor,
    M6PrintReturnVisitor,
    M7TypeConversionVisitor,
    M8WhileInfiniteVisitor,
)
from app.observability.logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# AST 解析
# =============================================================================

def safe_parse(code: str) -> tuple[Optional[ast.AST], Optional[str], Optional[int]]:
    """
    安全解析 Python 代码为 AST。

    返回:
        (tree, error_type, error_lineno)
        - 成功: (tree, None, None)
        - 失败: (None, "SyntaxError" | "IndentationError" | "Other", lineno)
    """
    # 规范化换行
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    if not code.strip():
        return None, "EmptyCode", None

    try:
        tree = ast.parse(code)
        return tree, None, None
    except IndentationError as e:
        return None, "IndentationError", getattr(e, "lineno", None)
    except SyntaxError as e:
        return None, "SyntaxError", getattr(e, "lineno", None)
    except Exception as e:
        return None, type(e).__name__, None


# =============================================================================
# M1/M2：语法错误检测
# =============================================================================

def _detect_m1_from_syntaxerror(code: str) -> dict | None:
    """
    检测 M1：赋值与比较混淆。

    触发条件：
    - 代码无法通过 ast.parse（SyntaxError）
    - if/while 条件中出现单个 =

    不触发：
    - == (比较运算符)
    - >=, <=, != (比较运算符)
    - := (海象运算符)
    - 普通赋值语句 x = 5
    """
    # 精确匹配：= 前后都不是 =，且前面不是 ! < > :
    pattern = r'(if|while)\s+.+?(?<![=!<>:])=(?!=)\s*[^=]'
    if re.search(pattern, code):
        return {
            "misconception_id": "M1",
            "misconception_name": "赋值与比较混淆",
            "confidence": 0.92,
            "evidence": "在 if/while 条件中使用了单个 = 而非 ==（比较运算符）",
            "diagnosis_method": "ast",
            "ast_features": {"pattern": "single_equal_in_condition"},
        }
    return None


def _detect_m2_from_indentationerror(code: str, error_type: str | None) -> dict | None:
    """
    检测 M2：缩进理解错误。

    触发条件：
    - IndentationError
    - SyntaxError 且错误信息含 "indent"
    """
    if error_type == "IndentationError":
        return {
            "misconception_id": "M2",
            "misconception_name": "缩进理解错误",
            "confidence": 0.95,
            "evidence": "代码缩进错误：if/for/while/def 后需要缩进的代码块",
            "diagnosis_method": "ast",
            "ast_features": {"pattern": "indentation_error"},
        }
    return None


# =============================================================================
# M3-M8：AST 结构检测
# =============================================================================

def _collect_dict_vars(tree: ast.AST) -> set[str]:
    """收集"可能是 dict"的变量名，用于 M4 dict 遍历豁免（v3.1 增强）。

    覆盖来源（较 v3.0 大幅扩展，用于消除 clean 代码假阳性）：
      1. 字典字面量：       d = {...}
      2. dict() 构造：      d = dict(...)
      3. 字典推导式：       d = {k: v for ...}                      (新)
      4. dict 返回的函数：  def get() -> {...} / return {...}         (新)
         —— 将"函数体内 return 字典字面量"的函数名登记，
            再把 `d = get()` 的 d 视作 dict。
      5. 显式类型注解：     d: dict = ... / d: Dict[...] = ...        (新)
      6. 函数形参名启发式： 形参名以 d/dict/map/dic/table/counts     (新, 弱信号)
         结尾者视为可能 dict —— 仅用于"豁免"，宁可漏报 M4 不可误伤。

    设计原则（对抗性审查结论）：M4 教学代价不对称——错怪写对字典遍历的
    学生代价高于漏掉一次真 index/value 混淆。故此集合只做"豁免"，从宽。
    """
    dict_vars: set[str] = set()

    # ---- Pass 1: 找出"返回 dict 字面量/推导式/dict() 的函数名" ----
    dict_returning_funcs: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, ast.Return) and sub.value is not None:
                    if _expr_is_dict(sub.value):
                        dict_returning_funcs.add(node.name)
                        break

    # ---- Pass 2: 赋值 / 注解 / 形参 ----
    for node in ast.walk(tree):
        # 赋值
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    v = node.value
                    if _expr_is_dict(v):
                        dict_vars.add(target.id)
                    elif isinstance(v, ast.Call) and isinstance(v.func, ast.Name) \
                            and v.func.id in dict_returning_funcs:
                        dict_vars.add(target.id)
        # 带注解赋值 d: dict = ...
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if _annotation_is_dict(node.annotation):
                dict_vars.add(node.target.id)
        # 函数形参名启发式
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in list(node.args.args) + list(node.args.posonlyargs) + list(node.args.kwonlyargs):
                if _param_name_looks_dict(arg.arg):
                    dict_vars.add(arg.arg)
                # 形参带 dict 注解
                if arg.annotation is not None and _annotation_is_dict(arg.annotation):
                    dict_vars.add(arg.arg)

    return dict_vars


def _expr_is_dict(node: ast.expr) -> bool:
    """表达式是否是 dict 字面量 / 字典推导式 / dict() 调用。"""
    if isinstance(node, (ast.Dict, ast.DictComp)):
        return True
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'dict':
        return True
    return False


def _annotation_is_dict(node: ast.expr) -> bool:
    """类型注解是否表示 dict（dict / Dict / typing.Dict[...]）。"""
    if isinstance(node, ast.Name) and node.id in ('dict', 'Dict'):
        return True
    if isinstance(node, ast.Subscript):
        base = node.value
        if isinstance(base, ast.Name) and base.id in ('dict', 'Dict'):
            return True
        if isinstance(base, ast.Attribute) and base.attr in ('dict', 'Dict'):
            return True
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        # 字符串形式的前向引用注解，如 "dict[str,int]"
        return node.value.strip().lower().startswith('dict')
    return False


def _param_name_looks_dict(name: str) -> bool:
    """形参名启发式：像 dict 的名字（弱信号，仅用于豁免 M4）。"""
    n = name.lower()
    return (
        n in {'d', 'dic', 'dct', 'dict', 'map', 'mapping', 'table',
              'counts', 'count_map', 'freq', 'freqs', 'lookup', 'index_map'}
        or n.endswith('_dict') or n.endswith('_map') or n.endswith('dict')
    )


def _analyze_ast_structure(tree: ast.AST, code: str, stderr: str,
                           student_question: str) -> list[dict]:
    """
    对 AST 树运行所有 Visitor，收集检测结果。

    返回按置信度降序排列的检测列表。
    """
    findings: list[dict] = []
    dict_vars = _collect_dict_vars(tree)

    # M3：in-place 方法赋值
    v3 = M3InplaceAssignmentVisitor()
    v3.visit(tree)
    if v3.found:
        v3.found["diagnosis_method"] = "ast"
        findings.append(v3.found)

    # M4：value/index 混淆（已知 dict 变量豁免）
    v4 = M4ValueAsIndexVisitor(dict_vars=dict_vars)
    v4.visit(tree)
    if v4.found:
        v4.found["diagnosis_method"] = "ast"
        findings.append(v4.found)

    # M5：range 右边界误解（信号评分制）
    v5 = M5RangeBoundaryVisitor(code)
    v5.visit(tree)
    m5_result = v5.evaluate(stderr=stderr, student_question=student_question)
    if m5_result:
        m5_result["diagnosis_method"] = "ast"
        findings.append(m5_result)

    # M6：print/return 混淆
    v6 = M6PrintReturnVisitor()
    v6.visit(tree)
    if v6.found:
        v6.found["diagnosis_method"] = "ast"
        findings.append(v6.found)

    # M7：类型转换错误（stderr 信号加权）
    v7 = M7TypeConversionVisitor(stderr=stderr)
    v7.visit(tree)
    if v7.found:
        v7.found["diagnosis_method"] = "ast"
        findings.append(v7.found)

    # M8：while 循环条件错误
    v8 = M8WhileInfiniteVisitor()
    v8.visit(tree)
    if v8.found:
        v8.found["diagnosis_method"] = "ast"
        findings.append(v8.found)

    # 按置信度降序排列
    findings.sort(key=lambda f: f.get("confidence", 0), reverse=True)
    return findings


# =============================================================================
# M1/M2 fallback：正则（保留旧逻辑的精确匹配能力）
# =============================================================================

def _fallback_m1_regex(code: str) -> dict | None:
    """旧正则 M1 检测（作为 AST 的补充）。"""
    # 避免误判 == != >= <= :=
    pattern = r'(if|while)\s+.+?(?<![=!<>:])=(?!=)\s*[^=]'
    if re.search(pattern, code):
        return {
            "misconception_id": "M1",
            "misconception_name": "赋值与比较混淆",
            "confidence": 0.85,
            "evidence": "代码匹配 M1 模式：在 if/while 条件中使用单个 =",
            "diagnosis_method": "regex",
            "ast_features": None,
        }
    return None


def _fallback_m2_regex(code: str) -> dict | None:
    """旧正则 M2 检测。"""
    pattern = r'(if|for|while|def|else|elif)\s+.*:\s*\n\s*(?!(    |\t|#))'
    if re.search(pattern, code):
        return {
            "misconception_id": "M2",
            "misconception_name": "缩进理解错误",
            "confidence": 0.85,
            "evidence": "代码匹配 M2 模式：控制流语句后缺少缩进",
            "diagnosis_method": "regex",
            "ast_features": None,
        }
    return None


# =============================================================================
# 统一入口
# =============================================================================

def analyze_misconceptions(
    code: str,
    stderr: str = "",
    student_question: str = "",
) -> list[dict]:
    """
    AST 误码分析统一入口。

    参数:
        code: 学生 Python 代码
        stderr: 运行错误信息（可为空）
        student_question: 学生提问文本（可为空）

    返回:
        list[dict]: 检测到的误区列表，按置信度降序。
        每个 dict 包含：
            - misconception_id: str
            - misconception_name: str
            - confidence: float
            - evidence: str
            - diagnosis_method: "ast" | "regex"
            - ast_features: dict | None
            - related_concepts: list[str]
        空列表表示未检测到误区。
    """
    if not code.strip():
        return []

    # ---- Step 1: 尝试 AST 解析 ----
    tree, error_type, error_lineno = safe_parse(code)

    # ---- Step 2: 处理语法错误 (M1/M2) ----
    if tree is None:
        findings: list[dict] = []

        if error_type in ("SyntaxError",):
            m1 = _detect_m1_from_syntaxerror(code)
            if m1:
                findings.append(m1)

        if error_type in ("IndentationError", "SyntaxError"):
            m2 = _detect_m2_from_indentationerror(code, error_type)
            if m2:
                findings.append(m2)

        # AST 解析失败时也尝试正则 fallback
        if not findings:
            m1_regex = _fallback_m1_regex(code)
            if m1_regex:
                findings.append(m1_regex)
            m2_regex = _fallback_m2_regex(code)
            if m2_regex:
                findings.append(m2_regex)

        if findings:
            logger.info(
                "ast_diagnosis_parse_error",
                error_type=error_type,
                finding_count=len(findings),
            )
        return findings

    # ---- Step 3: AST 结构分析 (M3-M8) ----
    findings = _analyze_ast_structure(tree, code, stderr, student_question)

    if findings:
        logger.info(
            "ast_diagnosis_completed",
            finding_count=len(findings),
            top_id=findings[0].get("misconception_id"),
            top_confidence=findings[0].get("confidence"),
        )
    else:
        logger.debug("ast_diagnosis_no_finding")

    return findings
