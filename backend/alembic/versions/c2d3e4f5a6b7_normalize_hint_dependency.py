"""normalize_hint_dependency_values

把 student_profiles.hint_dependency 从 JSON 字符串统一成等级标签。

背景：update_hint_dependency() 曾把 {"score": 1.0, "label": "high"} 整段写进
VARCHAR(20) 列。JSON 比列宽更长（SQLite 不校验，PostgreSQL 会报错），
并且教师端统计用的是 `hint_dependency == 'high'`，JSON 值永远匹配不上。

本迁移只做数据归一：能解析出 label 的取 label，解析失败或未知值落到 'low'。

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-10-22
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, Sequence[str], None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _normalize(raw: str | None) -> str:
    if not raw:
        return "low"
    text = str(raw).strip()
    if text.startswith("{"):
        try:
            label = json.loads(text).get("label")
        except (ValueError, TypeError):
            return "low"
        return label if label in {"low", "medium", "high"} else "low"
    return text if text in {"low", "medium", "high"} else "low"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "student_profiles" not in set(inspector.get_table_names()):
        return

    # 2.0 的字段此前是手工 ALTER 加的，旧基线里可能还没有这一列。
    # 新迁移 d3e4f5a6b7c8 会补列；这里没有列就直接跳过，不能让 fresh DB 卡住。
    columns = {c["name"] for c in inspector.get_columns("student_profiles")}
    if "hint_dependency" not in columns:
        return

    # 只处理需要改写的行；正常数据保持原样，避免整表重写。
    rows = bind.execute(sa.text(
        "SELECT id, hint_dependency FROM student_profiles "
        "WHERE hint_dependency IS NOT NULL AND hint_dependency NOT IN ('low','medium','high')"
    )).fetchall()

    for row_id, raw in rows:
        bind.execute(
            sa.text("UPDATE student_profiles SET hint_dependency = :value WHERE id = :id"),
            {"value": _normalize(raw), "id": row_id},
        )


def downgrade() -> None:
    """不可逆：旧值里的 score 已在归一过程中丢弃。"""
    pass
