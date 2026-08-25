"""学习会话上报 + 每日聚合统计接口（P1）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from ..database import get_db
from ..models import User, DailyStat, WordSnapshot
from ..schemas import SessionReport, DailyStatItem
from ..services import daily_stats
from ..services.learning_common import local_offset
from ..deps import get_current_user

router = APIRouter()


@router.post("/sessions")
async def report_session(
    payload: SessionReport,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = local_offset()
    learning_date = payload.date or daily_stats.current_learning_date(offset)
    await daily_stats.add_session_duration(db, current_user.id, learning_date, payload.duration_seconds)
    await db.commit()
    await daily_stats.recompute_day(db, current_user.id, learning_date, offset)
    await db.commit()
    return {"ok": True, "learning_date": learning_date}


@router.get("/stats/daily")
async def get_daily_stats(
    days: int = 365,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = local_offset()
    days = max(1, min(days, 365))
    today = daily_stats.current_learning_date(offset)
    from_d = today - timedelta(days=days - 1)

    # 懒聚合：回填最近 N 天缺失的学习日
    for i in range(days):
        await daily_stats.recompute_day(db, current_user.id, from_d + timedelta(days=i), offset)
    await db.commit()

    res = await db.execute(
        select(DailyStat).where(
            DailyStat.user_id == current_user.id,
            DailyStat.learning_date >= from_d,
            DailyStat.learning_date <= today,
        ).order_by(DailyStat.learning_date)
    )
    rows = res.scalars().all()
    return {
        "days": days,
        "start": from_d,
        "items": [
            DailyStatItem(
                date=r.learning_date,
                attempts=r.attempts or 0,
                correct_count=r.correct_count or 0,
                partial_count=r.partial_count or 0,
                wrong_count=r.wrong_count or 0,
                distinct_words=r.distinct_words or 0,
                duration_seconds=r.duration_seconds or 0,
                avg_response_ms=r.avg_response_ms or 0,
                new_learned=r.new_learned or 0,
                review_learned=r.review_learned or 0,
            )
            for r in rows
        ],
    }


@router.get("/stats/snapshots")
async def get_word_snapshots(
    word_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """某单词的 SM-2 调度历史快照（记忆曲线 EF 演变数据源）。"""
    res = await db.execute(
        select(WordSnapshot)
        .where(WordSnapshot.user_id == current_user.id, WordSnapshot.word_id == word_id)
        .order_by(WordSnapshot.captured_at)
    )
    rows = res.scalars().all()
    return {
        "word_id": word_id,
        "items": [
            {
                "captured_at": s.captured_at.isoformat() if s.captured_at else None,
                "repetitions": s.repetitions,
                "interval_days": s.interval_days,
                "ef": s.ef,
                "next_review_at": s.next_review_at.isoformat() if s.next_review_at else None,
            }
            for s in rows
        ],
    }