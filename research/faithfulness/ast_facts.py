"""
AST 事实集抽取器 (AST Fact Extractor)
=====================================

研究方向 R2 的地基：把一段学生代码的**客观结构事实**抽成一组标准化的
"事实三元组"，作为符号裁判核验 LLM 误区解释忠实度的 ground truth。

核心思想
--------
LLM 解释里的每个断言（claim），如"第 3 行把 append() 的返回值赋给了 x"，
要么在代码 AST 里**有客观对应**（忠实），要么**没有**（幻觉）。AST 不会撒谎，
所以我们先把代码能被客观陈述的一切事实枚举出来，形成一个可查询的事实集。

事实类型（可扩展）：
  - assign_call_result: 第 L 行，把 obj.method() 的返回值赋给了 var
  - method_call:        第 L 行，对 obj 调用了 method()
  - for_loop:           第 L 行，for var in iterable
  - subscript:          第 L 行，对 container 用 index 下标访问
  - range_call:         第 L 行，range(args...)
  - while_loop:         第 L 行，while <condition>
  - func_def:           第 L 行，定义函数 name(params)，has_return=?
  - print_call:         第 L 行，print(...)
  - binop:              第 L 行，<left> <op> <right>
  - var_type_hint:      变量 var 疑似类型 t（来自字面量/input/int() 等）

这是**纯离线、零 API**的，任何人可复现。它同时是 R1（notional machine 反演）
的语法层证据来源。
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field, asdict
from typing import Any


INPLACE_METHODS = frozenset({
    'append', 'extend', 'insert', 'remove', 'sort', 'reverse', 'clear',
    'update', 'add', 'discard',
})


@dataclass(frozen=True)
class Fact:
    """一条可核验的结构事实。"""
    kind: str                       # 事实类型
    line: int                       # 行号
    attrs: tuple                    # (key, value) 对的有序元组，便于 hash/比较

    def get(self, key: str, default: Any = None) -> Any:
        for k, v in self.attrs:
            if k == key:
                return v
        return default

    def to_dict(self) -> dict:
        return {"kind": self.kind, "line": self.line, **dict(self.attrs)}

    def describe(self) -> str:
        """人类可读描述，便于调试与论文附录展示。"""
        d = dict(self.attrs)
        if self.kind == "assign_call_result":
            return (f"L{self.line}: 把 {d.get('object')}.{d.get('method')}() 的"
                    f"返回值赋给 {d.get('target')}"
                    f"（{d.get('method')} 是 in-place 方法，返回 None）"
                    if d.get('is_inplace') else
                    f"L{self.line}: 把 {d.get('object')}.{d.get('method')}() 的返回值赋给 {d.get('target')}")
        if self.kind == "method_call":
            return f"L{self.line}: 对 {d.get('object')} 调用 {d.get('method')}()"
        if self.kind == "for_loop":
            return f"L{self.line}: for {d.get('target')} in {d.get('iterable')}"
        if self.kind == "subscript":
            return f"L{self.line}: {d.get('container')}[{d.get('index')}] 下标访问"
        if self.kind == "range_call":
            return f"L{self.line}: range({d.get('args')})"
        if self.kind == "while_loop":
            return f"L{self.line}: while {d.get('condition')}"
        if self.kind == "func_def":
            return (f"L{self.line}: 定义函数 {d.get('name')}("
                    f"{d.get('params')})，has_return={d.get('has_return')}")
        if self.kind == "print_call":
            return f"L{self.line}: print({d.get('args')})"
        if self.kind == "binop":
            return f"L{self.line}: {d.get('left')} {d.get('op')} {d.get('right')}"
        if self.kind == "var_type_hint":
            return f"变量 {d.get('var')} 疑似类型 {d.get('type')}"
        return f"L{self.line}: {self.kind} {d}"


def _fact(kind: str, line: int, **attrs) -> Fact:
    return Fact(kind=kind, line=line, attrs=tuple(sorted(attrs.items())))


def _unparse(node: ast.AST) -> str:
    try:
        return ast.unparse(node)
    except Exception:
        return "<expr>"


class _FactVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.facts: list[Fact] = []
        self.var_types: dict[str, str] = {}

    # -- 赋值：记录类型提示 + in-place 方法返回值赋值 --
    def visit_Assign(self, node: ast.Assign) -> None:
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            v = node.value
            if isinstance(v, ast.Constant):
                t = "str" if isinstance(v.value, str) else (
                    "num" if isinstance(v.value, (int, float)) else "other")
                self.var_types[name] = t
                self.facts.append(_fact("var_type_hint", node.lineno, var=name, type=t))
            elif isinstance(v, ast.Call) and isinstance(v.func, ast.Name):
                if v.func.id == "input":
                    self.var_types[name] = "str"
                    self.facts.append(_fact("var_type_hint", node.lineno, var=name, type="str(input)"))
                elif v.func.id in ("int", "float", "len"):
                    self.var_types[name] = "num"
                    self.facts.append(_fact("var_type_hint", node.lineno, var=name, type="num"))
            # in-place 方法返回值赋值
            if isinstance(v, ast.Call) and isinstance(v.func, ast.Attribute):
                method = v.func.attr
                obj = _unparse(v.func.value)
                self.facts.append(_fact(
                    "assign_call_result", node.lineno,
                    target=name, object=obj, method=method,
                    is_inplace=(method in INPLACE_METHODS),
                ))
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        target = _unparse(node.target)
        iterable = _unparse(node.iter)
        self.facts.append(_fact("for_loop", node.lineno, target=target, iterable=iterable))
        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name) \
                and node.iter.func.id == "range":
            args = ", ".join(_unparse(a) for a in node.iter.args)
            self.facts.append(_fact("range_call", node.lineno, args=args,
                                    argc=len(node.iter.args)))
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.facts.append(_fact("while_loop", node.lineno, condition=_unparse(node.test)))
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        self.facts.append(_fact(
            "subscript", node.lineno,
            container=_unparse(node.value), index=_unparse(node.slice)))
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id == "print":
            args = ", ".join(_unparse(a) for a in node.args)
            self.facts.append(_fact("print_call", node.lineno, args=args))
        elif isinstance(node.func, ast.Attribute):
            self.facts.append(_fact(
                "method_call", node.lineno,
                object=_unparse(node.func.value), method=node.func.attr))
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp) -> None:
        self.facts.append(_fact(
            "binop", node.lineno,
            left=_unparse(node.left), op=type(node.op).__name__,
            right=_unparse(node.right)))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        has_return = any(
            isinstance(n, ast.Return) and n.value is not None
            for n in ast.walk(node))
        params = ", ".join(a.arg for a in node.args.args)
        self.facts.append(_fact(
            "func_def", node.lineno,
            name=node.name, params=params, has_return=has_return))
        self.generic_visit(node)


def extract_facts(code: str) -> list[Fact]:
    """把代码抽成事实集。解析失败返回空集（调用方据此走语法误区通道）。"""
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    v = _FactVisitor()
    v.visit(tree)
    return v.facts


def facts_as_dicts(code: str) -> list[dict]:
    return [f.to_dict() for f in extract_facts(code)]


if __name__ == "__main__":
    sample = (
        "items = []\n"
        "new = items.append(5)\n"
        "for i in items:\n"
        "    print(items[i])\n"
    )
    print("=== 代码 ===")
    print(sample)
    print("=== 抽取的 AST 事实集 ===")
    for f in extract_facts(sample):
        print(" •", f.describe())
