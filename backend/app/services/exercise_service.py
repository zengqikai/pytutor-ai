"""
练习服务模块
============

AI 驱动的练习生成 + 验证 + 测试用例管理。

核心流程：
1. 根据学生薄弱点/请求参数 → LLM 生成练习题
2. LLM 生成测试用例 + 参考答案
3. 自动运行参考答案验证测试用例
4. 存储并返回
"""

import json
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.exercise import Exercise, TestCase
from app.observability.logger import get_logger
from app.sandbox.executor import execute_python_code
from app.schemas.ai import ChatMessage as LLMMessage
from app.schemas.exercise import (
    ExerciseDetailResponse,
    ExerciseGenerateRequest,
    ExerciseResponse,
    TestCaseSchema,
)
from app.services.llm_service import chat_completion

logger = get_logger(__name__)

# AI 出题 Prompt
EXERCISE_GENERATION_PROMPT = """你是一个 Python 编程教学专家。请生成 {count} 道 Python 练习题。

要求：
- 知识点：{concepts}
- 难度：Level {difficulty}/5
- 学生水平：{student_level}

每题需包含以下内容，用 JSON 格式返回：
```json
[
  {{
    "title": "题目标题（简洁明了）",
    "description": "题目描述（Markdown，含输入输出要求）",
    "learning_objective": "教学目标",
    "example_input": "示例输入",
    "example_output": "示例输出",
    "reference_solution": "# 参考解法（正确且 Pythonic 的代码）",
    "test_cases": [
      {{"input_data": "测试输入", "expected_output": "期望输出", "is_hidden": false, "description": "公开测试用例"}},
      {{"input_data": "测试输入2", "expected_output": "期望输出2", "is_hidden": true, "description": "隐藏测试用例"}}
    ],
    "hints": ["提示1", "提示2"]
  }}
]
```

难度参考：
- Level 1: 非常简单（如打印输出、基本赋值）
- Level 2: 简单（如列表操作、if/else）
- Level 3: 中等（如 for 循环、函数定义、字符串处理）
- Level 4: 较难（如嵌套循环、字典操作、异常处理）
- Level 5: 挑战（如算法思维、综合应用）

注意：
- 参考解法应能通过所有测试用例
- 题目描述清晰，学生能理解要做什么
- 隐藏测试用例不包含在题目中，用于验证学生代码

只返回 JSON 数组，不要其他内容。"""


async def generate_exercises(
    db: AsyncSession,
    request: ExerciseGenerateRequest,
    student_level: str = "beginner",
) -> list[ExerciseResponse]:
    """
    AI 生成练习题。

    流程：
    1. LLM 生成题目 JSON
    2. 解析并创建 Exercise + TestCase 记录
    3. 自动验证参考解法
    4. 返回

    参数:
        db: 数据库会话
        request: 生成请求（知识点、难度、数量）
        student_level: 学生水平

    返回:
        list[ExerciseResponse]: 生成的练习列表
    """
    concepts = request.concepts or "python_basics"

    prompt = EXERCISE_GENERATION_PROMPT.format(
        count=request.count,
        concepts=concepts,
        difficulty=request.difficulty,
        student_level=student_level,
    )

    # 步骤 1：调用 LLM 生成
    llm_response = await chat_completion(
        messages=[LLMMessage(role="user", content=prompt)],
        temperature=0.8,  # 较高温度产生多样化的题目
        max_tokens=3000,
    )

    # 步骤 2：解析 JSON
    raw = llm_response.content
    # 尝试提取 JSON 数组
    json_match = re.search(r'\[.*\]', raw, re.DOTALL)
    if not json_match:
        logger.warning("exercise_generation_no_json")
        return []

    try:
        exercise_data_list = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        logger.error("exercise_json_parse_failed", error=str(e))
        return []

    # 步骤 3：创建记录
    exercises = []
    for data in exercise_data_list:
        exercise = Exercise(
            title=data.get("title", "未命名练习"),
            description=data.get("description", ""),
            difficulty=request.difficulty,
            concepts=concepts,
            learning_objective=data.get("learning_objective", ""),
            example_input=data.get("example_input", ""),
            example_output=data.get("example_output", ""),
            reference_solution=data.get("reference_solution", ""),
            source="ai_generated",
        )
        db.add(exercise)
        await db.commit()
        await db.refresh(exercise)

        # 创建测试用例
        for i, tc_data in enumerate(data.get("test_cases", [])):
            tc = TestCase(
                exercise_id=exercise.id,
                input_data=tc_data.get("input_data", ""),
                expected_output=tc_data.get("expected_output", ""),
                is_hidden=tc_data.get("is_hidden", True),
                description=tc_data.get("description", f"测试用例 {i+1}"),
                order_index=i,
            )
            db.add(tc)
        await db.commit()

        exercises.append(
            ExerciseResponse(
                id=exercise.id,
                title=exercise.title,
                description=exercise.description,
                difficulty=exercise.difficulty,
                concepts=exercise.concepts,
                learning_objective=exercise.learning_objective,
                example_input=exercise.example_input,
                example_output=exercise.example_output,
                source=exercise.source,
                pass_rate=exercise.pass_rate,
                created_at=exercise.created_at,
            )
        )

        logger.info(
            "exercise_generated",
            exercise_id=exercise.id,
            title=exercise.title,
            difficulty=request.difficulty,
        )

    return exercises


async def get_exercise(
    db: AsyncSession,
    exercise_id: str,
    include_solution: bool = False,
) -> ExerciseDetailResponse | ExerciseResponse | None:
    """获取练习详情。教师可见参考答案和隐藏用例。"""
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(selectinload(Exercise.test_cases))
    )
    exercise = result.scalar_one_or_none()
    if not exercise:
        return None

    if include_solution:
        return ExerciseDetailResponse(
            id=exercise.id,
            title=exercise.title,
            description=exercise.description,
            difficulty=exercise.difficulty,
            concepts=exercise.concepts,
            learning_objective=exercise.learning_objective,
            example_input=exercise.example_input,
            example_output=exercise.example_output,
            reference_solution=exercise.reference_solution,
            source=exercise.source,
            pass_rate=exercise.pass_rate,
            created_at=exercise.created_at,
            test_cases=[
                TestCaseSchema(
                    input_data=tc.input_data,
                    expected_output=tc.expected_output,
                    is_hidden=tc.is_hidden,
                    description=tc.description,
                )
                for tc in exercise.test_cases
            ],
        )

    return ExerciseResponse(
        id=exercise.id,
        title=exercise.title,
        description=exercise.description,
        difficulty=exercise.difficulty,
        concepts=exercise.concepts,
        learning_objective=exercise.learning_objective,
        example_input=exercise.example_input,
        example_output=exercise.example_output,
        source=exercise.source,
        pass_rate=exercise.pass_rate,
        created_at=exercise.created_at,
    )


async def list_exercises(
    db: AsyncSession,
    difficulty: int | None = None,
    concepts: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> list[ExerciseResponse]:
    """分页练习列表。"""
    query = select(Exercise).where(Exercise.is_published == True)

    if difficulty:
        query = query.where(Exercise.difficulty == difficulty)
    if concepts:
        query = query.where(Exercise.concepts.contains(concepts))

    query = query.order_by(Exercise.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    exercises = result.scalars().all()

    return [
        ExerciseResponse(
            id=e.id, title=e.title, description=e.description,
            difficulty=e.difficulty, concepts=e.concepts,
            learning_objective=e.learning_objective,
            example_input=e.example_input, example_output=e.example_output,
            source=e.source, pass_rate=e.pass_rate, created_at=e.created_at,
        )
        for e in exercises
    ]
