export interface LessonStep {
  content: string;
  code?: string;
  action?: "run" | "edit" | "observe" | "predict" | "continue";
  actionHint?: string;
  highlight?: "editor" | "runBtn" | "output" | "error";
}

export interface Lesson {
  id: string;
  title: string;
  desc: string;
  initialCode: string;
  steps: LessonStep[];
  relatedConcepts: string[];
}

export const TUTORIAL_LESSONS: Lesson[] = [
  // ============================================================
  // Lesson 0A：认识 Code Lab 编辑器
  // ============================================================
  {
    id: "lesson_0a",
    title: "认识 Code Lab 编辑器",
    desc: "了解代码编辑器、运行按钮、输出和错误区域",
    initialCode: `print("Hello, Python!")`,
    relatedConcepts: ["editor", "run_code", "output"],
    steps: [
      { content: "欢迎来到 PyTutor 的 **Code Lab**（代码实验室）！\n\n这里是你学习 Python 的主要区域。在我继续之前，先让我们认识一下这个界面。", highlight: "editor" },
      { content: "👈 **左边是代码编辑器**\n\n你可以在这里输入和修改 Python 代码。\n\n现在编辑器里已经有一行代码了：", code: `print("Hello, Python!")` },
      { content: "👉 **右上角是运行按钮**\n\n点击它，系统就会执行你写的代码。\n\n现在试试点击右边的 **▶ 运行** 按钮！", action: "run", actionHint: "▶ 我运行了", highlight: "runBtn" },
      { content: "👀 **输出区域**\n\n运行后，代码的结果会显示在下方的输出区。\n\n你应该看到了 `Hello, Python!` ——这就是程序运行的结果。", highlight: "output" },
      { content: "⚠️ **错误信息**\n\n当代码有问题时，错误信息会显示在输出区。\n\n不用害怕报错！它只是告诉你代码哪里需要调整，是学习的好线索。", highlight: "error" },
      { content: "🤖 **AI Tutor**\n\n当你遇到问题时，我会在这里帮助你理解代码、解释错误、给出提示。\n\n我不是来直接给你答案的，而是来帮你**学会自己解决问题**。" },
      { content: "很好！现在你已经认识了 Code Lab。\n\n✅ 代码编辑器：写代码的地方\n✅ 运行按钮：执行代码\n✅ 输出区域：查看结果\n✅ 错误信息：学习线索\n✅ AI Tutor：你的学习伙伴\n\n准备好进入下一课了吗？", action: "continue", actionHint: "进入下一课 →" },
    ],
  },

  // ============================================================
  // Lesson 0B：认识运行、输出和报错
  // ============================================================
  {
    id: "lesson_0b",
    title: "认识运行、输出和报错",
    desc: "理解代码如何运行，输出来自哪里，报错是什么意思",
    initialCode: `print("Hello, Python!")`,
    relatedConcepts: ["run_code", "output", "error"],
    steps: [
      { content: "在上一课我们认识了 Code Lab 的界面。\n\n这一课我们来真正理解：**代码是怎么运行的**。\n\n代码就像一份说明书——你写下指令，电脑按指令一步步执行。" },
      { content: "让我们先运行一次正确的代码。\n\n点击右边的 **▶ 运行**，看看会发生什么。", action: "run", actionHint: "▶ 我运行了" },
      { content: "你看到了 `Hello, Python!` 对吗？\n\n这就是**输出（Output）**——程序执行后产生的结果。\n\n`print()` 的作用就是把你写的内容显示到屏幕上。" },
      { content: "现在让我们故意制造一个错误——这是学习的好方法！\n\n把代码改成：\n\n`print(Hello)`\n\n（注意：去掉了引号）\n\n然后再次运行。", code: `print(Hello)`, action: "edit", actionHint: "我改好并运行了" },
      { content: "你看到红色的错误信息了吗？\n\n这个错误叫 `NameError`，意思是 Python 不认识 `Hello` 这个单词。\n\n为什么呢？因为 Python 把没有引号的 `Hello` 当成了一个**变量名**，但你并没有定义过它。" },
      { content: "这就是报错的意义：\n\n❌ 不是\"你失败了\"\n✅ 而是\"代码这里需要调整\"\n\n每一个报错都是一条**线索**，帮我们找到问题所在。\n\n把代码改回 `print(\"Hello, Python!\")` 吧。", action: "edit", actionHint: "我改好了" },
      { content: "总结一下你学到的：\n\n✅ 代码 = 给电脑的指令\n✅ 运行 = 让电脑执行指令\n✅ 输出 = 程序执行后的结果\n✅ 报错 = 帮助我们定位问题的线索\n\n记住：**报错不是失败，是学习！**", action: "continue", actionHint: "进入下一课 →" },
    ],
  },

  // ============================================================
  // Lesson 1：运行第一行 Python 代码
  // ============================================================
  {
    id: "lesson_1",
    title: "运行第一行 Python 代码",
    desc: "完成第一次代码运行，理解 print() 的作用",
    initialCode: `print("Hello, Python!")`,
    relatedConcepts: ["print", "string"],
    steps: [
      { content: "现在让我们正式运行你的**第一行 Python 代码**！\n\n代码已经在编辑器里了：", code: `print("Hello, Python!")` },
      { content: "这行代码的意思是：\n\n📢 **print** = 显示\n📝 **\"Hello, Python!\"** = 要显示的文字\n\n点击 ▶ 运行 试试！", action: "run", actionHint: "▶ 我运行了" },
      { content: "🎉 恭喜！你刚刚运行了人生中第一行 Python 代码！\n\n你写的是：`print(\"Hello, Python!\")`\n电脑执行了这条指令，在输出区显示了 `Hello, Python!`。\n\n**这就是编程的基本流程：写指令 → 执行 → 看到结果。**" },
      { content: "现在试试动手修改！\n\n把双引号里的文字改成你自己的话，比如：\n\n`print(\"你好，世界！\")`\n\n然后再次运行。", action: "edit", actionHint: "我改好并运行了" },
      { content: "输出结果变了对吗？\n\n这说明：**修改代码会改变程序的行为**。\n\n你可以通过改变引号里的内容，让程序显示任何你想说的话。\n\n这就是编程的乐趣——你控制电脑做什么！" },
      { content: "✅ 你完成了：\n\n1. 运行了第一行 Python 代码\n2. 理解了 print() 的作用\n3. 修改了代码并看到输出变化\n4. 理解了\"写代码 → 运行 → 看结果\"的流程\n\n准备好学习更多了吗？", action: "continue", actionHint: "进入下一课 →" },
    ],
  },

  // ============================================================
  // Lesson 2：print 输出
  // ============================================================
  {
    id: "lesson_2",
    title: "print 输出",
    desc: "深入学习 print()，打印多条内容",
    initialCode: `print("My name is Alice")\nprint("I am learning Python")`,
    relatedConcepts: ["print", "string", "multi_line"],
    steps: [
      { content: "你已经用过 `print()` 了。\n\n这一课来深入了解它。\n\n`print()` 可以显示**任何内容**——文字、数字、甚至多行内容。", code: `print("My name is Alice")\nprint("I am learning Python")` },
      { content: "代码中有两行 `print()`。\n\n每行 `print()` 会在输出中**独立一行**。\n\n点击运行看看效果。", action: "run", actionHint: "▶ 我运行了" },
      { content: "你看到了两行输出对吗？\n\n每一行 `print()` 产生一行输出。\n\n这就是 Python 的执行方式：**从上到下，一行一行执行**。" },
      { content: "现在把内容改成你自己的信息：\n\n```\nprint(\"My name is Tom\")\nprint(\"I like Python\")\n```\n\n改完运行。", action: "edit", actionHint: "我改好并运行了" },
      { content: "很好！\n\n⚠️ 注意一个小陷阱：\n\n文字必须放在**英文双引号** `\" \"` 里面。\n\n如果用中文引号 `\" \"` 或者忘记引号，就会报错。\n\n试试故意写 `print(hello)` （不加引号）看看会发生什么？", action: "edit", actionHint: "我试过了" },
      { content: "总结：\n\n✅ `print()` 用来显示内容\n✅ 文字要放在引号里\n✅ 多行 print = 多行输出\n✅ 代码从上到下执行\n\n下一课我们学习**变量**——编程中最基础的概念！", action: "continue", actionHint: "进入下一课 →" },
    ],
  },

  // ============================================================
  // Lesson 3：变量
  // ============================================================
  {
    id: "lesson_3",
    title: "变量",
    desc: "理解变量是用来保存数据的名字",
    initialCode: `name = "Alice"\nage = 18\n\nprint(name)\nprint(age)`,
    relatedConcepts: ["variables", "assignment", "print"],
    steps: [
      { content: "现在学习一个非常重要的概念：**变量（Variable）**。\n\n变量就像一个**带标签的盒子**——你可以把数据放进去，贴上标签，以后通过标签来找到它。", code: `name = \"Alice\"\nage = 18\n\nprint(name)\nprint(age)` },
      { content: "`name = \"Alice\"` 的意思是：\n\n📦 创建一个叫 `name` 的变量\n📝 把 `\"Alice\"` 存进去\n\n**注意**：这里的 `=` 不是数学里的\"等于\"，而是**赋值**——\"把右边的值放进左边的变量\"。\n\n点击运行！", action: "run", actionHint: "▶ 我运行了" },
      { content: "输出显示了 `Alice` 和 `18`。\n\n`print(name)` 输出的是变量 `name` 里面存的值，而不是 `name` 这个单词。\n\n**变量存的是值，使用时拿出来的也是值。**" },
      { content: "现在修改一下：把 `name` 改成你自己的名字，`age` 改成你的年龄。\n\n```\nname = \"Tom\"\nage = 20\n```\n\n改完运行。", action: "edit", actionHint: "我改好并运行了" },
      { content: "⚠️ 常见错误：\n\n有些同学会这样写：\n```\nname = Alice    ← 少了引号！\n```\n\nPython 会把 `Alice` 当成变量名（而不是文字），但你没有定义过 `Alice` 这个变量，所以会报错。\n\n**文字需要引号，变量名不需要引号。**" },
      { content: "总结：\n\n✅ 变量 = 有名字的存储空间\n✅ `=` = 把右边的值**赋值**给左边的变量\n✅ `print(变量名)` = 输出变量的值\n✅ 文字要引号，变量名不要引号\n\n下一课：**if 条件判断**——让程序做出选择！", action: "continue", actionHint: "进入下一课 →" },
    ],
  },

  // ============================================================
  // Lesson 4：if 条件判断
  // ============================================================
  {
    id: "lesson_4",
    title: "if 条件判断",
    desc: "让程序根据不同条件做出不同选择",
    initialCode: `age = 18\n\nif age >= 18:\n    print("You are an adult")\nelse:\n    print("You are a minor")`,
    relatedConcepts: ["if_statement", "comparison", "indentation", "booleans"],
    steps: [
      { content: "现在让程序变聪明——它能根据条件做出不同选择！\n\n这就要用到 **if 条件判断**。\n\n`if` = \"如果\"，`else` = \"否则\"。", code: `age = 18\n\nif age >= 18:\n    print(\"You are an adult\")\nelse:\n    print(\"You are a minor\")` },
      { content: "这段代码的意思是：\n\n🔍 如果 `age >= 18`（age 大于等于 18）\n&emsp;&emsp;→ 显示 \"You are an adult\"\n🔍 否则\n&emsp;&emsp;→ 显示 \"You are a minor\"\n\n点击运行！", action: "run", actionHint: "▶ 我运行了" },
      { content: "因为 `age = 18`，满足 `age >= 18` 的条件，所以输出了 \"You are an adult\"。\n\n现在把 `age` 改成 `16`：\n\n```\nage = 16\n```\n\n猜猜会输出什么？然后再运行。", action: "edit", actionHint: "我改好并运行了" },
      { content: "这次输出了 \"You are a minor\"！\n\n因为 16 不满足 `>= 18` 的条件，所以走了 `else` 分支。\n\n**程序根据 age 的值选择了不同的执行路径。**" },
      { content: "⚠️ 两个最常见的错误：\n\n1️⃣ **用 `=` 代替 `==`**\n```\nif age = 18:    ← 错误！= 是赋值\nif age == 18:   ← 正确！== 是比较\n```\n\n2️⃣ **忘记缩进**\n```\nif age > 18:\nprint(\"adult\")  ← 错误！缺少缩进\n```\n\nPython 用缩进（空格）来表示代码属于 if 的一部分。" },
      { content: "总结：\n\n✅ `if` = 如果条件成立就执行\n✅ `else` = 否则执行另一段\n✅ `==` 是比较，`=` 是赋值\n✅ if 下面的代码要**缩进**（前面加空格）\n\n下一课：**for 循环**——让程序自动重复执行！", action: "continue", actionHint: "进入下一课 →" },
    ],
  },

  // ============================================================
  // Lesson 5：for 循环
  // ============================================================
  {
    id: "lesson_5",
    title: "for 循环",
    desc: "让程序重复执行，遍历一组数据",
    initialCode: `for i in range(1, 5):\n    print(i)`,
    relatedConcepts: ["for_loop", "range", "iteration", "indentation"],
    steps: [
      { content: "最后一课学习 **for 循环**——让程序自动重复执行。\n\n当你需要做重复的事情时（比如打印数字 1 到 100），不需要写 100 行代码，用循环几行就够了。", code: `for i in range(1, 5):\n    print(i)` },
      { content: "这段代码的意思是：\n\n🔁 `for` = 循环\n🔢 `range(1, 5)` = 生成 1, 2, 3, 4（不包含 5！）\n📝 `print(i)` = 每次打印当前的数字\n\n**在运行之前，先猜一猜**：输出会是 1 到 4 还是 1 到 5？", action: "predict", actionHint: "我猜 1 到 4" },
      { content: "答案揭晓：输出是 `1 2 3 4`，**不包含 5**！\n\n`range(1, 5)` 从 1 开始，到 5 **之前**停止。\n\n这是 Python 的设计：左闭右开区间。\n\n点击运行验证一下。", action: "run", actionHint: "▶ 我运行了" },
      { content: "现在修改代码：把 `range(1, 5)` 改成 `range(1, 10)`。\n\n你猜会输出什么？运行看看！", action: "edit", actionHint: "我改好并运行了" },
      { content: "你学会了 for 循环！\n\n```\nfor 变量 in range(开始, 结束):\n    重复执行的代码\n```\n\n✅ `for` = 循环\n✅ `range(开始, 结束)` = 生成数字序列（不包含结束值）\n✅ 循环里的代码要**缩进**\n✅ 每次循环，变量的值都会变化" },
      { content: "你学会了 for 循环！\n\n```\nfor 变量 in range(开始, 结束):\n    重复执行的代码\n```\n\n✅ `for` = 循环\n✅ `range(开始, 结束)` = 生成数字序列（不包含结束值）\n✅ 循环里的代码要**缩进**\n✅ 每次循环，变量的值都会变化\n\n下一课：让程序接收你的输入！", action: "continue", actionHint: "进入下一课 →" },
    ],
  },

  // Lesson 6：input 输入
  {
    id: "lesson_6",
    title: "input 输入",
    desc: "让程序接收用户输入，实现交互",
    initialCode: `name = input("What is your name? ")\nprint("Hello, " + name)`,
    relatedConcepts: ["input", "string", "variables"],
    steps: [
      { content: "之前我们的程序只能输出固定的内容。\n\n现在学习 **input()**——让程序接收你的输入！\n\n`input()` 会暂停程序，等待你输入内容，然后把你输入的内容作为**字符串**返回。", code: `name = input("What is your name? ")\nprint("Hello, " + name)` },
      { content: "这段代码会：\n\n1️⃣ 显示提示语 \"What is your name? \"\n2️⃣ 等待你输入\n3️⃣ 把你输入的内容存到 `name` 变量\n4️⃣ 打印 \"Hello, \" + 你的名字\n\n在下方「输入(stdin)」框里填你的名字，然后点击运行！", action: "run", actionHint: "▶ 我运行了" },
      { content: "你看到 \"Hello, xxx\" 了对吗？\n\n这就是交互式程序——程序根据你的输入生成了不同的输出。\n\n⚠️ 注意：`input()` 返回的**永远是字符串**。即使你输入数字 18，它也是字符串 \"18\"。", code: `age = input("How old are you? ")\nprint("You are " + age)` },
      { content: "现在把提示语改成中文：\n\n```\nname = input(\"你叫什么名字？ \")\nprint(\"你好, \" + name)\n```\n\n改完运行，输入你自己的名字！", action: "edit", actionHint: "我改好并运行了" },
      { content: "✅ 你学会了：\n\n✅ `input()` = 接收用户输入\n✅ `input(\"提示\")` = 显示提示+等待输入\n✅ input 返回的是字符串\n✅ 程序可以和人交互了！\n\n下一课：字符串和数字的类型转换。", action: "continue", actionHint: "进入下一课 →" },
    ],
  },

  // Lesson 7：字符串和数字
  {
    id: "lesson_7",
    title: "字符串和数字",
    desc: "理解字符串和数字的区别，学会类型转换",
    initialCode: `age = input("请输入年龄: ")\n# age 是字符串，不能直接计算\nreal_age = int(age)\nprint("明年你将是", real_age + 1, "岁")`,
    relatedConcepts: ["string", "int", "float", "type_conversion"],
    steps: [
      { content: "`input()` 返回的是**字符串**。但如果你要计算，就需要**数字**。\n\n这就是**类型转换**——在字符串和数字之间切换。", code: `age = input(\"请输入年龄: \")\nreal_age = int(age)\nprint(\"明年你将是\", real_age + 1, \"岁\")` },
      { content: "`int(age)` 把字符串 `\"18\"` 转换成数字 `18`。\n\n常用转换：\n- `int(x)` → 转整数\n- `float(x)` → 转小数\n- `str(x)` → 转字符串\n\n输入一个年龄试试！", action: "run", actionHint: "▶ 我运行了" },
      { content: "⚠️ 看看这个错误代码会怎样：\n\n把代码改成：\n```\nage = input(\"年龄: \")\nprint(age + 1)\n```\n运行看看会报什么错？", code: `age = input(\"年龄: \")\nprint(age + 1)`, action: "edit", actionHint: "我运行了，看到了报错" },
      { content: "你看到了 TypeError 对吗？\n\n错误说：不能把字符串和数字相加。\n\n**\"18\" 是文字，18 是数字，它们不是一回事。**\n\n把代码改回来：`print(int(age) + 1)`，再运行一次。", action: "edit", actionHint: "我修复好了" },
      { content: "✅ 你学会了：\n\n✅ 字符串 = 文字，数字 = 可计算\n✅ `int()` → 字符串转整数\n✅ `str()` → 数字转字符串\n✅ 类型不匹配会报 TypeError\n\n下一课：list 列表！", action: "continue", actionHint: "进入下一课 →" },
    ],
  },

  // Lesson 8：list 列表
  {
    id: "lesson_8",
    title: "list 列表",
    desc: "用列表保存多个数据，学习遍历和增删",
    initialCode: `fruits = ["apple", "banana", "orange"]\nprint("第一个水果:", fruits[0])\nprint("全部水果:")\nfor fruit in fruits:\n    print(fruit)`,
    relatedConcepts: ["list", "index", "append", "for_loop"],
    steps: [
      { content: "变量只能存一个值。如果需要存多个值（比如全班同学的名字），就需要**列表（list）**。\n\n列表用方括号 `[]`，元素用逗号分隔。", code: `fruits = [\"apple\", \"banana\", \"orange\"]\nprint(\"第一个水果:\", fruits[0])\nprint(\"全部水果:\")\nfor fruit in fruits:\n    print(fruit)` },
      { content: "列表的**下标（索引）从 0 开始**：\n- `fruits[0]` = 第一个元素 \"apple\"\n- `fruits[1]` = 第二个 \"banana\"\n- `fruits[2]` = 第三个 \"orange\"\n\n点击运行！", action: "run", actionHint: "▶ 我运行了" },
      { content: "你看到了用 for 循环遍历列表的效果！\n\n现在试试添加新元素：\n\n把代码改成：\n```python\nfruits = [\"apple\", \"banana\"]\nfruits.append(\"orange\")\nprint(fruits)\n```", action: "edit", actionHint: "我改好并运行了" },
      { content: "`append()` 添加了一个新元素到列表末尾。\n\n⚠️ 重要误区：\n```python\n# 错误写法！\nnew_fruits = fruits.append(\"orange\")  # new_fruits 是 None！\n\n# 正确写法\nfruits.append(\"orange\")  # 直接修改原列表\n```\n\n`append()` 直接修改原列表，不返回新列表。", code: `# 正确：直接 append，然后打印原列表\nfruits = [\"apple\", \"banana\"]\nfruits.append(\"orange\")\nprint(fruits)  # [\"apple\", \"banana\", \"orange\"]` },
      { content: "✅ 你学会了：\n\n✅ 列表 = 用 `[]` 存多个值\n✅ 下标从 0 开始\n✅ `append()` 添加元素\n✅ `append()` 修改原列表，不返回新列表\n\n下一课：函数入门！", action: "continue", actionHint: "进入下一课 →" },
    ],
  },

  // Lesson 9：函数入门
  {
    id: "lesson_9",
    title: "函数入门",
    desc: "学会定义和调用函数，理解 return",
    initialCode: `def greet(name):\n    return "Hello, " + name\n\nmessage = greet("Alice")\nprint(message)`,
    relatedConcepts: ["function", "def", "return", "parameters"],
    steps: [
      { content: "**函数**是一段可以重复使用的代码。\n\n就像遥控器的按钮——按一下执行一个功能。\n\n`def` = 定义函数，`return` = 返回结果。", code: `def greet(name):\n    return \"Hello, \" + name\n\nmessage = greet(\"Alice\")\nprint(message)` },
      { content: "代码解释：\n\n1️⃣ `def greet(name):` → 定义一个叫 greet 的函数，接收一个参数 name\n2️⃣ `return \"Hello, \" + name` → 返回拼接后的字符串\n3️⃣ `greet(\"Alice\")` → 调用函数，返回 \"Hello, Alice\"\n4️⃣ `print(message)` → 输出结果\n\n点击运行！", action: "run", actionHint: "▶ 我运行了" },
      { content: "现在自己写一个加法函数：\n\n```python\ndef add(a, b):\n    return a + b\n\nresult = add(3, 5)\nprint(result)\n```\n\n运行看看结果！", action: "edit", actionHint: "我改好并运行了" },
      { content: "⚠️ 重要：`print` 和 `return` 的区别！\n\n```python\n# 错误理解\ndef add(a, b):\n    print(a + b)  # 只是显示，没有返回值\n\nresult = add(3, 5)  # result 是 None！\n```\n\n`print()` 只是显示在屏幕上。\n`return` 才是把结果交回给调用者。\n\n把 print 改成 return 试试。", action: "edit", actionHint: "我理解了并改好了" },
      { content: "✅ 你学会了：\n\n✅ `def` 定义函数\n✅ 函数可以接收参数\n✅ `return` 返回结果（不是 print）\n✅ 函数 = 可重复使用的代码块\n\n最后一课：综合复习！", action: "continue", actionHint: "进入最后一课 →" },
    ],
  },

  // Lesson 10：综合复习
  {
    id: "lesson_10",
    title: "综合复习",
    desc: "综合运用所学知识，完成一个小项目",
    initialCode: `# 一个小项目：名字收集器\nnames = []\n\nwhile True:\n    name = input(\"输入名字（输入q退出）: \")\n    if name == \"q\":\n        break\n    names.append(name)\n\nprint(\"你输入的名字有:\")\nfor n in names:\n    print(\"-\", n)\nprint(\"共\", len(names), \"个名字\")`,
    relatedConcepts: ["list", "input", "if_statement", "for_loop", "while_loop", "function"],
    steps: [
      { content: "最后一课，我们来综合运用学到的所有知识！\n\n这是一个「名字收集器」程序——让你输入名字，最后列出所有名字。\n\n它用到了：input、if、while、list、append、for 循环。", code: `names = []\nwhile True:\n    name = input(\"输入名字（输入q退出）: \")\n    if name == \"q\":\n        break\n    names.append(name)\nprint(\"你输入的名字有:\")\nfor n in names:\n    print(\"-\", n)` },
      { content: "逐行解释：\n\n1. `names = []` — 创建空列表\n2. `while True:` — 无限循环（直到 break）\n3. `name = input(...)` — 接收输入\n4. `if name == \"q\": break` — 输入 q 就退出\n5. `names.append(name)` — 把名字加入列表\n6. 最后用 for 循环打印所有名字\n\n运行试试！输入几个名字，然后输入 q 退出。", action: "run", actionHint: "▶ 我运行了" },
      { content: "你完成了一个完整的交互式程序！\n\n现在试试修改：\n- 把退出字符改成 \"exit\"\n- 让程序统计输入了多少个名字（用 `len(names)`）\n- 加一个函数来打印欢迎语", action: "edit", actionHint: "我改好了" },
      { content: "🎉 恭喜你完成了 PyTutor 新手教程的全部 12 课！\n\n你学到了：\n\n✅ Lesson 0A-0B：编辑器 + 运行/输出/报错\n✅ Lesson 1-3：print + 变量\n✅ Lesson 4-5：if 条件 + for 循环\n✅ Lesson 6-7：input + 类型转换\n✅ Lesson 8-9：list + 函数\n✅ Lesson 10：综合项目\n\n现在你可以：\n- 在 **AI 对话** 中自由提问\n- 去 **练习中心** 挑战 ACM 题目\n- 用 Code Lab 编写自己的程序\n\n**你已经是一个真正的 Python 初学者了！** 🐍", action: "continue", actionHint: "🎉 完成全部教程！" },
    ],
  },
];
