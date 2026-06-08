"""
代码安全策略
============

在代码执行前进行静态安全检查，阻止危险操作。

安全检查是多层防御的第一层：
1. 静态分析（本模块）：在执行前扫描代码中的危险模式
2. 运行时隔离（executor.py）：Docker/子进程限制
3. 资源限制（executor.py）：CPU、内存、时间、输出大小

被阻止的危险模块：
    os, subprocess, sys, shutil, pathlib, socket, requests,
    ctypes, multiprocessing, threading, signal, importlib,
    __builtins__ (exec, eval, compile, __import__, open)

为什么不能只依赖运行时隔离？
    静态检查可以提前阻止明显的恶意代码，节省沙箱资源（无需创建容器）。
    但它不能替代运行时隔离——静态检查可以被绕过（如使用 __import__('os')）。
"""

import re
from typing import Tuple

# =============================================================================
# 危险模式定义
# =============================================================================

# 禁止导入的模块
FORBIDDEN_IMPORTS = [
    "os",
    "subprocess",
    "sys",
    "shutil",
    "pathlib",
    "socket",
    "requests",
    "urllib",
    "http",
    "ftplib",
    "telnetlib",
    "smtplib",
    "ctypes",
    "multiprocessing",
    "threading",
    "signal",
    "importlib",
    "pickle",
    "marshal",
]

# 禁止的内置函数
FORBIDDEN_BUILTINS = [
    "exec",
    "eval",
    "compile",
    "__import__",
    "open",
    "input",
]

# 禁止的文件操作模式
FORBIDDEN_FILE_PATTERNS = [
    r"open\s*\([^)]*['\"][wab]",
    r"__builtins__",
    r"getattr\s*\(\s*__import__",
]


def check_code_safety(code: str) -> Tuple[bool, str]:
    """
    静态检查代码安全性。

    参数:
        code: Python 源代码

    返回:
        (is_safe, reason): is_safe=True 表示通过检查，否则 reason 描述拦截原因
    """
    # 检查 1：禁止导入的模块
    for module in FORBIDDEN_IMPORTS:
        # 匹配：import os, from os import, __import__('os')
        patterns = [
            rf"^import\s+{module}\b",
            rf"from\s+{module}\b",
            rf"__import__\s*\(\s*['\"]{module}['\"]",
        ]
        for pattern in patterns:
            if re.search(pattern, code, re.MULTILINE):
                return False, f"禁止导入模块: {module}"

    # 检查 2：禁止的内置函数
    for func in FORBIDDEN_BUILTINS:
        # 匹配独立调用（不匹配作为变量名的一部分）
        pattern = rf"(?<![a-zA-Z_.]){func}\s*\("
        if re.search(pattern, code):
            # exec() 和 eval() 在字符串中也可能被误判，做更精确的匹配
            if func in ("exec", "eval"):
                # 检查是否真的是函数调用（前面没有定义）
                if not re.search(rf"(def|class|\.)\s*{func}", code):
                    return False, f"禁止使用内置函数: {func}()"
            else:
                return False, f"禁止使用内置函数: {func}()"

    # 检查 3：危险的文件操作
    for pattern in FORBIDDEN_FILE_PATTERNS:
        if re.search(pattern, code):
            return False, "禁止文件写操作"

    return True, ""


def sanitize_code(code: str) -> str:
    """
    清理代码中的潜在问题（不改变语义）。

    当前处理：
    - 统一换行符
    - 移除 BOM 头
    """
    code = code.replace("\r\n", "\n").replace("\r", "\n")
    code = code.lstrip("﻿")  # 移除 UTF-8 BOM
    return code
