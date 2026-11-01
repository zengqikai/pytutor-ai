"""add_profile_learning_fields

补齐 PyTutor 2.0 的画像字段。这些列原先只靠手工 ALTER / create_all 添加，
迁移链里没有，导致生产环境（APP_ENV=production 不跑 create_all）从空库
upgrade 出来的 student_profiles 缺列，启动后画像读写直接报错。

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, Sequence[str], None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


NEW_COLUMNS = [
    (
        "weak_topics",
        sa.Column("weak_topics", sa.Text(), nullable=True,
                  comment="薄弱知识点列表（JSON）"),
    ),
    (
        "recent_misconceptions",
        sa.Column("recent_misconceptions", sa.Text(), nullable=True,
                  comment="最近出现的误区 ID（JSON）"),
    ),
    (
        "hint_dependency",
        sa.Column("hint_dependency", sa.String(length=20), nullable=True,
                  server_default="low", comment="提示依赖度：low/medium/high"),
    ),
    (
        "completed_lessons",
        sa.Column("completed_lessons", sa.Text(), nullable=True,
                  comment="已完成课程列表（JSON）"),
    ),
]


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "student_profiles" not in set(inspector.get_table_names()):
        return

    existing = {c["name"] for c in inspector.get_columns("student_profiles")}
    for name, column in NEW_COLUMNS:
        if name not in existing:
            op.add_column("student_profiles", column)


def downgrade() -> None:
    """SQLite 不支持 DROP COLUMN 的旧版本；只在明确支持时回滚。"""
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "student_profiles" not in set(inspector.get_table_names()):
        return
    existing = {c["name"] for c in inspector.get_columns("student_profiles")}
    for name, _ in reversed(NEW_COLUMNS):
        if name in existing:
            op.drop_column("student_profiles", name)
