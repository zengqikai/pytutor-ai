"""对抗性审查：独立验证 SRS 3.1 声称的四类假阳性是否已修复，并主动寻找新的假阳性。"""
import sys
sys.path.insert(0, "/home/claude/shim")
sys.path.insert(0, ".")
from app.analysis.ast_analyzer import analyze_misconceptions

def diag(code, stderr="", q=""):
    res = analyze_misconceptions(code, stderr, q)
    if not res:
        return "—(无检出)"
    return ",".join(f"{r['misconception_id']}@{r['confidence']}" for r in res)

# (标签, 代码, 期望: 'clean'=不应报, 或应报的 M 号)
CASES = [
    # ---- SRS 3.1 声称已修的 4 类假阳性 (hard negatives, 应 clean) ----
    ("M4字典遍历-字面量", "d={'a':1,'b':2}\nfor k in d:\n    print(d[k])", "clean"),
    ("M4字典遍历-dict()", "d=dict(a=1)\nfor k in d:\n    print(d[k])", "clean"),
    ("M8-pop收敛", "items=[1,2,3]\nwhile items:\n    items.pop()", "clean"),
    ("M8-popleft收敛", "from collections import deque\nq=deque([1,2])\nwhile q:\n    x=q.popleft()", "clean"),
    ("M5-正常range题面", "for i in range(1,10):\n    print(i)", "clean_q"),  # q含range
    ("M7-已完成转换", "x=input()\nx=int(x)\ny=x*2\nprint(y)", "clean"),
    ("M3-pop合法", "items=[1,2,3]\nx=items.pop()\nprint(x)", "clean"),
    ("纯展示函数", "def menu():\n    print('1.开始')\n    print('2.退出')", "M6?"),  # 有争议
    # ---- 应该报的真阳性 (回归保护) ----
    ("M3真-append赋值", "items=[]\nnew=items.append(5)", "M3"),
    ("M4真-value当索引", "items=['a','b','c']\nfor i in items:\n    print(items[i])", "M4"),
    ("M7真-input未转换", "name=input()\nprint(name%3)", "M7"),
    ("M8真-while无更新", "i=0\nwhile i<10:\n    print(i)", "M8"),
    ("M8真-whileTrue无break", "while True:\n    print('hi')", "M8"),
    ("M6真-只print无return", "def add(a,b):\n    print(a+b)", "M6"),
    ("M1真-赋值当比较", "x=5\nif x=3:\n    print('yes')", "M1"),
    # ---- 我主动构造的新对抗样本（探测未覆盖的假阳性/漏报）----
    ("新-嵌套dict遍历", "d={'a':1}\nfor k in d:\n    for j in d:\n        print(d[k],d[j])", "clean"),
    ("新-dict来自函数返回", "def get():\n    return {'a':1}\nd=get()\nfor k in d:\n    print(d[k])", "clean?"),  # dict_vars无法追踪
    ("新-while len收敛", "s=[1,2,3]\nwhile len(s)>0:\n    s.pop()", "clean?"),
    ("新-字符串格式化%", "print('%d'%5)", "clean"),
    ("新-合法enumerate", "xs=[1,2]\nfor i,v in enumerate(xs):\n    print(xs[i])", "clean"),
    ("新-input转int后-min", "n=int(input())\nfor i in range(n):\n    print(i)", "clean"),
    ("新-return后print真不可达", "def f(x):\n    return x\n    print('dead')", "M6"),
    ("新-while标志位break", "done=False\nwhile not done:\n    done=True", "clean"),
    ("新-while计数器方法改", "stack=[1]\nwhile stack:\n    top=stack.pop()\n    print(top)", "clean"),
    ("新-M7假阳-str乘int合法", "print('='*20)", "clean"),  # 'abc'*3 合法!
    ("新-M7假阳-列表乘", "row=[0]*5\nprint(row)", "clean"),
]

print(f"{'标签':<26}{'诊断结果':<20}{'期望':<10}")
print("-"*60)
issues=[]
for label, code, expect in CASES:
    q = "range 到 10" if expect=="clean_q" else ""
    r = diag(code, "", q)
    flag=""
    if expect.startswith("clean") and r!="—(无检出)":
        flag=" ← 疑似假阳性!"
        issues.append((label,r,expect))
    if expect in ("M1","M3","M4","M6","M7","M8") and expect not in r:
        flag=" ← 漏报!"
        issues.append((label,r,expect))
    print(f"{label:<26}{r:<20}{expect:<10}{flag}")

print("\n=== 发现的问题 ===")
for i in issues:
    print(" -", i)
print(f"\n共 {len(issues)} 个疑点")
