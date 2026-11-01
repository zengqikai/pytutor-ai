"""
练习成绩统计
============

练习提交写进 `LearningEvent`，`detail_json` 里带 `exercise_id` 与 `score_pct`。
过去统计一律按 `concept` 聚合，导致：

- 同一个知识点下的多道题共用一份通过率；
- 只通过概念去重，学生做对同一概念的两道题只算一次；
- 得分 0（看过答案）的"通过"也被算成通过。

这里统一按 `exercise_id` 聚合，并且只认 `score_pct > 0` 的通过。

`detail_json` 是 Text 列（不是 JSON 列），SQLite/PostgreSQL 都能跑，但没法
用 JSON 函数统一过滤，所以读出来在 Python 里解析。调用方可以用
`exercise_id` 预过滤，把扫描量压到单题级别。
"""

import json
from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import LearningEvent

# 只有这三种事件算"尝试过这道题"；hint_requested / solution_viewed 不算
ATTEMPT_EVENT_TYPES = ("exercise_passed", "exercise_failed", "exercise_retry")


def parse_detail(detail_json: str | None) -> dict:
    """把 detail_json 解析成 dict，坏数据返回空 dict。"""
    if not detail_json:
        return {}
    try:
        data = json.loads(detail_json)
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def detail_exercise_id(detail: dict) -> str | None:
    value = detail.get("exercise_id")
    return str(value) if value else None


def detail_score(detail: dict) -> int:
    try:
        return int(detail.get("score_pct") or 0)
    except (ValueError, TypeError):
        return 0


def is_counted_pass(event_type: str, detail: dict) -> bool:
    """只有记了分（>0）的 exercise_passed 才算通过。"""
    return event_type == "exercise_passed" and detail_score(detail) > 0


async def load_attempt_events(
    db: AsyncSession,
    *,
    user_id: str | None = None,
    exercise_id: str | None = None,
) -> list[dict]:
    """读取尝试事件（按时间升序）。

    返回 [{user_id, event_type, concept, exercise_id, detail, created_at}, ...]
    """
    stmt = select(
        LearningEvent.user_id,
        LearningEvent.event_type,
        LearningEvent.concept,
        LearningEvent.detail_json,
        LearningEvent.created_at,
    ).where(LearningEvent.event_type.in_(ATTEMPT_EVENT_TYPES))
    if user_id:
        stmt = stmt.where(LearningEvent.user_id == user_id)
    if exercise_id:
        # Text 列上的粗过滤，真正匹配交给下面的 detail 解析
        stmt = stmt.where(LearningEvent.detail_json.like(f'%"{exercise_id}"%'))
    stmt = stmt.order_by(LearningEvent.created_at)

    rows = (await db.execute(stmt)).all()
    events = []
    for uid, etype, concept, detail_json, created_at in rows:
        detail = parse_detail(detail_json)
        ex_id = detail_exercise_id(detail)
        if exercise_id and ex_id != exercise_id:
            continue
        events.append({
            "user_id": uid,
            "event_type": etype,
            "concept": concept,
            "exercise_id": ex_id,
            "detail": detail,
            "created_at": created_at,
        })
    return events


def aggregate_by_exercise(events: Iterable[dict]) -> dict[str, dict]:
    """按题目聚合：{exercise_id: {attempts, passed, students_passed, best_score}}。"""
    stats: dict[str, dict] = {}
    for e in events:
        ex_id = e.get("exercise_id")
        if not ex_id:
            continue
        entry = stats.setdefault(
            ex_id, {"attempts": 0, "passed": 0, "_students": set(), "best_score": 0}
        )
        entry["attempts"] += 1
        if is_counted_pass(e["event_type"], e["detail"]):
            entry["passed"] += 1
            entry["_students"].add(e["user_id"])
            entry["best_score"] = max(entry["best_score"], detail_score(e["detail"]))

    for entry in stats.values():
        entry["students_passed"] = len(entry.pop("_students"))
    return stats


async def passed_exercise_ids(db: AsyncSession, user_id: str) -> set[str]:
    """某学生计分通过的题目 ID 集合。"""
    events = await load_attempt_events(db, user_id=user_id)
    return {
        e["exercise_id"]
        for e in events
        if e["exercise_id"] and is_counted_pass(e["event_type"], e["detail"])
    }


async def passed_count_by_user(db: AsyncSession) -> dict[str, int]:
    """每个学生计分通过的**不重复题目数**。"""
    events = await load_attempt_events(db)
    passed: dict[str, set[str]] = {}
    for e in events:
        if not e["exercise_id"] or not is_counted_pass(e["event_type"], e["detail"]):
            continue
        passed.setdefault(e["user_id"], set()).add(e["exercise_id"])
    return {uid: len(ids) for uid, ids in passed.items()}
