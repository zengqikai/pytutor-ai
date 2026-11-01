"""
代码安全策略（简化版）
======================

只拦截真正危险的系统级操作，允许正常编程学习所需的一切。

被拦截的：
- 系统命令执行（os.system, subprocess）
- 动态代码执行（eval, exec, compile, __import__）
- 网络访问（socket, requests, urllib）
- 文件系统修改（shutil, os.remove, os.rmdir）

不被拦截的（学习/ACM 需要的）：
- input(), print() —— 基本 IO
- open() 读取 —— 但限制只读
- 标准库：math, collections, itertools, random, json 等
- sys.stdin, sys.stdout（ACM 模式常用）
"""

import re
from typing import Tuple

# 仅拦截这些模块的导入
FORBIDDEN_MODULES = [
    "os", "subprocess", "socket", "shutil",
    "requests", "urllib", "http", "ftplib", "smtplib",
    "ctypes", "multiprocessing", "signal",
    "pickle", "marshal",
]

# 仅拦截这些内置函数
FORBIDDEN_FUNCTIONS = [
    "eval", "exec", "compile", "__import__",
]


# 子进程模式没有文件系统隔离，额外拦截这几类能直接读服务端文件的写法。
# 注意：这仍然只是"抬高门槛"，不是安全边界——真正的隔离只有 Docker。
STRICT_FORBIDDEN_MODULES = ["importlib", "runpy", "pkgutil", "importlib.util"]
STRICT_FORBIDDEN_PATTERNS = [
    (r"\bopen\s*\(", "子进程模式禁止文件读写（open）"),
    (r"\b__builtins__\b", "禁止访问 __builtins__"),
    (r"\bsys\s*\.\s*modules\b", "禁止访问 sys.modules"),
    (r"\bglobals\s*\(", "禁止使用 globals()"),
    (r"\blocals\s*\(", "禁止使用 locals()"),
    (r"\bvars\s*\(", "禁止使用 vars()"),
]


def check_code_safety(code: str, strict: bool = False) -> Tuple[bool, str]:
    """
    静态检查代码安全性。
    返回 (is_safe, reason): True=安全，False=拦截原因。

    strict=True 供 subprocess 模式使用：额外禁止文件访问和模块动态加载。
    """
    # 去掉注释和字符串后再检查，减少误杀
    cleaned = _remove_strings_and_comments(code)

    if strict:
        for module in STRICT_FORBIDDEN_MODULES:
            if re.search(rf"\b(?:import|from)\s+{re.escape(module)}\b", cleaned):
                return False, f"子进程模式禁止导入模块: {module}"
        for pattern, reason in STRICT_FORBIDDEN_PATTERNS:
            if re.search(pattern, cleaned):
                return False, reason

    # 1. 检查危险模块导入
    for module in FORBIDDEN_MODULES:
        patterns = [
            rf"\bimport\s+{module}\b",
            rf"\bfrom\s+{module}\b",
            rf"__import__\s*\(\s*['\"]{module}['\"]",
        ]
        for pattern in patterns:
            if re.search(pattern, cleaned):
                return False, f"禁止导入模块: {module}"

    # 2. 检查危险函数调用
    for func in FORBIDDEN_FUNCTIONS:
        if re.search(rf"\b{func}\s*\(", cleaned):
            return False, f"禁止使用: {func}()"

    # 3. 系统命令执行
    if re.search(r"\bos\.system\s*\(|\bos\.popen\s*\(|\bsubprocess\.", cleaned):
        return False, "禁止执行系统命令"

    # 4. 文件写入（允许读取）
    if re.search(r"\bopen\s*\([^)]*['\"][wab]", cleaned):
        return False, "禁止文件写入操作"

    return True, ""


def _remove_strings_and_comments(code: str) -> str:
    """移除字符串字面量和注释，避免误杀。"""
    # 移除单行注释
    code = re.sub(r"#.*$", "", code, flags=re.MULTILINE)
    # 移除三引号字符串
    code = re.sub(r'""".*?"""', '""', code, flags=re.DOTALL)
    code = re.sub(r"'''.*?'''", "''", code, flags=re.DOTALL)
    # 移除普通字符串
    code = re.sub(r'"[^"]*"', '""', code)
    code = re.sub(r"'[^']*'", "''", code)
    return code
