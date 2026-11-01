"""
学习闭环回归测试
================

对任务 06 的验收路径做一次服务层串联：
入门诊断答错 → 学完一课 → 练习失败 → 请求提示 → 修正通过，
最后画像与教师看板都能重建这个过程。
"""

import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.chat  # noqa: F401
import app.models.exercise  # noqa: F401
import app.models.misconception  # noqa: F401
import app.models.profile  # noqa: F401
import app.models.prompt  # noqa: F401
import app.models.rag  # noqa: F401
import app.models.submission  # noqa: F401
import app.models.user  # noqa: F401
from app.database.base import Base
from app.models.user import User, UserRole
from app.services.profile_service import (
    get_or_create_profile,
    get_profile_summary,
    get_weaknesses,
    record_event,
    update_weakness,
)


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'loop.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


@pytest.fixture
async def student(db):
    user = User(
        id="s-loop",
        email="loop@example.com",
        password_hash="x",
        display_name="闭环学生",
        role=UserRole.STUDENT,
    )
    db.add(user)
    await db.commit()
    return user


async def test_full_learning_loop_is_reconstructable(db, student):
    # 1) 入门诊断答错两题 → 两个薄弱点
    await update_weakness(db, student.id, "for_loop")
    await update_weakness(db, student.id, "function")
    assert {w["concept"] for w in await get_weaknesses(db, student.id)} == {"for_loop", "function"}

    # 2) 学完一课 → completed_lessons 记在画像上
    await record_event(db, student.id, "lesson_completed", concept="lesson_1")

    # 3) 练习失败 → 严重度累加
    await update_weakness(db, student.id, "for_loop")
    await update_weakness(db, student.id, "for_loop")
    weak = {w["concept"]: w for w in await get_weaknesses(db, student.id)}
    assert weak["for_loop"]["fail_count"] == 3
    assert weak["for_loop"]["severity"] == 3

    # 4) 请求提示 → 画像计数 + 提示依赖字段仍可读
    await record_event(db, student.id, "hint_requested", concept="for_loop",
                       detail={"exercise_id": "ex-1", "hint_level": 2})
    profile = await get_or_create_profile(db, student.id)
    assert profile.total_hints_used == 1
    assert profile.hint_dependency in {"low", "medium", "high"}

    # 5) 修正通过 → 该弱点 resolved，weak_topics 同步
    await update_weakness(db, student.id, "for_loop", is_success=True)
    remaining = {w["concept"] for w in await get_weaknesses(db, student.id)}
    assert remaining == {"function"}
    await db.refresh(profile)
    assert json.loads(profile.weak_topics or "[]") == ["function"]

    # 6) 画像摘要能还原全过程
    summary = await get_profile_summary(db, student.id)
    assert "lesson_1" in summary["completed_lessons"]
    assert summary["stats"]["hints_used"] == 1
    assert [w["concept"] for w in summary["weaknesses"]] == ["function"]


async def test_lesson_completion_is_idempotent(db, student):
    await record_event(db, student.id, "lesson_completed", concept="lesson_1")
    await record_event(db, student.id, "lesson_completed", concept="lesson_1")

    profile = await get_or_create_profile(db, student.id)
    assert json.loads(profile.completed_lessons) == ["lesson_1"]
