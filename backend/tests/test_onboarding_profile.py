"""
入门诊断 → 学习画像 → 教师看板 的回归测试
=========================================

任务清单 06 的验收点：入门诊断的逐题结果必须真正落到画像里，
并且不同账号之间不能互相污染。

这些用例不依赖运行中的服务器，也不碰开发库：
每个用例自建一个临时 SQLite 文件，直接调用路由函数。
"""

import json

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.chat  # noqa: F401  —— 导入以注册所有表
import app.models.exercise  # noqa: F401
import app.models.misconception  # noqa: F401
import app.models.profile  # noqa: F401
import app.models.prompt  # noqa: F401
import app.models.rag  # noqa: F401
import app.models.submission  # noqa: F401
import app.models.user  # noqa: F401
from app.api.v1.profile import complete_onboarding
from app.api.v1.teacher import teacher_overview
from app.database.base import Base
from app.models.user import User, UserRole
from app.services.profile_service import get_or_create_profile, get_weaknesses


@pytest.fixture
async def db(tmp_path):
    """独立的临时库，避免测试写进开发库 ai_tutor.db。"""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'test.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


async def make_user(db, user_id: str, role: UserRole = UserRole.STUDENT) -> User:
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        password_hash="x",
        display_name=user_id,
        role=role,
    )
    db.add(user)
    await db.commit()
    return user


async def test_diagnosis_results_reach_profile(db):
    """诊断出的薄弱点和误区要写进画像，而不只是存一条事件。"""
    student = await make_user(db, "s-onboarding")

    resp = await complete_onboarding(
        body={
            "skill_level": "B",
            "diagnosis": {
                "level": "beginner",
                "weak": ["for_loop", "function"],
                "misconceptions": ["M5", "M6"],
            },
        },
        db=db,
        current_user=student,
    )
    assert resp["weak_count"] == 2

    profile = await get_or_create_profile(db, student.id)
    weak_topics = json.loads(profile.weak_topics or "[]")
    assert set(weak_topics) >= {"for_loop", "function"}

    weaknesses = await get_weaknesses(db, student.id)
    assert {w["concept"] for w in weaknesses} >= {"for_loop", "function"}

    assert json.loads(profile.recent_misconceptions or "[]") == ["M5", "M6"]
    assert profile.weak_topics and profile.recent_misconceptions


async def test_teacher_dashboard_sees_diagnosed_weaknesses(db):
    """诊断出的薄弱点要能被教师看板聚合到。"""
    student = await make_user(db, "s-teacher-view")
    teacher = await make_user(db, "t-view", role=UserRole.INSTRUCTOR)

    await complete_onboarding(
        body={"skill_level": "A", "diagnosis": {"weak": ["while_loop"]}},
        db=db,
        current_user=student,
    )

    overview = await teacher_overview(db=db, current_user=teacher)
    topics = {t["concept"]: t["count"] for t in overview["weak_topic_stats"]}
    assert topics.get("while_loop", 0) >= 1


async def test_second_account_does_not_inherit_profile(db):
    """两个账号的画像互相独立——教师重新登录不会看到上一个学生的薄弱点。"""
    first = await make_user(db, "s-first")
    second = await make_user(db, "s-second")

    await complete_onboarding(
        body={"skill_level": "B", "diagnosis": {"weak": ["list"], "misconceptions": ["M3"]}},
        db=db,
        current_user=first,
    )

    second_profile = await get_or_create_profile(db, second.id)
    assert not second_profile.weak_topics
    assert not second_profile.recent_misconceptions
    assert await get_weaknesses(db, second.id) == []


async def test_onboarding_without_diagnosis_is_harmless(db):
    """A/D 这类没有诊断数据的入口不能因为缺字段而 500。"""
    student = await make_user(db, "s-no-diagnosis")

    resp = await complete_onboarding(body={"skill_level": "D"}, db=db, current_user=student)
    assert resp["weak_count"] == 0

    profile = await get_or_create_profile(db, student.id)
    assert not profile.recent_misconceptions
