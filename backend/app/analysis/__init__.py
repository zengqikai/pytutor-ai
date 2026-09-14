"""
AST 代码分析模块
================

提供基于 Python AST 的代码结构分析，用于增强误区诊断。

主要入口：
    analyze_misconceptions(code, stderr, student_question) -> list[dict]

模块结构：
    ast_analyzer.py   — 统一调度、parse、fallback 逻辑
    ast_visitors.py   — 各误区的 ast.NodeVisitor 子类

使用方式：
    from app.analysis import analyze_misconceptions
    results = analyze_misconceptions(code, stderr, student_question)
"""

from app.analysis.ast_analyzer import analyze_misconceptions, safe_parse

__all__ = ["analyze_misconceptions", "safe_parse"]
