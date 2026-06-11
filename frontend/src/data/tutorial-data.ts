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
      { content: "🎉 恭喜你完成了 Python 新手教程的全部课程！\n\n你学到了：\n\n✅ Lesson 0A：认识编辑器\n✅ Lesson 0B：运行、输出和报错\n✅ Lesson 1：第一行代码\n✅ Lesson 2：print 输出\n✅ Lesson 3：变量\n✅ Lesson 4：if 条件判断\n✅ Lesson 5：for 循环\n\n现在你已经可以自己写简单的 Python 程序了！\n\n接下来可以在 **AI 对话** 中自由提问，在 **练习中心** 挑战题目，继续你的学习之旅！", action: "continue", actionHint: "🎉 完成教程，开始学习！" },
    ],
  },
];
