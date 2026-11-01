"""
误区专项练习种子 API
====================

POST /exercises/seed-mc-exercises — 将 M1-M8 靶向练习写入数据库（幂等，管理员）。

数据定义在 `backend/app/data/mc_exercises.py`，与 API 逻辑分离。

幂等键是**入库后的标题** `[{code}] {title}`。旧实现拿 `ex["title"]`（没有前缀）
去比对带前缀的 title，永远匹配不上，于是每调用一次就多插一遍——库里曾经
每道题躺两份。这里顺带把历史重复行清掉。
"""

from fastapi import APIRouter, Depends
from sqlalchemy import delete as sa_delete
from sqlalchemy import select as sa_select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.mc_exercises import MC_EXERCISES
from app.database.session import get_db
from app.models.exercise import Exercise, TestCase
from app.models.user import User, UserRole
from app.security.dependencies import require_role

router = APIRouter()


def _seeded_title(ex: dict) -> str:
    return f'[{ex["code"]}] {ex["title"]}'


@router.post("/seed-mc-exercises")
async def seed_mc_exercises(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.ADMIN)),
):
    """将 M1-M8 误区专项练习写入数据库（幂等，重复调用不重复创建）。

    只有管理员能调用：这会改练习库，学生不该能触发。
    """
    expected_titles = [_seeded_title(ex) for ex in MC_EXERCISES]

    # 先按标题回收历史重复行（保留 id 最小的一条，删掉后来重复插入的）
    existing_rows = (await db.execute(
        sa_select(Exercise.id, Exercise.title)
        .where(Exercise.title.in_(expected_titles))
        .order_by(Exercise.id)
    )).all()

    seen: set[str] = set()
    duplicate_ids: list[str] = []
    for exercise_id, title in existing_rows:
        if title in seen:
            duplicate_ids.append(exercise_id)
        else:
            seen.add(title)

    if duplicate_ids:
        await db.execute(sa_delete(TestCase).where(TestCase.exercise_id.in_(duplicate_ids)))
        await db.execute(sa_delete(Exercise).where(Exercise.id.in_(duplicate_ids)))

    count = 0
    for ex in MC_EXERCISES:
        title = _seeded_title(ex)
        if title in seen:
            continue

        exercise = Exercise(
            title=title,
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

        seen.add(title)
        count += 1

    await db.commit()
    return {
        "seeded": count,
        "total": len(MC_EXERCISES),
        "removed_duplicates": len(duplicate_ids),
    }
