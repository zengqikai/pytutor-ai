"""
判题与统计的口径测试
====================

固定三条规则，防止回退：

1. 看答案做出的全对记 0 分，且**不写** `exercise_passed`；
2. 之后再独立做对，仍然能拿到首次通过奖励（不会被一次看答案永久锁死）；
3. 后台统计按 `exercise_id` 聚合，同一知识点下的不同题目互不串数。
"""

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.chat  # noqa: F401
import app.models.exercise  # noqa: F401
import app.models.misconception  # noqa: F401
import app.models.profile  # noqa: F401
import app.models.prompt  # noqa: F401
import app.models.rag  # noqa: F401
import app.models.submission  # noqa: F401
import app.models.user  # noqa: F401
from app.api.v1.exercises import SubmitExerciseRequest, submit_exercise_answer
from app.database.base import Base
from app.models.exercise import Exercise, TestCase
from app.models.profile import LearningEvent
from app.models.user import User, UserRole
from app.schemas.exercise import ExerciseGenerateRequest, SubmitExerciseRequest as _Req  # noqa: F401
from app.services.exercise_stats import aggregate_by_exercise, load_attempt_events


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'scoring.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
def stub_sandbox(monkeypatch):
    """用固定输出替代真实沙箱，避免测试依赖 Docker/子进程。"""

    async def fake_execute(code: str, stdin_input: str = ""):
        return {
            "status": "completed",
            "exit_code": 0,
            "stdout": f"answer:{stdin_input}",
            "stderr": "",
            "runtime_ms": 1.0,
            "memory_kb": None,
            "timeout_triggered": False,
        }

    import app.sandbox.runner as runner
    monkeypatch.setattr(runner, "execute_student_code", fake_execute)


async def make_user(db, user_id: str) -> User:
    user = User(
        id=user_id, email=f"{user_id}@example.com", password_hash="x",
        display_name=user_id, role=UserRole.STUDENT,
    )
    db.add(user)
    await db.commit()
    return user


async def make_exercise(db, title: str, concepts: str = "for_loop") -> Exercise:
    ex = Exercise(
        title=title, description="打印输入", difficulty=1, concepts=concepts,
        reference_solution="print(input())", is_published=True,
    )
    db.add(ex)
    await db.flush()
    db.add(TestCase(
        exercise_id=ex.id, input_data="5", expected_output="answer:5",
        is_hidden=False, description="公开用例", order_index=0,
    ))
    await db.commit()
    return ex


async def _passed_events(db, user_id: str, exercise_id: str) -> list[LearningEvent]:
    rows = (await db.execute(
        select(LearningEvent).where(
            LearningEvent.user_id == user_id,
            LearningEvent.event_type == "exercise_passed",
            LearningEvent.detail_json.like(f'%"{exercise_id}"%'),
        )
    )).scalars().all()
    return list(rows)


async def test_viewed_solution_scores_zero_and_records_no_pass(db, stub_sandbox):
    """看过答案再全对：0 分，且不产生 exercise_passed。"""
    from app.services.profile_service import record_event

    user = await make_user(db, "s-viewed")
    ex = await make_exercise(db, "打印输入")

    # 学生先看了参考答案（服务端事件）
    await record_event(db, user.id, "solution_viewed", detail={"exercise_id": ex.id})
    await db.commit()

    result = await submit_exercise_answer(
        exercise_id=ex.id,
        body=SubmitExerciseRequest(code="print(input())"),
        db=db,
        current_user=user,
    )

    assert result["test_results"]["all_passed"] is True
    assert result["score_pct"] == 0
    assert result["exp_gained"] == 0
    assert await _passed_events(db, user.id, ex.id) == []


async def test_independent_pass_after_viewing_solution_still_rewards(db, stub_sandbox):
    """看答案一次不等于永久作废：之后独立做对仍然首发奖励。"""
    from app.services.profile_service import record_event

    user = await make_user(db, "s-recover")
    ex = await make_exercise(db, "打印输入")

    await record_event(db, user.id, "solution_viewed", detail={"exercise_id": ex.id})
    await db.commit()
    first = await submit_exercise_answer(
        exercise_id=ex.id, body=SubmitExerciseRequest(code="print(input())"),
        db=db, current_user=user,
    )
    assert first["score_pct"] == 0

    second = await submit_exercise_answer(
        exercise_id=ex.id, body=SubmitExerciseRequest(code="print(input())"),
        db=db, current_user=user,
    )

    assert second["score_pct"] == 100
    assert second["exp_gained"] > 0
    assert len(await _passed_events(db, user.id, ex.id)) == 1


async def test_client_supplied_flags_are_ignored():
    """前端塞进来的 viewed_solution / used_hints 不再进入评分。"""
    parsed = SubmitExerciseRequest.model_validate(
        {"code": "print(1)", "viewed_solution": True, "used_hints": 3}
    )
    assert not hasattr(parsed, "viewed_solution")
    assert not hasattr(parsed, "used_hints")
    assert parsed.code == "print(1)"


async def test_admin_stats_are_per_exercise_not_per_concept(db, stub_sandbox):
    """同一知识点下的两道题，统计互不串。"""
    user = await make_user(db, "s-stats")
    ex_a = await make_exercise(db, "题 A", concepts="for_loop")
    ex_b = await make_exercise(db, "题 B", concepts="for_loop")

    await submit_exercise_answer(
        exercise_id=ex_a.id, body=SubmitExerciseRequest(code="print(input())"),
        db=db, current_user=user,
    )

    stats = aggregate_by_exercise(await load_attempt_events(db))
    assert stats[ex_a.id]["attempts"] == 1
    assert stats[ex_a.id]["passed"] == 1
    assert ex_b.id not in stats


async def test_event_detail_keeps_real_score(db, stub_sandbox):
    """detail 里记的是真实分数，不再被 already_passed 改写成 0。"""
    user = await make_user(db, "s-detail")
    ex = await make_exercise(db, "打印输入")

    await submit_exercise_answer(
        exercise_id=ex.id, body=SubmitExerciseRequest(code="print(input())"),
        db=db, current_user=user,
    )
    events = await _passed_events(db, user.id, ex.id)
    detail = json.loads(events[0].detail_json)
    assert detail["exercise_id"] == ex.id
    assert detail["score_pct"] == 100
