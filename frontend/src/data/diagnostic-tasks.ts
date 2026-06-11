export interface DiagnosticTask {
  id: number;
  topic: string;
  code: string;
  question: string;
  options: { key: string; text: string; isCorrect: boolean }[];
  explanation: string;
  misconception?: string;
  relatedConcepts: string[];
}

export const DIAGNOSTIC_TASKS: DiagnosticTask[] = [
  {
    id: 1,
    topic: "print 输出",
    code: `print("Hello, Python")`,
    question: "这段代码运行后会显示什么？",
    options: [
      { key: "A", text: "Hello, Python", isCorrect: true },
      { key: "B", text: "\"Hello, Python\"（带引号）", isCorrect: false },
      { key: "C", text: "什么都不显示", isCorrect: false },
      { key: "D", text: "报错", isCorrect: false },
    ],
    explanation: "print() 会把引号里的内容显示出来，但引号本身不会显示。",
    relatedConcepts: ["print", "string"],
  },
  {
    id: 2,
    topic: "变量",
    code: `name = "Tom"\nprint(name)`,
    question: "程序会输出什么？",
    options: [
      { key: "A", text: "Tom", isCorrect: true },
      { key: "B", text: "name", isCorrect: false },
      { key: "C", text: "\"Tom\"", isCorrect: false },
      { key: "D", text: "报错", isCorrect: false },
    ],
    explanation: "name 是一个变量，保存了 \"Tom\"。print(name) 输出的是变量的值（Tom），而不是变量名。",
    relatedConcepts: ["variables", "print"],
  },
  {
    id: 3,
    topic: "赋值与比较",
    code: `x = 3\n\nif x == 3:\n    print(\"yes\")`,
    question: "这段代码中，= 和 == 分别是什么意思？",
    options: [
      { key: "A", text: "= 是赋值，== 是比较", isCorrect: true },
      { key: "B", text: "两个都是比较", isCorrect: false },
      { key: "C", text: "两个都是赋值", isCorrect: false },
      { key: "D", text: "= 是比较，== 是赋值", isCorrect: false },
    ],
    explanation: "在 Python 中，单个 = 是把值放进变量（赋值），双 == 是判断两个值是否相等（比较）。",
    misconception: "M1",
    relatedConcepts: ["variables", "if_statement", "comparison"],
  },
  {
    id: 4,
    topic: "for 循环与 range",
    code: `for i in range(1, 4):\n    print(i)`,
    question: "这段代码会输出哪些数字？",
    options: [
      { key: "A", text: "1, 2, 3", isCorrect: true },
      { key: "B", text: "1, 2, 3, 4", isCorrect: false },
      { key: "C", text: "0, 1, 2, 3", isCorrect: false },
      { key: "D", text: "1, 2", isCorrect: false },
    ],
    explanation: "range(1, 4) 从 1 开始，到 4 之前停止，所以生成 1、2、3。注意不包含 4！",
    misconception: "M5",
    relatedConcepts: ["for_loop", "range"],
  },
  {
    id: 5,
    topic: "list 列表索引",
    code: `fruits = ["apple", "banana", "orange"]\nprint(fruits[0])`,
    question: "程序会输出什么？",
    options: [
      { key: "A", text: "apple", isCorrect: true },
      { key: "B", text: "banana", isCorrect: false },
      { key: "C", text: "orange", isCorrect: false },
      { key: "D", text: "报错", isCorrect: false },
    ],
    explanation: "列表的下标从 0 开始，所以 fruits[0] 取的是第一个元素 \"apple\"。",
    relatedConcepts: ["list", "index"],
  },
  {
    id: 6,
    topic: "append 行为",
    code: `numbers = [1, 2, 3]\nnumbers.append(4)\nprint(numbers)`,
    question: "程序会输出什么？",
    options: [
      { key: "A", text: "[1, 2, 3, 4]", isCorrect: true },
      { key: "B", text: "[1, 2, 3]", isCorrect: false },
      { key: "C", text: "None", isCorrect: false },
      { key: "D", text: "4", isCorrect: false },
    ],
    explanation: "append() 会直接修改原列表，在末尾添加新元素。所以 numbers 变成了 [1, 2, 3, 4]。",
    misconception: "M3",
    relatedConcepts: ["list", "append"],
  },
];
