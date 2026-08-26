"""每日聚合统计（懒聚合 lazy upsert）。

从 learning_records 按学习日（02:00 边界）全量重算并 upsert 到 daily_stats：
- 提交复习 / 上报会话 / 访问 /stats/daily 时按需回填，避免定时任务。
- duration_seconds 来自 /sessions 上报，重算学习类字段时保留（不覆盖）。
"""
from datetime import datetime, date, time, timedelta
from typing import Iterable

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.mysql import insert as mysql_insert

from ..models import LearningRecord, DailyStat


def learning_day_bounds(learning_date: date, offset: timedelta) -> tuple:
    """学习日 [L 02:00, L+1 02:00) 对应的 UTC 起止时间。"""
    start_local = datetime.combine(learning_date, time(0, 0)) + timedelta(hours=2)
    end_local = start_local + timedelta(days=1)
    return start_local - offset, end_local - offset


def current_learning_date(offset: timedelta) -> date:
    return (datetime.now() - timedelta(hours=2)).date()


def to_learning_date(dt: datetime, offset: timedelta) -> date:
    # 把一条 UTC 时间戳归并到对应的学习日（本地 02:00 边界）
    return (dt + offset - timedelta(hours=2)).date()


async def fetch_day_records(db: AsyncSession, user_id: str, learning_date: date, offset: timedelta) -> list:
    start, end = learning_day_bounds(learning_date, offset)
    res = await db.execute(
        select(LearningRecord).where(
            LearningRecord.user_id == user_id,
            LearningRecord.created_at >= start,
            LearningRecord.created_at < end,
        )
    )
    return list(res.scalars().all())


async def upsert_day(db: AsyncSession, user_id: str, learning_date: date, fields: dict,
                     add: bool = False, preserve: Iterable[str] = ()) -> None:
    """MySQL ON DUPLICATE KEY UPDATE upsert 到 daily_stats。
    - add=True：数值字段在原值基础上累加（用于 duration_seconds 上报）
    - preserve：重算时保留原值的列（如 duration_seconds 不参与重算覆盖）
    """
    values = {"user_id": user_id, "learning_date": learning_date}
    values.update(fields)
    stmt = mysql_insert(DailyStat).values(**values)
    update_cols = {}
    for k, v in fields.items():
        if add:
            update_cols[k] = DailyStat.__table__.c[k] + v
        elif k in preserve:
            update_cols[k] = DailyStat.__table__.c[k]
        else:
            update_cols[k] = v
    if update_cols:
        stmt = stmt.on_duplicate_key_update(**update_cols)
    await db.execute(stmt)


async def recompute_day(db: AsyncSession, user_id: str, learning_date: date, offset: timedelta) -> None:
    """从 learning_records 重算该学习日的学习类字段并 upsert（保留 duration_seconds）。"""
    records = await fetch_day_records(db, user_id, learning_date, offset)
    distinct = len({r.word_id for r in records if r.word_id})
    attempts = len(records)
    correct_count = sum(1 for r in records if r.result in ("correct", "partial"))
    partial_count = sum(1 for r in records if r.result == "partial")
    wrong_count = sum(1 for r in records if r.result not in ("correct", "partial"))
    ms_vals = [r.response_ms or 0 for r in records if r.response_ms is not None]
    avg_response_ms = round(sum(ms_vals) / len(ms_vals)) if ms_vals else 0
    new_learned = sum(1 for r in records if r.is_new)
    review_learned = sum(1 for r in records if r.is_new is False)
    await upsert_day(db, user_id, learning_date, {
        "distinct_words": distinct,
        "attempts": attempts,
        "correct_count": correct_count,
        "partial_count": partial_count,
        "wrong_count": wrong_count,
        "avg_response_ms": avg_response_ms,
        "new_learned": new_learned,
        "review_learned": review_learned,
    }, preserve=("duration_seconds",))


async def add_session_duration(db: AsyncSession, user_id: str, learning_date: date, seconds: int) -> None:
    await upsert_day(db, user_id, learning_date, {"duration_seconds": max(0, int(seconds))}, add=True)


async def count_today_correct(db: AsyncSession, user_id: str, offset: timedelta) -> int:
    """今日（学习日）答对数（correct + partial），供 /progress 与打卡门槛实时统计。"""
    today = current_learning_date(offset)
    start, end = learning_day_bounds(today, offset)
    res = await db.execute(
        select(func.count()).select_from(LearningRecord).where(
            LearningRecord.user_id == user_id,
            LearningRecord.created_at >= start,
            LearningRecord.created_at < end,
            LearningRecord.result.in_(("correct", "partial")),
        )
    )
    return res.scalar_one() or 0
