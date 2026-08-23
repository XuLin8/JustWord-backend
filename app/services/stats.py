"""学习数据聚合查询。

把散落在 看板/效率/掌握度/统计 中的“取当前用户 words/records 并汇总”抽取为可复用助手，
避免同一套 SQL 与计算在多个 router 里复制。
"""
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import Optional

from ..models import Word as WordModel, LearningRecord, Checkin, WrongWord


async def fetch_words(db: AsyncSession, user_id: str) -> list:
    res = await db.execute(
        select(WordModel).where(WordModel.user_id == user_id)
    )
    return list(res.scalars().all())


async def fetch_records(
    db: AsyncSession, user_id: str, start: Optional[datetime] = None
) -> list:
    stmt = select(LearningRecord).where(LearningRecord.user_id == user_id)
    if start is not None:
        stmt = stmt.where(LearningRecord.created_at >= start)
    res = await db.execute(stmt)
    return list(res.scalars().all())


async def fetch_checkin_dates(db: AsyncSession, user_id: str) -> set:
    res = await db.execute(select(Checkin.date).where(Checkin.user_id == user_id))
    return set(res.scalars().all())


async def fetch_weak_word_ids(db: AsyncSession, user_id: str) -> set:
    res = await db.execute(
        select(WrongWord.word_id).where(
            WrongWord.user_id == user_id, WrongWord.status == "open"
        )
    )
    return set(res.scalars().all())


def summarize_records(records: list) -> dict:
    """统计学习记录：作答数/答对数/正确率/结果分布。"""
    attempts = len(records)
    correct_count = sum(1 for r in records if r.result == "correct")
    by_result_map = {"correct": 0, "partial": 0, "close": 0, "wrong": 0}
    for r in records:
        by_result_map[r.result] = by_result_map.get(r.result, 0) + 1
    return {
        "total_attempts": attempts,
        "correct_count": correct_count,
        "correct_rate": correct_count / attempts if attempts > 0 else 0,
        "by_result": [{"result": k, "count": v} for k, v in by_result_map.items()],
    }


def summarize_words(words: list, now: Optional[datetime] = None) -> dict:
    """统计单词概况：总数/已学/掌握/熟练度分布/待复习与待学。"""
    now = now or datetime.now()
    from .learning_common import mastery_level
    total = len(words)
    learned = sum(1 for w in words if (w.repetitions or 0) > 0)
    mastered = sum(1 for w in words if (w.repetitions or 0) >= 6)

    distribution = {"未学": 0, "新学": 0, "巩固中": 0, "已掌握": 0}
    for w in words:
        distribution[mastery_level(w.repetitions or 0)] += 1

    new_words_due = sum(1 for w in words if (w.repetitions or 0) == 0)
    review_words_due = sum(
        1
        for w in words
        if (w.repetitions or 0) > 0
        and w.next_review_at is not None
        and w.next_review_at <= now
    )
    return {
        "total": total,
        "learned": learned,
        "mastered": mastered,
        "new_words_due": new_words_due,
        "review_words_due": review_words_due,
        "distribution": [{"label": k, "count": v} for k, v in distribution.items()],
    }