"""
误区专项练习种子接口的回归测试
==============================

历史问题：
- 幂等检查拿 `ex["title"]`（无前缀）比对入库的 `[M1] 标题`，永远不相等，
  每调一次接口就把 16 道题再插一遍（开发库里曾经每题两份）；
- 接口没有任何鉴权，学生也能触发写库。
"""

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.chat  # noqa: F401
import app.models.exercise  # noqa: F401
import app.models.misconception  # noqa: F401
import app.models.profile  # noqa: F401
import app.models.prompt  # noqa: F401
import app.models.rag  # noqa: F401
import app.models.submission  # noqa: F401
import app.models.user  # noqa: F401
from app.api.v1.misconception_exercises import router as mc_exercises_router
from app.data.mc_exercises import MC_EXERCISES
from app.database.base import Base
from app.database.session import get_db
from app.models.exercise import Exercise
from app.models.user import User, UserRole
from app.security.dependencies import get_current_user


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'seed.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


def make_client(session, user):
    app = FastAPI()
    app.include_router(mc_exercises_router, prefix="/api/v1/exercises")

    async def _db():
        yield session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[get_current_user] = lambda: user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def make_user(db, user_id: str, role: UserRole) -> User:
    user = User(
        id=user_id, email=f"{user_id}@example.com", password_hash="x",
        display_name=user_id, role=role,
    )
    db.add(user)
    await db.commit()
    return user


async def _count(db) -> int:
    return (await db.execute(select(func.count()).select_from(Exercise))).scalar() or 0


async def test_student_cannot_seed(db):
    student = await make_user(db, "s-seed", UserRole.STUDENT)
    async with make_client(db, student) as client:
        resp = await client.post("/api/v1/exercises/seed-mc-exercises")
    assert resp.status_code == 403
    assert await _count(db) == 0


async def test_seed_is_idempotent(db):
    admin = await make_user(db, "a-seed", UserRole.ADMIN)
    async with make_client(db, admin) as client:
        first = await client.post("/api/v1/exercises/seed-mc-exercises")
        second = await client.post("/api/v1/exercises/seed-mc-exercises")

    assert first.status_code == 200
    assert first.json()["seeded"] == len(MC_EXERCISES)
    assert second.json()["seeded"] == 0
    assert await _count(db) == len(MC_EXERCISES)


async def test_seed_cleans_up_historical_duplicates(db):
    """库里已有的重复行（旧实现留下的）会在下次调用时被清掉。"""
    admin = await make_user(db, "a-dup", UserRole.ADMIN)
    first = MC_EXERCISES[0]
    title = f'[{first["code"]}] {first["title"]}'

    for _ in range(2):
        db.add(Exercise(title=title, description="dup", difficulty=1, concepts=first["code"]))
    await db.commit()
    assert await _count(db) == 2

    async with make_client(db, admin) as client:
        resp = await client.post("/api/v1/exercises/seed-mc-exercises")

    body = resp.json()
    assert body["removed_duplicates"] == 1
    assert body["seeded"] == len(MC_EXERCISES) - 1
    assert await _count(db) == len(MC_EXERCISES)
