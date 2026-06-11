"""
误区专项练习种子 API
====================

POST /exercises/seed-mc-exercises — 将 M1-M8 靶向练习写入数据库（幂等）。

数据定义在 `backend/app/data/mc_exercises.py`，与 API 逻辑分离。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import select as sa_select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.mc_exercises import MC_EXERCISES
from app.database.session import get_db
from app.models.exercise import Exercise, TestCase

router = APIRouter()


@router.post("/seed-mc-exercises")
async def seed_mc_exercises(db: AsyncSession = Depends(get_db)):
    """将 M1-M8 误区专项练习写入数据库（幂等，重复调用不重复创建）。"""
    count = 0
    for ex in MC_EXERCISES:
        # 幂等检查：标题已存在则跳过
        existing = await db.execute(
            sa_select(func.count()).select_from(Exercise).where(Exercise.title == ex["title"])
        )
        if existing.scalar() > 0:
            continue

        exercise = Exercise(
            title=f'[{ex["code"]}] {ex["title"]}',
            description=ex["desc"],
            difficulty=1,
            concepts=ex["code"],
            example_input=ex.get("input", ""),
            example_output=ex.get("output", ""),
            reference_solution=ex.get("solution", ""),
            learning_objective=ex.get("hint", ""),
        )
        db.add(exercise)
        await db.flush()

        if ex.get("output"):
            tc = TestCase(
                exercise_id=exercise.id,
                description=f'{ex["code"]} 测试',
                input_data=ex.get("input", ""),
                expected_output=ex.get("output", ""),
                order_index=0,
                is_hidden=False,
            )
            db.add(tc)

        count += 1

    await db.commit()
    return {"seeded": count, "total": len(MC_EXERCISES)}
