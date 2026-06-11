export interface McExercise {
  id: string;
  misconceptionCode: string;
  title: string;
  type: "fix_error" | "predict_output" | "fill_blank" | "identify_issue";
  description: string;
  wrongCode: string;
  correctCode: string;
  hint: string;
  explanation: string;
}

export const MISCONCEPTION_EXERCISES: McExercise[] = [
  // M1: 赋值与比较混淆
  {
    id: "mc1-1", misconceptionCode: "M1", type: "fix_error",
    title: "if 条件中的 = 和 ==",
    description: "下面的代码想判断 x 是否等于 10，但有一个错误。请找出并修复。",
    wrongCode: `x = 10\nif x = 10:\n    print("x is ten")`,
    correctCode: `x = 10\nif x == 10:\n    print("x is ten")`,
    hint: "if 后面应该用比较运算符 == 而不是赋值运算符 =",
    explanation: "单个 = 是赋值（把右边放到左边），双 == 才是比较（判断左右是否相等）。if 条件中必须用 ==。",
  },
  {
    id: "mc1-2", misconceptionCode: "M1", type: "predict_output",
    title: "判断这段代码会报什么错",
    description: "阅读代码，猜测运行结果。然后在 Code Lab 中验证。",
    wrongCode: `score = 90\nif score = 100:\n    print("满分")\nelse:\n    print("不是满分")`,
    correctCode: `score = 90\nif score == 100:\n    print("满分")\nelse:\n    print("不是满分")`,
    hint: "注意 if 后面的 = 号有几个？单个 = 在 if 里会报 SyntaxError。",
    explanation: "if score = 100 会报 SyntaxError，因为 Python 不允许在条件表达式中使用赋值 =。应该用 score == 100。",
  },

  // M2: 缩进理解错误
  {
    id: "mc2-1", misconceptionCode: "M2", type: "fix_error",
    title: "修复缩进错误",
    description: "下面的代码缺少必要的缩进。请修复。",
    wrongCode: `for i in range(3):\nprint(i)`,
    correctCode: `for i in range(3):\n    print(i)`,
    hint: "for 循环体中的代码需要向右缩进（通常 4 个空格）。",
    explanation: "Python 用缩进来表示代码块。for/if/def 后面的代码如果属于它们，必须缩进。",
  },
  {
    id: "mc2-2", misconceptionCode: "M2", type: "predict_output",
    title: "哪个 print 属于 if？",
    description: "阅读代码，判断哪些 print 属于 if 语句，哪些不属于。",
    wrongCode: `age = 20\nif age >= 18:\n    print("成人")\n    print("可以投票")\nprint("程序结束")`,
    correctCode: `age = 20\nif age >= 18:\n    print("成人")\n    print("可以投票")\nprint("程序结束")`,
    hint: "缩进相同的行属于同一个代码块。不缩进的行不属于 if。",
    explanation: ""成人"和"可以投票"都缩进了，属于 if 块。"程序结束"没有缩进，所以无论 age 是多少都会执行。",
  },

  // M3: append 返回值误解
  {
    id: "mc3-1", misconceptionCode: "M3", type: "fix_error",
    title: "append 不等于返回新列表",
    description: "下面的代码想给列表添加元素并打印，但打印出了 None。请修复。",
    wrongCode: `numbers = [1, 2, 3]\nnew_numbers = numbers.append(4)\nprint(new_numbers)`,
    correctCode: `numbers = [1, 2, 3]\nnumbers.append(4)\nprint(numbers)`,
    hint: "append() 直接修改原列表，不返回新列表。应该打印原列表。",
    explanation: "append() 是原地操作（in-place），它修改列表本身并返回 None。正确做法：先 append，再打印原列表。",
  },
  {
    id: "mc3-2", misconceptionCode: "M3", type: "predict_output",
    title: "sort 和 sorted 的区别",
    description: "比较两段代码，哪个返回排序后的列表？",
    wrongCode: `nums = [3, 1, 2]\nresult = nums.sort()\nprint(result)`,
    correctCode: `nums = [3, 1, 2]\nsorted_nums = sorted(nums)\nprint(sorted_nums)`,
    hint: "sort() 返回 None，sorted() 返回排序后的新列表。",
    explanation: "sort() 是原地排序，返回 None。sorted() 返回排序后的新列表，原列表不变。",
  },

  // M4: index/value 混淆
  {
    id: "mc4-1", misconceptionCode: "M4", type: "fix_error",
    title: "for 循环中的 i 是元素还是索引？",
    description: "这段代码本意是打印水果名称，但报错了。请修复。",
    wrongCode: `fruits = ["apple", "banana", "cherry"]\nfor i in fruits:\n    print(fruits[i])`,
    correctCode: `fruits = ["apple", "banana", "cherry"]\nfor f in fruits:\n    print(f)`,
    hint: "for i in list 中的 i 就是列表元素本身，不是索引。直接用 i 即可。",
    explanation: "for i in fruits 遍历时，i 依次是 'apple'、'banana'、'cherry'。不需要再用 fruits[i]（那是在用字符串做索引，会报错）。",
  },
  {
    id: "mc4-2", misconceptionCode: "M4", type: "predict_output",
    title: "这段代码输出什么？",
    description: "仔细思考 for 循环中变量的值，然后预测输出。",
    wrongCode: `items = [10, 20, 30]\nfor x in items:\n    print(x)`,
    correctCode: `items = [10, 20, 30]\nfor x in items:\n    print(x)`,
    hint: "x 依次取列表中的每个元素值，不是索引。",
    explanation: "输出：10、20、30。x 每次取列表中的一个元素值，不是索引号。",
  },

  // M5: range 右边界
  {
    id: "mc5-1", misconceptionCode: "M5", type: "predict_output",
    title: "range(1, 5) 包含哪些数？",
    description: "预测输出，然后运行验证。",
    wrongCode: `for i in range(1, 5):\n    print(i)`,
    correctCode: `for i in range(1, 5):\n    print(i)`,
    hint: "range(1, 5) 从 1 开始，在 5 之前停止。",
    explanation: "输出：1 2 3 4。range(开始, 结束) 包含开始值，不包含结束值。这就是「左闭右开」。",
  },
  {
    id: "mc5-2", misconceptionCode: "M5", type: "fix_error",
    title: "打印 1 到 5（包含 5）",
    description: "修改代码让它打印 1 到 5（包含 5）。",
    wrongCode: `for i in range(1, 5):\n    print(i)`,
    correctCode: `for i in range(1, 6):\n    print(i)`,
    hint: "如果想包含 5，结束值应该设为 6（比 5 大 1）。",
    explanation: "要打印 1 到 5，需要 range(1, 6)。因为 range 不包含结束值，所以要 +1。",
  },

  // M6: print/return 混淆
  {
    id: "mc6-1", misconceptionCode: "M6", type: "fix_error",
    title: "函数应该返回结果，不是打印",
    description: "这个函数想返回 a+b 的结果，但调用者拿到了 None。修复它。",
    wrongCode: `def add(a, b):\n    print(a + b)\n\nresult = add(3, 5)\nprint("结果是:", result)`,
    correctCode: `def add(a, b):\n    return a + b\n\nresult = add(3, 5)\nprint("结果是:", result)`,
    hint: "print 只是显示，return 才是把结果交回。",
    explanation: "print() 输出到屏幕但不返回给调用者。要用 return 把计算结果交回给 result 变量。",
  },
  {
    id: "mc6-2", misconceptionCode: "M6", type: "predict_output",
    title: "这段代码会输出什么？",
    description: "预测两段代码的输出差异。",
    wrongCode: `def test():\n    print("A")\n    return "B"\n\nx = test()\nprint(x)`,
    correctCode: `def test():\n    print("A")\n    return "B"\n\nx = test()\nprint(x)`,
    hint: "print 在函数内输出 A，return 返回 B 给 x，然后 print(x) 输出 B。",
    explanation: "输出：A（来自函数内 print）然后 B（来自 print(x)）。print 显示但不返回，return 返回但不显示。",
  },

  // M7: 类型转换
  {
    id: "mc7-1", misconceptionCode: "M7", type: "fix_error",
    title: "字符串 + 数字的 TypeError",
    description: "修复类型错误：不能直接用 + 连接字符串和数字。",
    wrongCode: `age = 20\nprint("我今年" + age + "岁")`,
    correctCode: `age = 20\nprint("我今年" + str(age) + "岁")`,
    hint: "用 str() 把数字转成字符串后再拼接。",
    explanation: "Python 不能自动把数字转成字符串来拼接。需要用 str(age) 显式转换。或者用逗号：print('我今年', age, '岁')。",
  },
  {
    id: "mc7-2", misconceptionCode: "M7", type: "fix_error",
    title: "input 得到的字符串不能直接计算",
    description: "用户输入年龄后想计算明年多大，但程序报错了。修复它。",
    wrongCode: `age = input("年龄: ")\nprint("明年你", age + 1, "岁")`,
    correctCode: `age = input("年龄: ")\nprint("明年你", int(age) + 1, "岁")`,
    hint: "input() 返回的是字符串，需要用 int() 转成数字才能计算。",
    explanation: "input() 永远返回字符串。要数学运算必须先 int() 或 float() 转换。",
  },

  // M8: while 循环条件
  {
    id: "mc8-1", misconceptionCode: "M8", type: "fix_error",
    title: "while 循环变量忘记更新",
    description: "下面的代码进入了死循环。修复它，让它只打印 0 到 4。",
    wrongCode: `count = 0\nwhile count < 5:\n    print(count)`,
    correctCode: `count = 0\nwhile count < 5:\n    print(count)\n    count = count + 1`,
    hint: "while 循环内部需要更新循环变量，否则条件永远为真。",
    explanation: "count 始终是 0，永远 < 5，所以死循环。需要在循环体里 count = count + 1（或 count += 1）来更新变量。",
  },
  {
    id: "mc8-2", misconceptionCode: "M8", type: "predict_output",
    title: "预测 while 循环的输出",
    description: "仔细追踪循环变量的变化，预测输出。",
    wrongCode: `n = 5\nwhile n > 0:\n    print(n)\n    n = n - 1\nprint("发射!")`,
    correctCode: `n = 5\nwhile n > 0:\n    print(n)\n    n = n - 1\nprint("发射!")`,
    hint: "追踪 n 的变化：5→4→3→2→1→0（停止）。",
    explanation: "输出：5 4 3 2 1 发射!。每次循环 n 减 1，当 n=0 时不满足 >0，退出循环。",
  },
];
