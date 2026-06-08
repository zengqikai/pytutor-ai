"""
初始知识库数据导入脚本
======================

预置 Python 基础知识点，让 RAG 知识库有初始内容。

运行方式：
    cd backend
    python scripts/seed_knowledge.py

每条知识包含：标题（对应知识点标签）、Markdown 格式的教学内容、难度级别。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database.session import AsyncSessionFactory
from app.rag.retriever import retriever
from app.services.rag_service import ingest_document

# =============================================================================
# Python 基础知识点
# =============================================================================

KNOWLEDGE_BASE = [
    # --- 变量与数据类型 ---
    {
        "title": "Python 变量与赋值",
        "concepts": "variables,assignment",
        "difficulty": "beginner",
        "content": """# Python 变量与赋值

## 什么是变量

变量就像一个带标签的盒子，用来存放数据。在 Python 中，你不需要声明变量的类型——Python 会自动推断。

## 变量的命名规则

- 变量名只能包含字母、数字和下划线
- 变量名不能以数字开头
- 变量名区分大小写（`name` 和 `Name` 是不同的变量）
- 不能使用 Python 的关键字（如 `if`、`for`、`while`）

## 赋值语句

```python
# 基本赋值
name = "小明"
age = 18
height = 1.75

# 多重赋值
a, b, c = 1, 2, 3

# 交换两个变量的值（Python 特有技巧）
a, b = b, a
```

## 常见错误

1. **NameError：name 'xxx' is not defined**
   使用了未定义的变量。检查是否正确拼写了变量名。

2. **SyntaxError：invalid syntax**
   变量名不合法（如以数字开头）。
""",
    },
    {
        "title": "Python 数据类型",
        "concepts": "data_types,string,int,float,list,dict,tuple,set,bool",
        "difficulty": "beginner",
        "content": """# Python 基本数据类型

## 数字类型

```python
# 整数 (int)
age = 25
count = -10

# 浮点数 (float)
price = 19.99
pi = 3.14159
```

## 字符串 (str)

```python
# 单引号或双引号都可以
name = '小明'
message = "Hello, World!"

# 字符串拼接
greeting = "Hello, " + name  # "Hello, 小明"

# f-string（推荐）
greeting = f"Hello, {name}"  # Python 3.6+
```

## 布尔值 (bool)

```python
is_student = True
is_admin = False
```

## 类型转换

```python
# 字符串转整数
num = int("123")  # 123

# 整数转字符串
text = str(456)   # "456"

# 转浮点数
price = float("19.99")  # 19.99
```

## 常见错误

**TypeError：can only concatenate str (not "int") to str**
不能将字符串和整数直接拼接。需要先转换：`"年龄：" + str(18)`
""",
    },
    {
        "title": "Python 列表 (list)",
        "concepts": "list,indexing,slicing,append,remove",
        "difficulty": "beginner",
        "content": """# Python 列表 (list)

## 什么是列表

列表是一个有序的容器，可以存放任意类型的数据。就像一个带编号的储物柜。

```python
# 创建列表
fruits = ["苹果", "香蕉", "橘子"]
numbers = [1, 2, 3, 4, 5]
mixed = [1, "hello", 3.14, True]
```

## 访问元素（索引）

索引从 0 开始！第一个元素的下标是 0。

```python
fruits = ["苹果", "香蕉", "橘子"]
print(fruits[0])   # "苹果"
print(fruits[1])   # "香蕉"
print(fruits[-1])  # "橘子"（负数索引从末尾开始）
```

## 切片

```python
numbers = [0, 1, 2, 3, 4, 5]
print(numbers[0:3])   # [0, 1, 2]
print(numbers[2:])    # [2, 3, 4, 5]
print(numbers[:4])    # [0, 1, 2, 3]
print(numbers[::2])   # [0, 2, 4]（步长为 2）
```

## 常用方法

```python
fruits = ["苹果", "香蕉"]

# 添加
fruits.append("橘子")     # 末尾添加
fruits.insert(1, "草莓")  # 指定位置插入

# 删除
fruits.remove("香蕉")     # 按值删除
last = fruits.pop()      # 弹出最后一个
del fruits[0]            # 按索引删除

# 查找
len(fruits)              # 列表长度
"苹果" in fruits         # 检查是否存在
fruits.index("苹果")     # 查找索引
```

## 常见错误

**IndexError：list index out of range**
索引超出了列表范围。注意：长度为 n 的列表，索引范围是 0 到 n-1。
""",
    },
    {
        "title": "Python for 循环",
        "concepts": "for_loop,range,iteration,list",
        "difficulty": "beginner",
        "content": """# Python for 循环

## 什么是 for 循环

for 循环用于重复执行一段代码，每次处理序列中的一个元素。

```python
# 遍历列表
fruits = ["苹果", "香蕉", "橘子"]
for fruit in fruits:
    print(f"我喜欢吃{fruit}")
```

## range() 函数

`range()` 生成一个数字序列，常用于循环指定次数。

```python
# range(n): 0 到 n-1
for i in range(5):
    print(i)  # 0, 1, 2, 3, 4

# range(start, stop): start 到 stop-1
for i in range(2, 6):
    print(i)  # 2, 3, 4, 5

# range(start, stop, step): 带步长
for i in range(0, 10, 2):
    print(i)  # 0, 2, 4, 6, 8
```

## 遍历字典

```python
student = {"name": "小明", "age": 18, "score": 95}

# 遍历键
for key in student:
    print(key)

# 遍历键和值
for key, value in student.items():
    print(f"{key}: {value}")
```

## 常见错误

1. **忘记冒号**：`for i in range(5)` 后面必须有 `:`
2. **忘记缩进**：循环体必须缩进 4 个空格
3. **range(n) 的范围**：是 0 到 n-1，不是 1 到 n
""",
    },
    {
        "title": "Python 条件判断 (if/elif/else)",
        "concepts": "if_statement,elif,else,comparison,boolean",
        "difficulty": "beginner",
        "content": """# Python 条件判断

## 基本语法

```python
if 条件:
    执行代码
elif 另一个条件:
    执行代码
else:
    执行代码
```

## 比较运算符

| 运算符 | 含义 | 示例 |
|--------|------|------|
| `==` | 等于 | `x == 5` |
| `!=` | 不等于 | `x != 5` |
| `>` | 大于 | `x > 5` |
| `<` | 小于 | `x < 5` |
| `>=` | 大于等于 | `x >= 5` |
| `<=` | 小于等于 | `x <= 5` |

## 逻辑运算符

```python
# and: 两个条件都成立
if age > 18 and score >= 60:
    print("及格")

# or: 至少一个条件成立
if temperature < 0 or temperature > 40:
    print("极端温度")

# not: 取反
if not is_raining:
    print("可以出去玩")
```

## 示例

```python
score = 85

if score >= 90:
    grade = "A"
elif score >= 80:
    grade = "B"
elif score >= 70:
    grade = "C"
elif score >= 60:
    grade = "D"
else:
    grade = "F"

print(f"你的成绩是: {grade}")
```

## 常见错误

1. **用 = 代替 ==**：`if x = 5` 是赋值，`if x == 5` 才是比较
2. **忘记冒号**：每个条件语句后面都需要 `:`
3. **缩进不一致**：同一层级的代码必须对齐
""",
    },
    {
        "title": "Python 函数定义与调用",
        "concepts": "function,def,return,parameters,arguments",
        "difficulty": "beginner",
        "content": """# Python 函数

## 定义函数

```python
def 函数名(参数):
    '''文档字符串：描述函数功能'''
    执行代码
    return 返回值
```

## 简单示例

```python
def greet(name):
    '''向指定的人打招呼'''
    return f"你好，{name}！"

# 调用函数
print(greet("小明"))  # "你好，小明！"
```

## 参数类型

```python
# 位置参数
def add(a, b):
    return a + b

# 默认参数
def greet(name, greeting="你好"):
    return f"{greeting}，{name}！"

# 关键字参数
greet(name="小明", greeting="Hi")
```

## 返回值

```python
# 无返回值（返回 None）
def say_hello():
    print("hello")

# 单个返回值
def square(x):
    return x * x

# 多个返回值（打包为元组）
def get_min_max(numbers):
    return min(numbers), max(numbers)

min_val, max_val = get_min_max([3, 1, 4, 1, 5])
```

## 常见错误

1. **忘记 return**：函数默认返回 None
2. **参数顺序**：调用时参数顺序要对应
3. **变量作用域**：函数内部定义的变量，外部无法访问
""",
    },
    {
        "title": "Python 字符串操作",
        "concepts": "string,method,format,fstring,slice",
        "difficulty": "beginner",
        "content": """# Python 字符串操作

## 创建字符串

```python
s1 = 'hello'
s2 = "world"
s3 = '''多行
字符串'''
```

## 常用方法

```python
s = "Hello, Python"

# 大小写转换
s.upper()       # "HELLO, PYTHON"
s.lower()       # "hello, python"
s.title()       # "Hello, Python"

# 去除空白
"  hello  ".strip()   # "hello"
"  hello  ".lstrip()  # "hello  "
"  hello  ".rstrip()  # "  hello"

# 查找和替换
s.find("Python")       # 7（位置索引）
s.replace("Python", "World")  # "Hello, World"
"hello" in s            # True

# 分割和连接
"a,b,c".split(",")      # ["a", "b", "c"]
"-".join(["a", "b", "c"])  # "a-b-c"
```

## 格式化

```python
name = "小明"
age = 18

# f-string（推荐）
f"{name} 今年 {age} 岁"

# format 方法
"{} 今年 {} 岁".format(name, age)

# 旧式 %
"%s 今年 %d 岁" % (name, age)
```

## 切片

字符串支持切片操作：

```python
s = "Python"
s[0]      # "P"
s[-1]     # "n"
s[0:3]    # "Pyt"
s[::-1]   # "nohtyP"（反转字符串）
```
""",
    },
    {
        "title": "Python 字典 (dict)",
        "concepts": "dict,dictionary,key_value,mapping",
        "difficulty": "beginner",
        "content": """# Python 字典 (dict)

## 什么是字典

字典存储键值对（key-value pair）。就像一个真实的字典——通过"词"（key）来查找"定义"（value）。

```python
# 创建字典
student = {
    "name": "小明",
    "age": 18,
    "score": 95
}
```

## 访问和修改

```python
# 访问
student["name"]       # "小明"
student.get("grade", "N/A")  # 安全访问，键不存在返回默认值

# 添加/修改
student["grade"] = "A"  # 添加新键
student["age"] = 19     # 修改已有键

# 删除
del student["score"]
age = student.pop("age")
```

## 遍历

```python
for key in student:
    print(key, student[key])

for key, value in student.items():
    print(f"{key}: {value}")
```

## 常见错误

**KeyError：'xxx'**
访问了不存在的键。使用 `dict.get('xxx')` 代替 `dict['xxx']` 可以避免此错误。
""",
    },
    {
        "title": "Python 异常处理 (try/except)",
        "concepts": "exception,try_except,error_handling,ValueError,TypeError",
        "difficulty": "intermediate",
        "content": """# Python 异常处理

## 基本语法

```python
try:
    # 可能出错的代码
    result = 10 / 0
except ZeroDivisionError:
    # 处理特定错误
    print("不能除以零！")
except Exception as e:
    # 处理其他错误
    print(f"出错了: {e}")
else:
    # 没有异常时执行
    print("计算成功")
finally:
    # 无论如何都执行
    print("清理资源")
```

## 常见异常类型

| 异常 | 原因 |
|------|------|
| `ValueError` | 值不合法（如 int("abc")） |
| `TypeError` | 类型错误（如 "a" + 1） |
| `IndexError` | 索引超出范围 |
| `KeyError` | 字典键不存在 |
| `ZeroDivisionError` | 除以零 |
| `FileNotFoundError` | 文件不存在 |
| `SyntaxError` | 语法错误（无法被 catch） |
| `NameError` | 变量未定义 |

## 示例

```python
def safe_divide(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        print("错误：不能除以零")
        return None
    except TypeError:
        print("错误：参数类型不正确")
        return None
```
""",
    },
    {
        "title": "Python 列表推导式",
        "concepts": "list_comprehension,for_loop,list",
        "difficulty": "intermediate",
        "content": """# Python 列表推导式

列表推导式是一种简洁的创建列表的方式。

## 基本语法

```python
[表达式 for 变量 in 可迭代对象 if 条件]
```

## 示例

```python
# 普通写法
squares = []
for i in range(10):
    squares.append(i * i)

# 推导式写法（一行搞定）
squares = [i * i for i in range(10)]
# [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]

# 带条件
even_squares = [i * i for i in range(10) if i % 2 == 0]
# [0, 4, 16, 36, 64]

# 嵌套循环
pairs = [(x, y) for x in range(3) for y in range(3) if x != y]
```

## 注意事项

列表推导式虽然简洁，但不要滥用。如果逻辑太复杂，用普通 for 循环更清晰。
""",
    },
]

# =============================================================================
# 主函数
# =============================================================================

async def seed():
    print("开始导入知识库...")
    count = 0

    async with AsyncSessionFactory() as db:
        for kb in KNOWLEDGE_BASE:
            try:
                doc = await ingest_document(
                    db=db,
                    title=kb["title"],
                    content=kb["content"],
                    difficulty=kb["difficulty"],
                    concepts=kb["concepts"],
                )
                count += 1
                print(f"  [{count}] {doc.title} ({getattr(doc, '_chunk_count', 0)} chunks)")
            except Exception as e:
                print(f"  [FAIL] {kb['title']}: {e}")

    print(f"\n导入完成！共 {count} 篇文档，索引中 {len(retriever._chunks)} 个 chunk。")


if __name__ == "__main__":
    asyncio.run(seed())
