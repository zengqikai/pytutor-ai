# PyTutor 2.0 PPT 指南

> 按 Introduction → Literature Review → Proposed Method → Conclusion → Demo 五段式结构
> 每页标注了具体内容和截图位置

---

## Section 1: Introduction（2-3 slides）

### Slide 1 — 封面

```
PyTutor 2.0
Misconception-Aware AI Tutoring System for Python Beginners
AI 引导式与误区感知型 Python 编程学习平台
```

---

### Slide 2 — 为什么初学者需要专用导师

**核心论点**：传统判题只告诉对错，ChatGPT 容易导致复制答案。初学者需要的是"诊断误区 + 分步引导"。

**三个痛点，各配一例**：

| 痛点 | 例子 |
|------|------|
| 传统判题只判对错 | 学生看到 "Wrong Answer 1/4 passed"，不知道怎么改 |
| ChatGPT 直接给完整代码 | 学生复制粘贴就过了，没学到东西 |
| 老师看不到全班数据 | 不知道哪个误区出现最频繁，无法针对性讲解 |

**一句话定位**：

> PyTutor 2.0 is not a Python Chatbot. It is a misconception-aware tutoring system that diagnoses why beginners make mistakes and guides them through progressive hints.

---

### Slide 3 — 项目当前状态

| 指标 | 数据 |
|------|------|
| 核心模块 | AI 对话 / 12 课教程 / 练习中心 / 学习画像 / 教师仪表盘 |
| 误区系统 | M1-M8 八类 Python 初学者误区，规则+LLM 双通道诊断 |
| 提示系统 | 5 级渐进式提示，禁止首次给答案 |
| 后端文件 | 50+ Python 文件 |
| 前端文件 | 15+ TypeScript/React 文件 |
| 数据库表 | 12 张，API 端点 25+ |
| 测试 | 28 个 pytest 用例，20 例基准评估 @ 92.3% |
| Bug 修复 | 38 个 |
| 部署 | Vercel + Render，公网可访问 |

---

## Section 2: Literature Review / Related Work（2-3 slides）

### Slide 4 — 相关研究方向

| 研究方向 | 代表工作 | 局限 | 我们的改进 |
|---------|---------|------|-----------|
| Automated Program Assessment | 传统 OJ/自动判题系统 | 只做 I/O 匹配，不解释为什么错 | PyTutor 增加语义层面的误区诊断 |
| LLM for Programming Education | ChatGPT, Copilot | 回复直接给完整代码，初学者容易复制 | 我们给 LLM 加教学约束（5 级提示策略） |
| Misconception Research | 文献分类了 Python 常见概念错误 | 研究很多但缺少可运行的系统实现 | 我们把 M1-M8 做成了可运行的双通道诊断引擎 |
| Intelligent Tutoring Systems | Cognitive Tutor 等 | 通常需要人工标注知识图谱 | PyTutor 用 LLM 辅助分类，减少人工标注成本 |
| Learner Modeling | 知识追踪模型 | 复杂模型难以部署 | 我们实现轻量画像追踪（weak_topics, recent_misconceptions, hint_dependency） |

**Research Gap**：缺少一个 **将 LLM 放进有教学约束的辅导流程，同时结合误区诊断和长期学习追踪** 的 Python 编程教学系统。

---

## Section 3: Proposed Method（5-6 slides）

### Slide 5 — 系统架构总览

**用 draw.io 画架构图，或直接用 PPT 文本框+箭头**：

```
浏览器 (Next.js 16 + React 19 + Tailwind CSS 4)
        ↓
   Vercel (前端) + Render (后端)
        ↓
FastAPI → SQLAlchemy (async) → SQLite
        ↓
┌─────────────────────────────────────────┐
│  LiteLLM → DeepSeek (AI 对话)            │
│  ChromaDB + DashScope API (RAG 检索)     │
│  Docker Sandbox (代码安全执行)            │
│  LangGraph (Agent 工作流编排)             │
└─────────────────────────────────────────┘
```

**核心流程**：

```
用户提交代码 → Docker 沙箱执行 → 误区诊断(规则+LLM)
→ 教学策略选择 → 5级提示生成 → AI 回复
→ 质量自检 → 学习画像更新 → 教师数据汇总
```

---

### Slide 6 — 创新点 1：M1-M8 误区诊断系统

**M1-M8 误区库**（已数据化实现，存在 `misconceptions.json` 中）：

| ID | 误区名称 | 典型错误模式 |
|----|---------|-------------|
| M1 | 赋值与比较混淆 | `if x = 3:` |
| M2 | 缩进理解错误 | if/for 后无缩进 |
| M3 | append 返回值误解 | `new = list.append(x)` |
| M4 | index/value 混淆 | `for i in list: print(list[i])` |
| M5 | range 右边界误解 | 以为 range(1,5) 含 5 |
| M6 | print/return 混淆 | 函数只 print 不 return |
| M7 | 类型转换错误 | `"score: " + 100` |
| M8 | while 循环条件错误 | 忘记更新循环变量 |

**双通道诊断流程**：

```
学生代码 + 错误信息
  → 通道 1：正则规则匹配（<1ms，识别已知模式，confidence 0.85）
  → 通道 2：LLM 辅助分类（规则不确定时调用 AI）
  → 输出：{misconception_id, confidence, evidence, related_concepts}
```

**核心贡献**：M1-M8 标签是连接代码错误和教学反馈的**中间表示层** — 同时驱动提示生成、学习画像更新和教师统计。

> 📸 截图：后端 API 返回 JSON（Postman/Swagger），展示 diagnosis 结构化输出

---

### Slide 7 — 创新点 2：渐进式提示系统

**设计原则**：禁止首次给完整答案。

| Level | 类型 | 示例（针对 M3 append 误区） |
|-------|------|---------------------------|
| 1 | 概念提示 | "请先观察 append() 之后，原来的 numbers 有没有变化" |
| 2 | 方向提示 | "append() 会直接修改原列表，不一定会返回新列表" |
| 3 | 位置提示 | "问题可能出现在 new_numbers = numbers.append(4) 这一行" |
| 4 | 部分代码 | "可以先写 numbers.append(4)，然后再 print(numbers)" |
| 5 | 完整答案 | 给出完整正确代码（仅多次失败后） |

**升级规则**：根据学生尝试次数自动调整 — 第 1 次错误给 Level 1-2，第 3 次以上给 Level 3-4。

**7 种教学策略选择器**：

```
首次误区 → progressive_hint
重复误区 ≥3 次 → concept_explanation
多次失败 → debugging_guidance
修正成功 → summary_reflection
```

> 📸 截图：练习中心 Hint 按钮 + 不同等级的提示卡片对比

---

### Slide 8 — 创新点 3：学习画像系统

**追踪维度**：

| 字段 | 说明 | 示例 |
|------|------|------|
| weak_topics | 薄弱知识点列表 | ["lists", "loops"] |
| recent_misconceptions | 最近出现的误区 ID | ["M3", "M5"] |
| hint_dependency | 提示依赖度 | low / medium / high |
| completed_lessons | 已完成课程 | ["lesson_0a", "lesson_1"] |
| total_exercises_passed | 通过题目数 | 12 |

**更新时机**：每次代码提交、误区诊断、使用提示、完成课程时自动更新。

**核心价值**：不仅响应当前代码提交，还追踪学生长期的学习困难模式。AI 回复会根据画像调整策略（高依赖度 → 降低提示等级，鼓励独立思考）。

> 📸 截图：Profile 页面完整截图（含误区卡片 + 提示依赖度条 + 推荐下一步）

---

### Slide 9 — 创新点 4：教师数据分析

**仪表盘内容**：

- 📊 全班误区频次柱状图（M1-M8 排行）
- ⚠️ 薄弱知识点 TOP 10
- 📖 提示依赖度分布（低/中/高）
- 👨‍🎓 学生列表（等级、通过数、最近误区）
- 📝 最近学习动态流

**核心价值**：把个体调试数据转化为班级教学决策 — 哪些误区最需要课堂讲解、谁需要额外辅导。

> 📸 截图：Teacher Dashboard 页面截图

---

## Section 4: Conclusion（1-2 slides）

### Slide 10 — 总结与贡献

**我们做了什么**：

1. 设计和实现了一个 **功能型原型**，不只是概念设计
2. 建立了 **M1-M8 八类 Python 初学者误区**的结构化库
3. 实现了 **规则 + LLM 双通道诊断引擎**（77.5% 准确率）
4. 设计了 **5 级渐进式提示系统**（100% 不早给答案）
5. 构建了 **学习画像追踪** 和 **教师数据分析** 模块
6. 通过 **20 例基准评估** 证明了系统的教学价值（综合 92.3%）

**一句话总结**：

> We built PyTutor 2.0 as a misconception-aware tutoring system that integrates code execution, structured diagnosis, progressive hinting, learner profiling, and teacher-facing analytics — going beyond correctness feedback to diagnose why beginners make mistakes.

---

### Slide 11 — 未来工作

| 方向 | 说明 |
|------|------|
| 诊断覆盖 | 扩展误区种类，增强 LLM 诊断精度 |
| 学习画像 | 完善画像更新闭环，增加 concept mastery 评分 |
| 评估 | 扩大测试集，完成 ChatGPT baseline 对比 |
| 部署 | 迁移到国内直连云平台（Zeabur/阿里云），去掉梯子依赖 |

---

## Section 5: Demo（1-2 slides）

### Slide 12 — Demo 演示流程

**现场演示路线（约 3 分钟）**：

```
1. 打开网站 → 登录学生账号
2. 进入练习中心 → 选一道题
3. 故意写错代码（new = numbers.append(4)）→ 提交
4. 展示 🧠 误区诊断卡片（M3: append 返回值误解）
5. 点击"提示" → 展示渐进式提示升级（Level 1 → 2 → 3）
6. 修改代码 → 再次提交 → ✅ Accepted
7. 打开学习画像 → 展示更新的误区记录
8. 登录教师账号 → 展示教师仪表盘
```

> 📸 截图：每个关键步骤各一张

---

## 补图清单（按优先级）

| 优先级 | 截图内容 | 放哪 |
|--------|---------|------|
| ⭐⭐⭐ | 练习中心错误代码 + 误区诊断卡片 | Slide 6 |
| ⭐⭐⭐ | 练习中心 Hint 卡片（不同级别对比） | Slide 7 |
| ⭐⭐⭐ | Profile 页面（误区 + 提示依赖） | Slide 8 |
| ⭐⭐ | Teacher Dashboard 页面 | Slide 9 |
| ⭐⭐ | 系统架构图（draw.io 画） | Slide 5 |
| ⭐ | 后端 API JSON 截图（Swagger/Postman） | Slide 6 |
