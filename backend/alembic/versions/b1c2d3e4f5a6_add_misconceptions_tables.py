"""add_misconceptions_and_events

补齐此前只在模型里定义、却从未进入 Alembic 的两张表。

背景：项目长期依赖启动时 Base.metadata.create_all() 建表，因此
`misconceptions` / `misconception_events` 虽然一直存在，但没有对应迁移。
这里补上，同时用 inspector 做幂等保护——已经由 create_all 建好表的库
不会因为执行本迁移而失败。

Revision ID: b1c2d3e4f5a6
Revises: afc8d011c8ae
Create Date: 2026-10-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, Sequence[str], None] = "afc8d011c8ae"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "misconceptions" not in existing:
        op.create_table(
            "misconceptions",
            sa.Column("code", sa.String(length=10), nullable=False, comment="误区编号 M1-M8"),
            sa.Column("name", sa.String(length=100), nullable=False, comment="误区名称"),
            sa.Column("description", sa.Text(), nullable=False, comment="误区详细描述"),
            sa.Column("typical_patterns", sa.Text(), nullable=True,
                      comment="典型代码模式（JSON 数组，用于规则匹配）"),
            sa.Column("related_concepts", sa.String(length=200), nullable=True,
                      comment="关联知识点，逗号分隔"),
            sa.Column("recommended_strategy", sa.String(length=50), nullable=False,
                      comment="推荐教学策略"),
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_misconceptions_id"), "misconceptions", ["id"], unique=False)
        op.create_index(op.f("ix_misconceptions_code"), "misconceptions", ["code"], unique=True)

    if "misconception_events" not in existing:
        op.create_table(
            "misconception_events",
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("misconception_id", sa.String(), nullable=True),
            sa.Column("submission_id", sa.String(), nullable=True),
            sa.Column("exercise_id", sa.String(), nullable=True),
            sa.Column("confidence", sa.Float(), nullable=False, comment="诊断置信度 0-1"),
            sa.Column("evidence", sa.Text(), nullable=True, comment="诊断依据"),
            sa.Column("code_snippet", sa.Text(), nullable=True),
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True),
                      server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True),
                      server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["misconception_id"], ["misconceptions.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_misconception_events_id"), "misconception_events",
                        ["id"], unique=False)
        op.create_index(op.f("ix_misconception_events_user_id"), "misconception_events",
                        ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "misconception_events" in existing:
        op.drop_index(op.f("ix_misconception_events_user_id"), table_name="misconception_events")
        op.drop_index(op.f("ix_misconception_events_id"), table_name="misconception_events")
        op.drop_table("misconception_events")

    if "misconceptions" in existing:
        op.drop_index(op.f("ix_misconceptions_code"), table_name="misconceptions")
        op.drop_index(op.f("ix_misconceptions_id"), table_name="misconceptions")
        op.drop_table("misconceptions")
