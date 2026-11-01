"""
接口错误契约的回归测试
======================

历史问题：找不到资源时返回 `200 {"detail": "..."}`，前端 `res.ok` 为真，
把错误当成功渲染；`body: dict` 的接口对超长代码没有任何限制。

这里直接调用路由函数，断言抛出的 HTTPException 状态码。
"""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models.chat  # noqa: F401
import app.models.exercise  # noqa: F401
import app.models.misconception  # noqa: F401
import app.models.profile  # noqa: F401
import app.models.prompt  # noqa: F401
import app.models.rag  # noqa: F401
import app.models.submission  # noqa: F401
import app.models.user  # noqa: F401
from app.api.v1.admin import student_detail, toggle_exercise
from app.api.v1.code import get_submission
from app.database.base import Base
from app.models.submission import CodeSubmission
from app.models.user import User, UserRole
from app.schemas.code import AnalyzeErrorRequest
from app.schemas.exercise import ExercisePublishRequest


@pytest.fixture
async def db(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'errors.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    Session = async_sessionmaker(engine, expire_on_commit=False)
    async with Session() as session:
        yield session
    await engine.dispose()


async def make_user(db, user_id: str, role: UserRole = UserRole.STUDENT) -> User:
    user = User(
        id=user_id, email=f"{user_id}@example.com", password_hash="x",
        display_name=user_id, role=role,
    )
    db.add(user)
    await db.commit()
    return user


async def _status(coro) -> int:
    with pytest.raises(HTTPException) as exc:
        await coro
    return exc.value.status_code


async def test_missing_submission_is_404(db):
    student = await make_user(db, "s-code")
    assert await _status(get_submission(
        submission_id="nope", db=db, current_user=student,
    )) == 404


async def test_other_students_submission_is_403(db):
    owner = await make_user(db, "s-owner")
    intruder = await make_user(db, "s-intruder")
    sub = CodeSubmission(id="sub-1", user_id=owner.id, code="print(1)", status="completed")
    db.add(sub)
    await db.commit()

    assert await _status(get_submission(
        submission_id=sub.id, db=db, current_user=intruder,
    )) == 403


async def test_missing_student_overview_is_404(db):
    admin = await make_user(db, "a-1", UserRole.ADMIN)
    assert await _status(student_detail(
        student_id="nope", db=db, current_user=admin,
    )) == 404


async def test_missing_exercise_publish_is_404(db):
    admin = await make_user(db, "a-2", UserRole.ADMIN)
    assert await _status(toggle_exercise(
        exercise_id="nope", body=ExercisePublishRequest(is_published=True),
        db=db, current_user=admin,
    )) == 404


def test_analyze_request_is_length_limited():
    """分析接口会把代码拼进 prompt，必须限长。"""
    with pytest.raises(ValidationError):
        AnalyzeErrorRequest(code="x" * 50_001)
    assert AnalyzeErrorRequest(code="print(1)").stderr == ""
