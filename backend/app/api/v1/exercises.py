"""
练习 API
========

接口：
    POST   /api/v1/exercises/generate - AI 生成练习
    GET    /api/v1/exercises          - 练习列表
    GET    /api/v1/exercises/{id}     - 练习详情
    POST   /api/v1/exercises/{id}/submit - 提交答案（执行测试用例）
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.models.exercise import Exercise
from app.models.user import User, UserRole
from app.sandbox.executor import execute_python_code
from app.schemas.exercise import ExerciseGenerateRequest, ExerciseResponse
from app.security.dependencies import get_current_user, require_role
from app.services.exercise_service import generate_exercises, get_exercise, list_exercises

router = APIRouter()


@router.get("", response_model=list[ExerciseResponse])
async def list_exercise_list(
    difficulty: int | None = Query(default=None, ge=1, le=5),
    concepts: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取练习题列表（可按难度和知识点筛选）。"""
    return await list_exercises(db, difficulty=difficulty, concepts=concepts, limit=limit, offset=offset)


@router.post("/generate")
async def generate_exercise_list(
    request: ExerciseGenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 生成个性化练习题。"""
    exercises = await generate_exercises(db, request)
    return {"exercises": exercises, "count": len(exercises)}


@router.get("/{exercise_id}")
async def get_exercise_detail(
    exercise_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取练习详情。教师可见参考答案。"""
    is_teacher = current_user.role in (UserRole.INSTRUCTOR, UserRole.ADMIN)
    exercise = await get_exercise(db, exercise_id, include_solution=is_teacher)
    if not exercise:
        return {"detail": "练习不存在"}
    return exercise


@router.post("/{exercise_id}/submit")
async def submit_exercise_answer(
    exercise_id: str,
    code: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    提交练习答案，自动运行测试用例。

    请求体：{"code": "学生的 Python 代码"}
    返回：测试用例通过情况 + 执行结果
    """
    from sqlalchemy.orm import selectinload
    from sqlalchemy import select

    # 获取练习和测试用例
    result = await db.execute(
        select(Exercise)
        .where(Exercise.id == exercise_id)
        .options(selectinload(Exercise.test_cases))
    )
    exercise = result.scalar_one_or_none()
    if not exercise:
        return {"detail": "练习不存在"}

    user_code = code.get("code", "")

    # 执行用户代码
    exec_result = await execute_python_code(user_code)

    # 运行测试用例（简单比对 stdout）
    test_results = []
    passed = 0
    total = 0

    for tc in exercise.test_cases:
        total += 1
        # 简单比较：运行代码的输出是否等于期望输出
        if exec_result["stdout"].strip() == tc.expected_output.strip():
            passed += 1
            test_results.append({
                "description": tc.description,
                "passed": True,
                "is_hidden": tc.is_hidden,
            })
        else:
            test_results.append({
                "description": tc.description,
                "passed": False,
                "is_hidden": tc.is_hidden,
                "expected": tc.expected_output if not tc.is_hidden else "(隐藏)",
                "got": exec_result["stdout"][:100] if not tc.is_hidden else "(隐藏)",
            })

    # 更新使用统计
    exercise.use_count = (exercise.use_count or 0) + 1
    await db.commit()

    return {
        "exercise_id": exercise_id,
        "execution": {
            "stdout": exec_result["stdout"][:500],
            "stderr": exec_result["stderr"][:500],
            "status": exec_result["status"],
            "runtime_ms": exec_result["runtime_ms"],
        },
        "test_results": {
            "passed": passed,
            "total": total,
            "details": test_results,
        },
    }
