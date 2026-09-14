"""
AST NodeVisitor 子类集合
========================

每种 Python 初学者误区 (M3-M8) 对应一个 Visitor，遍历 AST 树提取特征。

设计原则：
- 每个 Visitor 只负责一种误区的检测
- 找到匹配后设置 self.found 字典并停止遍历（设置 self._done）
- 返回 None 表示未发现该误区
"""

import ast

# =============================================================================
# 工具常量
# =============================================================================

# Python 原地修改方法（返回 None，不应被赋值）
INPLACE_METHODS = frozenset({
    'append', 'extend', 'insert', 'remove',
    'sort', 'reverse', 'clear',
})

# 类型转换函数名
CONVERSION_FUNCS = frozenset({'str', 'int', 'float', 'bool', 'list', 'tuple', 'set', 'dict'})


# =============================================================================
# M3: append/sort 返回值误解
# =============================================================================

class M3InplaceAssignmentVisitor(ast.NodeVisitor):
    """
    检测将 in-place 方法的返回值赋给变量的模式。

    目标代码：
        new_list = items.append(x)
        result = numbers.sort()
        sorted_data = data.reverse()

    AST 结构：
        Assign(value=Call(func=Attribute(attr in INPLACE_METHODS)))

    正确用法：
        items.append(x)       # 无赋值 → 不触发
        new_list = items + [x] # 非 in-place 方法 → 不触发
    """

    def __init__(self):
        self.found = None
        self._done = False

    def visit_Assign(self, node: ast.Assign):
        if self._done:
            return
        if not isinstance(node.value, ast.Call):
            return
        call = node.value
        if not isinstance(call.func, ast.Attribute):
            return
        method_name = call.func.attr
        if method_name in INPLACE_METHODS:
            target_str = self._name_str(node.targets[0]) if node.targets else "?"
            obj_str = self._name_str(call.func.value)
            self.found = {
                "misconception_id": "M3",
                "misconception_name": "append 返回值误解",
                "confidence": 0.92,
                "evidence": (
                    f"第 {node.lineno} 行：将 {obj_str}.{method_name}() 的返回值赋给 "
                    f"'{target_str}' —— {method_name}() 返回 None，应直接调用而不赋值"
                ),
                "ast_features": {
                    "method": method_name,
                    "target": target_str,
                    "object": obj_str,
                    "line": node.lineno,
                },
            }
            self._done = True
        self.generic_visit(node)

    @staticmethod
    def _name_str(node: ast.expr) -> str:
        """安全地将 AST 表达式转为可读字符串。"""
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return f"{M3InplaceAssignmentVisitor._name_str(node.value)}.{node.attr}"
        if isinstance(node, ast.Constant):
            return repr(node.value)
        return "..."


# =============================================================================
# M4: index/value 混淆
# =============================================================================

class M4ValueAsIndexVisitor(ast.NodeVisitor):
    """
    检测 for 循环中将元素当作索引使用的模式。

    目标代码：
        items = ['a', 'b', 'c']
        for i in items:
            print(items[i])     # i 是 'a'/'b'/'c'，不应作为下标

    AST 结构：
        For(target=Name('i'), iter=Name('items'))
          body contains: Subscript(value=Name('items'), slice=Name('i'))
    """

    def __init__(self, dict_vars: set[str] | frozenset = frozenset()):
        self.found = None
        self._done = False
        self._dict_vars = dict_vars

    def visit_For(self, node: ast.For):
        if self._done:
            return
        # 只处理简单变量名作为循环变量
        if not isinstance(node.target, ast.Name):
            self.generic_visit(node)
            return
        loop_var = node.target.id
        iter_name = self._extract_iter_name(node.iter)
        if iter_name is None:
            self.generic_visit(node)
            return
        # 字典遍历是合法的，跳过
        if iter_name in self._dict_vars:
            self.generic_visit(node)
            return

        # 在循环体中查找 iterable[loop_var] 模式
        checker = _SubscriptChecker(iter_name, loop_var)
        for stmt in node.body:
            checker.visit(stmt)
            if checker.found_line is not None:
                self.found = {
                    "misconception_id": "M4",
                    "misconception_name": "index 和 value 混淆",
                    "confidence": 0.90,
                    "evidence": (
                        f"第 {checker.found_line} 行：循环变量 '{loop_var}' 被用作 "
                        f"'{iter_name}' 的索引。for 循环遍历的是元素值，不是下标。"
                        f"应使用 `for {loop_var} in range(len({iter_name})):` 或直接使用元素。"
                    ),
                    "ast_features": {
                        "loop_variable": loop_var,
                        "iterable": iter_name,
                        "error_line": checker.found_line,
                    },
                }
                self._done = True
                return
        self.generic_visit(node)

    @staticmethod
    def _extract_iter_name(node: ast.expr) -> str | None:
        """从 for 的 iter 部分提取可迭代对象的变量名。

        只提取纯 for var in list_name 模式。
        range(len(x)) 模式中循环变量是合法的整数下标，使用 x[i] 是正确的，不触发 M4。
        """
        if isinstance(node, ast.Name):
            return node.id
        # range(len(items)) → 循环变量是有效下标，不提取（避免误报）
        return None


class _SubscriptChecker(ast.NodeVisitor):
    """在子树中查找特定名称的下标访问。"""

    def __init__(self, list_name: str, index_name: str):
        self.list_name = list_name
        self.index_name = index_name
        self.found_line = None

    def visit_Subscript(self, node: ast.Subscript):
        if self.found_line is not None:
            return
        # 检查 iterable[loop_var]
        if isinstance(node.value, ast.Name) and node.value.id == self.list_name:
            if isinstance(node.slice, ast.Name) and node.slice.id == self.index_name:
                self.found_line = node.lineno
                return
        self.generic_visit(node)


# =============================================================================
# M5: range 右边界误解
# =============================================================================

class M5RangeBoundaryVisitor(ast.NodeVisitor):
    """
    检测 range() 右边界可能被误解的模式。

    注意：M5 是意图型误区！AST 只能提供辅助信号（range 参数信息），
    不能直接判定学生是否误解。必须结合 stderr、学生问题、测试期望。

    触发条件（累积信号）：
    1. 代码中有 range(start, stop)
    2. 循环体中引用了 stop 值（暗示期望 inclusive）
    3. 或学生问题/stderr 中包含"为什么不到"、"边界"等关键词
    """

    def __init__(self, code_snippet: str = ""):
        self.found = None
        self._done = False
        self.range_calls: list[dict] = []
        self._code = code_snippet

    def visit_For(self, node: ast.For):
        if self._done:
            return
        # 提取 range() 调用
        if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name):
            if node.iter.func.id == 'range':
                info = self._extract_range_info(node)
                if info:
                    self.range_calls.append(info)
        self.generic_visit(node)

    def evaluate(self, stderr: str = "", student_question: str = "") -> dict | None:
        """
        基于 range 调用信息 + 外部信号判断是否是 M5。

        必须在遍历完整个 AST 后调用。

        v3.3（评测漂移修复）：v3.2 曾把"循环体内引用 stop 值"设为唯一门控，
        导致学生**明确问出边界困惑**（"为什么只到4不到5"）时反而不判 M5——
        对意图型误区而言，学生亲口陈述的困惑是最强证据，不应被结构信号一票否决。
        现在门控为：结构信号 或 提问信号，二者有其一。
        提问信号分两档：
          - 强关键词（"为什么只到"等）直接成立；
          - 弱关键词（"最后"）必须同时出现边界数值（stop 或 stop-1），
            防止"最后输出是什么"这类中性提问误触发。
        """
        if not self.range_calls:
            return None

        # 信号权重累加
        score = 0

        # 边界数值集合（用于弱提问信号校验 + 循环后引用检测）
        boundary_nums: set[str] = set()
        for rc in self.range_calls:
            if rc.get("stop_is_constant"):
                boundary_nums.add(str(rc["stop_val"]))
                boundary_nums.add(str(rc["stop_val"] - 1))

        for rc in self.range_calls:
            # 有 stop 参数且循环体中使用了 stop 值
            if rc.get("stop_ref_in_body"):
                score += 0.5
            # stop 是常量且与 start 的差值很小（学生可能在测试边界）
            if rc.get("stop_is_constant") and rc.get("start_is_constant"):
                diff = rc["stop_val"] - rc["start_val"]
                if diff <= 5:
                    score += 0.2

        # 结构信号（弱）：循环变量在循环结束后被引用——
        # 学生把"循环最后一个值"当成 stop 使用的典型形态
        loop_var_after = self._loop_var_used_after_loop()
        if loop_var_after:
            score += 0.2

        stderr_lower = stderr.lower()
        q_lower = student_question.lower()

        # 提问信号（去掉 "range"——它是题目必然词，不是误解信号）
        STRONG_KWS = ("不到", "不包含", "为什么只到", "少一个", "边界", "不包括")
        WEAK_KWS = ("最后",)
        strong_q = any(kw in q_lower for kw in STRONG_KWS)
        weak_q = any(kw in q_lower for kw in WEAK_KWS) and any(
            n in q_lower for n in boundary_nums
        )
        q_signal = strong_q or weak_q
        if q_signal:
            score += 0.5

        # stderr 信号（如 IndexError 场景下的边界描述）
        if any(kw in stderr_lower for kw in STRONG_KWS):
            score += 0.3

        # 门控：结构信号（stop 引用 / 循环后引用）或提问信号，至少其一
        structural = any(rc.get("stop_ref_in_body") for rc in self.range_calls) or loop_var_after
        if score < 0.6 or not (structural or q_signal):
            return None

        # 找到最可疑的 range 调用
        best = max(self.range_calls, key=lambda r: (r.get("stop_ref_in_body", 0), r.get("stop_val", 0)))

        return {
            "misconception_id": "M5",
            "misconception_name": "range 右边界误解",
            "confidence": round(min(0.85, score), 2),
            "evidence": (
                f"第 {best['line']} 行：range({best['start_str']}, {best['stop_str']}) "
                f"— Python 的 range 是左闭右开区间，不包含 {best['stop_str']}。"
                f"如需包含 {best['stop_str']}，应使用 range({best['start_str']}, {best['stop_str']}+1)。"
            ),
            "ast_features": {
                "range_calls": self.range_calls,
                "signal_score": round(score, 2),
                "has_external_signal": q_signal,
                "loop_var_used_after_loop": loop_var_after,
            },
        }

    def _loop_var_used_after_loop(self) -> bool:
        """同一语句块内，for 循环之后是否引用了循环变量。

        只看同级语句块（不跨函数边界），避免把无关同名变量算进来。
        解析失败时保守返回 False。
        """
        try:
            tree = ast.parse(self._code)
        except SyntaxError:
            return False

        def scan(body: list) -> bool:
            for i, stmt in enumerate(body):
                if isinstance(stmt, ast.For) and isinstance(stmt.target, ast.Name):
                    var = stmt.target.id
                    for later in body[i + 1:]:
                        for n in ast.walk(later):
                            if (isinstance(n, ast.Name) and n.id == var
                                    and isinstance(n.ctx, ast.Load)):
                                return True
                # 递归进入嵌套语句块
                for attr in ("body", "orelse", "finalbody"):
                    sub = getattr(stmt, attr, None)
                    if sub and scan(sub):
                        return True
            return False

        return scan(getattr(tree, "body", []))

    def _extract_range_info(self, for_node: ast.For) -> dict | None:
        call = for_node.iter
        if not isinstance(call, ast.Call):
            return None
        args = call.args

        info = {
            "line": for_node.lineno,
            "start_str": "0",
            "stop_str": "?",
            "start_val": 0,
            "stop_val": 0,
            "start_is_constant": True,
            "stop_is_constant": False,
            "stop_ref_in_body": False,
        }

        if len(args) >= 1 and isinstance(args[0], ast.Constant) and isinstance(args[0].value, int):
            info["stop_str"] = str(args[0].value)
            info["stop_val"] = args[0].value
            info["stop_is_constant"] = True
            if len(args) >= 2 and isinstance(args[1], ast.Constant) and isinstance(args[1].value, int):
                info["start_str"] = str(args[0].value)
                info["start_val"] = args[0].value
                info["stop_str"] = str(args[1].value)
                info["stop_val"] = args[1].value
            elif len(args) == 1:
                info["start_str"] = "0"
                info["start_val"] = 0
        elif len(args) >= 2:
            if isinstance(args[0], ast.Constant) and isinstance(args[0].value, int):
                info["start_str"] = str(args[0].value)
                info["start_val"] = args[0].value
                info["start_is_constant"] = True
            else:
                info["start_str"] = "..."
                info["start_is_constant"] = False
            if isinstance(args[1], ast.Constant) and isinstance(args[1].value, int):
                info["stop_str"] = str(args[1].value)
                info["stop_val"] = args[1].value
                info["stop_is_constant"] = True
            else:
                info["stop_str"] = "..."
                info["stop_is_constant"] = False

        # 检查循环体中是否引用了 stop 值（只扫描 body，不扫描整个 for_node）
        if info["stop_is_constant"] and info["stop_val"] > 0:
            stop_name = str(info["stop_val"])
            for stmt in for_node.body:
                for node in ast.walk(stmt):
                    if isinstance(node, ast.Constant) and str(node.value) == stop_name:
                        info["stop_ref_in_body"] = True
                        break
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        if node.func.id in ('print', 'range') and node.args:
                            for a in node.args:
                                if isinstance(a, ast.Constant) and str(a.value) == stop_name:
                                    info["stop_ref_in_body"] = True
                                    break
                if info["stop_ref_in_body"]:
                    break

        return info


# =============================================================================
# M6: print/return 混淆
# =============================================================================

class M6PrintReturnVisitor(ast.NodeVisitor):
    """
    检测函数中 print/return 混淆模式。

    场景 1：函数只用 print 输出，没有 return
        def add(a, b):
            print(a + b)      # 学生期望外部能拿到值

    场景 2：return 后有不可达的 print
        def calc(x):
            return x * 2
            print("done")     # 不可达

    场景 3：将 print() 的返回值赋给变量
        result = print(x)     # print 返回 None
    """

    def __init__(self):
        self.found = None
        self._done = False

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if self._done:
            return

        all_nodes = list(ast.walk(node))
        has_print = False
        has_return = False
        has_return_value = False
        print_lines: list[int] = []
        return_line: int | None = None
        unreachable_print = False
        printed_computed_value = False  # print 的实参是"本函数计算出的变量/表达式"

        # 本函数内被赋值的局部变量名（用于判断 print 的是不是"算出来的值"）
        local_assigned: set[str] = set()
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Assign):
                for tgt in stmt.targets:
                    if isinstance(tgt, ast.Name):
                        local_assigned.add(tgt.id)
            elif isinstance(stmt, ast.AugAssign) and isinstance(stmt.target, ast.Name):
                local_assigned.add(stmt.target.id)

        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Return):
                has_return = True
                return_line = stmt.lineno
                if stmt.value is not None:
                    has_return_value = True
            if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Name):
                if stmt.func.id == 'print':
                    has_print = True
                    print_lines.append(stmt.lineno)
                    # print 的实参里是否含"本函数算出来的变量"或"运算表达式"
                    # v3.3：比较/布尔表达式同样是"算出来的值"
                    # （`print(n % 2 == 0)` 正是调用方 result=f() 拿到 None 的典型 M6）
                    for a in stmt.args:
                        if isinstance(a, ast.Name) and a.id in local_assigned:
                            printed_computed_value = True
                        elif isinstance(a, (ast.BinOp, ast.Compare, ast.BoolOp)):
                            printed_computed_value = True

        # ---- 场景 1（v3.1 收紧）：print 但无 return，且有"计算意图"证据 ----
        # 对抗性审查发现：旧实现对任何"有 print 无 return"的函数一律 M6@0.88，
        # 把 menu()/show()/main() 这类合法展示函数全部误报（高敏感低精确）。
        # 修复：仅当满足"计算意图"证据时才判 M6，且对展示型函数名豁免。
        if has_print and not has_return and not node.name.startswith('__'):
            if self._looks_like_computation(node.name, printed_computed_value):
                self.found = {
                    "misconception_id": "M6",
                    "misconception_name": "print 和 return 混淆",
                    # 有 printed_computed_value 证据置信度高；仅靠函数名时降置信
                    "confidence": 0.85 if printed_computed_value else 0.70,
                    "evidence": (
                        f"函数 '{node.name}()' 第 {node.lineno} 行：把计算结果 print() 出来但没有 return。"
                        f"print() 只是在屏幕显示，调用者拿不到这个值。"
                        f"若希望调用者能使用这个结果，应改用 return 返回。"
                    ),
                    "ast_features": {
                        "function": node.name,
                        "has_print": True,
                        "has_return": False,
                        "print_lines": print_lines,
                        "printed_computed_value": printed_computed_value,
                    },
                }
                self._done = True
                return

        # 场景 2：return 后有不可达的语句
        if has_return and return_line is not None:
            body_stmts = node.body
            past_return = False
            for stmt in body_stmts:
                if past_return:
                    # 检查是否是 Expr(Call(print))
                    if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                        if isinstance(stmt.value.func, ast.Name) and stmt.value.func.id == 'print':
                            unreachable_print = True
                            self.found = {
                                "misconception_id": "M6",
                                "misconception_name": "print 和 return 混淆",
                                "confidence": 0.80,
                                "evidence": (
                                    f"函数 '{node.name}()' 第 {stmt.lineno} 行：print() 在 return "
                                    f"语句之后，是不可达代码。学生可能误以为 return 后还可以继续执行。"
                                ),
                                "ast_features": {
                                    "function": node.name,
                                    "unreachable_print_line": stmt.lineno,
                                    "return_line": return_line,
                                },
                            }
                            self._done = True
                            return
                if isinstance(stmt, ast.Return):
                    past_return = True

        self.generic_visit(node)

    # 场景 3：代码顶层 print 被赋值 → 在 M3 visitor 中也可能检测到，不重复

    # 展示/入口型函数名：这些函数"本来就该只 print 不 return"，豁免 M6
    _DISPLAY_NAMES = frozenset({
        'main', 'menu', 'show', 'display', 'render', 'draw', 'plot',
        'print_menu', 'show_menu', 'welcome', 'banner', 'greet', 'greeting',
        'help', 'usage', 'info', 'log', 'report', 'dump', 'demo', 'run',
    })
    # 计算型函数名前缀/名：暗示"应当算出一个值"
    _COMPUTE_HINTS = frozenset({
        'add', 'sub', 'mul', 'div', 'calc', 'calculate', 'compute',
        'sum', 'total', 'average', 'avg', 'mean', 'count', 'get',
        'find', 'max', 'min', 'product', 'factorial', 'fib', 'square',
        'area', 'volume', 'convert', 'to_', 'parse', 'make', 'build',
    })

    @classmethod
    def _looks_like_computation(cls, func_name: str, printed_computed_value: bool) -> bool:
        """判断"print 无 return"是否真的是 print/return 混淆（v3.1）。

        证据分两路，命中任一即认为有计算意图：
          A) 结构证据：print 的实参是本函数算出来的变量或运算表达式
             （如 `s = a + b; print(s)` 或 `print(a + b)`）——强证据。
          B) 命名证据：函数名像"计算型"（add/calc/get/sum...），
             且不在展示/入口型豁免名单里——弱证据。
        展示/入口型名字（main/menu/show/...）一律豁免，即便打印了变量。
        """
        n = func_name.lower()
        if n in cls._DISPLAY_NAMES:
            return False
        if any(n.startswith(p) or n == p for p in ('print_', 'show_', 'display_')):
            return False
        if printed_computed_value:
            return True
        # 命名证据
        return any(n == h or n.startswith(h) for h in cls._COMPUTE_HINTS)


# =============================================================================
# M7: 类型转换错误
# =============================================================================

class M7TypeConversionVisitor(ast.NodeVisitor):
    """
    检测类型不匹配的运算（主要是字符串+整数）。

    目标代码：
        age = 20
        print('I am ' + age)    # TypeError
        s = 'hello' + 5         # TypeError

    注意：仅通过 AST 无法完全确定运行时类型。结合 stderr 中的 TypeError
    来提升置信度。AST 提供精确的行号和操作数信息。
    """

    def __init__(self, stderr: str = ""):
        self.found = None
        self._done = False
        self._has_typeerror = "typeerror" in stderr.lower() or "can only concatenate" in stderr.lower()
        self._var_types: dict[str, str] = {}

    def _scan_assignments(self, tree: ast.AST):
        """有序扫描赋值语句，建立变量类型映射（后写覆盖前写）。

        使用 Body 级别顺序遍历替代 ast.walk 的无序遍历，
        解决 `x=input(); x=int(x); y=x*2` 的重赋值覆盖问题。
        int()/float()/len() 结果登记为 "num"。
        """
        body = getattr(tree, "body", [])
        if not isinstance(body, list):
            # fallback: 非 Module/FunctionDef 仍然 walk
            self._scan_assignments_walk(tree)
            return
        for stmt in body:
            stmts = [stmt]
            # 展开 if/for/while 的嵌套 body 但不进入内层函数定义
            while stmts:
                s = stmts.pop(0)
                if isinstance(s, ast.FunctionDef):
                    continue  # 不跨函数边界传播类型
                if isinstance(s, ast.Assign) and len(s.targets) == 1 \
                   and isinstance(s.targets[0], ast.Name):
                    name = s.targets[0].id
                    v = s.value
                    if _is_input_call(v):
                        self._var_types[name] = "input"
                    elif isinstance(v, ast.Call) and isinstance(v.func, ast.Name) \
                         and v.func.id in ("int", "float", "len"):
                        self._var_types[name] = "num"
                    elif isinstance(v, ast.Constant):
                        self._var_types[name] = "str" if isinstance(v.value, str) else "num"
                    else:
                        self._var_types.pop(name, None)  # 未知类型，清除旧登记
                # 展开嵌套语句
                for attr in ("body", "orelse"):
                    nested = getattr(s, attr, None)
                    if isinstance(nested, list):
                        stmts.extend(nested)

    def _scan_assignments_walk(self, tree: ast.AST):
        """fallback: 无序扫描（用于非 Module/FunctionDef 的 AST 片段）。"""
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        if isinstance(node.value, ast.Constant):
                            if isinstance(node.value.value, str):
                                self._var_types[target.id] = "str"
                            elif isinstance(node.value.value, (int, float)):
                                self._var_types[target.id] = "int"
                        elif isinstance(node.value, ast.Call) and _is_input_call(node.value):
                            self._var_types[target.id] = "input"

    def visit_Module(self, node: ast.Module):
        self._scan_assignments(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._scan_assignments(node)
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        if self._done:
            return

        left_str = self._is_likely_str(node.left)
        right_int = self._is_likely_int(node.right)
        left_int = self._is_likely_int(node.left)
        right_str = self._is_likely_str(node.right)

        # ---- Add 操作检测 (str + int) ----
        if isinstance(node.op, ast.Add):
            # 精准匹配：两侧都能推断类型
            if (left_str and right_int) or (left_int and right_str):
                confidence = 0.88 if self._has_typeerror else 0.65
                self.found = self._build_result(node, left_str, right_int, confidence, "Add")
                self._done = True
                return

            # 放宽匹配：有 stderr TypeError 信号时，只要一侧是常量就触发
            if self._has_typeerror:
                if self._relaxed_match_impl(node):
                    self._done = True
                    return

        # ---- 算术运算检测 (input() * int / // / % 等) ----
        if isinstance(node.op, (ast.Mult, ast.Div, ast.Sub, ast.Pow, ast.FloorDiv, ast.Mod)):
            # % 特殊处理：左操作数是 str 字面量 → 格式化（不报）；是 input 变量 → M7
            if isinstance(node.op, ast.Mod):
                left_is_str_const = isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)
                if left_is_str_const:
                    self.generic_visit(node)
                    return
            left_input = self._is_input_var(node.left)
            right_input = self._is_input_var(node.right)
            right_num = isinstance(node.right, ast.Constant) and isinstance(node.right.value, (int, float))
            left_num = isinstance(node.left, ast.Constant) and isinstance(node.left.value, (int, float))
            if (left_input and right_num) or (right_input and left_num):
                self.found = {
                    "misconception_id": "M7",
                    "misconception_name": "类型转换错误",
                    "confidence": 0.82,
                    "evidence": (
                        f"第 {node.lineno} 行：input() 返回字符串，参与算术运算前"
                        f"应先用 int() 或 float() 转换类型。"
                    ),
                    "ast_features": {
                        "line": node.lineno,
                        "operation": type(node.op).__name__,
                        "input_involved": True,
                    },
                }
                self._done = True
                return

        self.generic_visit(node)

    def _relaxed_match_impl(self, node: ast.BinOp) -> bool:
        """放宽匹配：有 TypeError 时单侧常量 + 另一侧可能是错误类型。"""
        has_str_const = (isinstance(node.left, ast.Constant) and isinstance(node.left.value, str)) or \
                        (isinstance(node.right, ast.Constant) and isinstance(node.right.value, str))
        has_int_const = (isinstance(node.left, ast.Constant) and isinstance(node.left.value, (int, float))) or \
                        (isinstance(node.right, ast.Constant) and isinstance(node.right.value, (int, float)))
        has_input = _is_input_call(node.left) or _is_input_call(node.right)

        if has_str_const or has_int_const or has_input:
            self.found = self._build_result(
                node, has_str_const or has_input, has_int_const,
                confidence=0.80, operation="Add",
            )
            return True
        return False

    def _build_result(self, node, left_str, right_int, confidence, operation="Add"):
        return {
            "misconception_id": "M7",
            "misconception_name": "类型转换错误",
            "confidence": confidence,
            "evidence": (
                f"第 {node.lineno} 行：字符串与数值直接拼接/运算会导致 TypeError。"
                f"应使用 str() 转换：str(数值) 或使用 f-string：f'文本{{变量}}'。"
            ),
            "ast_features": {
                "line": node.lineno,
                "operation": operation,
                "left_likely_str": left_str,
                "right_likely_int": right_int,
                "has_typeerror": self._has_typeerror,
            },
        }

    def _is_likely_str(self, node: ast.expr) -> bool:
        """判断 AST 节点是否可能是字符串类型。"""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == 'input':
                return True
        if isinstance(node, ast.Name) and self._var_types.get(node.id) in ("str", "input"):
            return True
        return False

    def _is_likely_int(self, node: ast.expr) -> bool:
        """判断 AST 节点是否可能是整数类型。"""
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return True
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in ('len', 'int'):
                return True
        if isinstance(node, ast.Name) and self._var_types.get(node.id) in ("int", "num"):
            return True
        return False

    def _is_input_var(self, node: ast.expr) -> bool:
        """判断节点是否是 input() 调用或其赋值变量。"""
        if isinstance(node, ast.Call) and _is_input_call(node):
            return True
        if isinstance(node, ast.Name) and self._var_types.get(node.id) == "input":
            return True
        return False


def _is_input_call(node: ast.expr) -> bool:
    """判断 AST 节点是否是 input() 调用（返回 str）。"""
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == 'input'
    )


# =============================================================================
# M8: while 循环条件错误
# =============================================================================

class M8WhileInfiniteVisitor(ast.NodeVisitor):
    """
    检测 while 循环可能无限执行的模式。

    场景 1：while True 且循环体内无 break/return/raise
    场景 2：while condition：条件变量在循环体内未被更新
    """

    def __init__(self):
        self.found = None
        self._done = False

    def visit_While(self, node: ast.While):
        if self._done:
            return

        # 场景 1：while True 无退出
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            has_exit = self._has_exit_statement(node)
            if not has_exit:
                self.found = {
                    "misconception_id": "M8",
                    "misconception_name": "while 循环条件错误",
                    "confidence": 0.92,
                    "evidence": (
                        f"第 {node.lineno} 行：while True 循环缺少 break/return/raise "
                        f"等退出语句，会导致无限循环。应在循环体内添加条件判断和 break。"
                    ),
                    "ast_features": {
                        "pattern": "while_true_no_exit",
                        "line": node.lineno,
                    },
                }
                self._done = True
                return

        # 场景 2：条件变量在循环体内未更新
        cond_vars = self._extract_condition_vars(node.test)
        if cond_vars:
            modified_vars = self._extract_modified_vars(node)
            unchanged = cond_vars - modified_vars
            # v3.1 修复（假阴性优先）：只要"任意一个"条件变量在体内被更新，
            # 循环就有合理的收敛路径（如 `while count < len(x): count += 1`，
            # count 收敛向 len(x)；或 `while lo < hi: lo += 1`）。此时不报 M8，
            # 宁可漏一个真无限循环，也不误伤会收敛的正常循环——教学场景
            # 误报（错怪写对的学生）代价更高。仅当"所有"条件变量都没被动过
            # 才判定可疑。
            any_modified = bool(cond_vars & modified_vars)
            if unchanged and not any_modified:
                has_exit = self._has_exit_statement(node)
                if not has_exit:
                    self.found = {
                        "misconception_id": "M8",
                        "misconception_name": "while 循环条件错误",
                        "confidence": 0.80 if len(unchanged) == len(cond_vars) else 0.65,
                        "evidence": (
                            f"第 {node.lineno} 行：while 循环的条件变量 "
                            f"{unchanged} 在循环体内未更新，可能导致无限循环。"
                            f"请检查是否遗漏了递增/递减/赋值或 break 语句。"
                        ),
                        "ast_features": {
                            "pattern": "condition_var_unchanged",
                            "line": node.lineno,
                            "condition_vars": list(cond_vars),
                            "unchanged_vars": list(unchanged),
                        },
                    }
                    self._done = True
                    return
        self.generic_visit(node)

    @staticmethod
    def _has_exit_statement(while_node: ast.While) -> bool:
        """检查 while 循环体内是否有退出语句。"""
        for node in ast.walk(while_node):
            # break 语句
            if isinstance(node, ast.Break):
                return True
            # return 语句（在函数内的 while）
            if isinstance(node, ast.Return):
                return True
            # raise 语句
            if isinstance(node, ast.Raise):
                return True
        return False

    # 常见内置/全局名，出现在 while 条件里不是"需要在循环体内更新的状态变量"
    _COND_IGNORE_NAMES = frozenset({
        'True', 'False', 'None',
        'len', 'range', 'int', 'float', 'str', 'bool', 'abs', 'min', 'max',
        'sum', 'any', 'all', 'sorted', 'reversed', 'enumerate', 'input',
        'print', 'ord', 'chr', 'set', 'list', 'dict', 'tuple',
    })

    @staticmethod
    def _extract_condition_vars(test_node: ast.expr) -> set[str]:
        """提取 while 条件中"真正的状态变量"名（v3.1 修复）。

        关键修复（对抗性审查发现的假阳性）：
          `while len(s) > 0: s.pop()` 中，旧实现把 `len` 也当成条件变量，
          而 `len` 永远不会"被更新"，于是误报 M8。修复方式：
            1. 排除处于"函数被调用位置"(Call.func) 的名字；
            2. 排除内置函数名白名单。
          这样条件里真正需要收敛的状态变量只剩 `s`，而 `s.pop()` 已使
          `_extract_modified_vars` 将 `s` 标记为已修改 → 不再误报。
        """
        # 先收集所有"位于 Call.func 位置"的名字（这些是被调用的函数，不是状态变量）
        callee_names: set[str] = set()
        for node in ast.walk(test_node):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                callee_names.add(node.func.id)

        vars_set: set[str] = set()
        for node in ast.walk(test_node):
            if isinstance(node, ast.Name):
                name = node.id
                if name in callee_names:
                    continue
                if name in M8WhileInfiniteVisitor._COND_IGNORE_NAMES:
                    continue
                vars_set.add(name)
        return vars_set

    @staticmethod
    def _extract_modified_vars(while_node: ast.While) -> set[str]:
        """提取 while 循环体内被修改的变量名。"""
        modified: set[str] = set()
        for node in ast.walk(while_node):
            # i += 1 类型 (AugAssign)
            if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
                modified.add(node.target.id)
            # i = i + 1 类型 (Assign)
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        modified.add(target.id)
            # for 循环中的循环变量也会更新
            if isinstance(node, ast.For):
                if isinstance(node.target, ast.Name):
                    modified.add(node.target.id)
            # 方法调用接收者可能被修改（items.pop() → items 视为被改）
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                recv = node.func.value
                if isinstance(recv, ast.Name):
                    modified.add(recv.id)
        return modified
