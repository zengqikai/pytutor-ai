import sys
sys.path.insert(0, "/home/claude/shim")
sys.path.insert(0, "/home/claude/out/backend")
from app.analysis.ast_analyzer import analyze_misconceptions
def d(code, stderr="", q=""):
    r = analyze_misconceptions(code, stderr, q)
    return ",".join(f"{x['misconception_id']}@{x['confidence']}" for x in r) if r else "clean"

CASES = [
 # 之前的 2 个新假阳性 —— 应变 clean
 ("dict来自函数返回(FP)", "def get():\n    return {'a':1}\nd=get()\nfor k in d:\n    print(d[k])", "clean"),
 ("while len(s)>0:pop(FP)", "s=[1,2]\nwhile len(s)>0:\n    s.pop()", "clean"),
 ("while len(s):pop(FP)", "s=[1,2]\nwhile len(s):\n    s.pop()", "clean"),
 ("while count<len(x)递增(FP)", "x=[1,2]\ncount=0\nwhile count<len(x):\n    count+=1", "clean"),
 # M6 展示函数 —— 应变 clean
 ("menu纯print(FP)", "def menu():\n    print('a')\n    print('b')", "clean"),
 ("show副作用(FP)", "def show(items):\n    for i in items:\n        print(i)", "clean"),
 ("main入口(FP)", "def main():\n    print('start')\nmain()", "clean"),
 # M4 dict 各来源 —— 应变 clean
 ("dict推导式(FP)", "d={k:1 for k in range(3)}\nfor k in d:\n    print(d[k])", "clean"),
 ("dict形参(FP)", "def f(d):\n    for k in d:\n        print(d[k])", "clean"),
 ("dict注解(FP)", "d: dict = {}\nfor k in d:\n    print(d[k])", "clean"),
 # ===== 真阳性回归保护（必须仍然报）=====
 ("M6真-add只print", "def add(a,b):\n    print(a+b)", "M6"),
 ("M6真-calc算了变量", "def calc(x):\n    r=x*2\n    print(r)", "M6"),
 ("M6真-return后不可达", "def f(x):\n    return x\n    print('dead')", "M6"),
 ("M4真-value当索引", "items=['a','b']\nfor i in items:\n    print(items[i])", "M4"),
 ("M8真-while无更新", "i=0\nwhile i<10:\n    print(i)", "M8"),
 ("M8真-whileTrue无break", "while True:\n    print('x')", "M8"),
 ("M3真-append赋值", "new=[].append(5)", "M3"),
 ("M7真-input未转", "n=input()\nprint(n%3)", "M7"),
 ("M1真-赋值当比较", "if x=3:\n    print(1)", "M1"),
 # ===== 更多对抗（防止修过头/欠修）=====
 ("dict字面量遍历", "d={'a':1}\nfor k in d:\n    print(d[k])", "clean"),
 ("真index混淆-list参数", "def f(items):\n    for i in items:\n        print(items[i])", "?"),  # items 是 list 但名字不像 dict
 ("while标志break", "done=False\nwhile not done:\n    done=True", "clean"),
 ("while纯无限真", "while True:\n    x=1", "M8"),
]
bad=[]
for label, code, expect in CASES:
    r = d(code)
    flag=""
    if expect=="clean" and r!="clean":
        flag=" ← 仍假阳性!"; bad.append(label)
    elif expect in ("M1","M3","M4","M6","M7","M8") and expect not in r:
        flag=" ← 漏报回归!"; bad.append(label)
    print(f"{label:<24}{r:<18}{expect:<8}{flag}")
print(f"\n剩余问题 {len(bad)}: {bad}")
