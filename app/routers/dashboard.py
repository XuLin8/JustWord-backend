"""学习统计看板。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, date

from ..database import get_db
from ..models import User
from ..schemas import (
    DashboardResponse,
    DashboardWordStats,
    DashboardLearningStats,
)
from ..services.learning_common import local_offset, build_daily_trend, compute_streaks
from ..services import stats
from ..deps import get_current_user

router = APIRouter()


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    trend_days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """学习统计看板：单词掌握概况、SRS 熟练度分布、练习正确率、近 N 天趋势、打卡统计"""
    words = await stats.fetch_words(db, current_user.id)
    records = await stats.fetch_records(db, current_user.id)
    word_stats = stats.summarize_words(words)
    learning_stats = stats.summarize_records(records)

    daily_trend = build_daily_trend(records, trend_days, local_offset(), date.today())

    checkin_dates = await stats.fetch_checkin_dates(db, current_user.id)
    current, max_streak = compute_streaks(checkin_dates)

    return DashboardResponse(
        word_stats=DashboardWordStats(
            total=word_stats["total"],
            learned=word_stats["learned"],
            mastered=word_stats["mastered"],
            new_words_due=word_stats["new_words_due"],
            review_words_due=word_stats["review_words_due"],
            distribution=word_stats["distribution"],
        ),
        learning_stats=DashboardLearningStats(
            total_attempts=learning_stats["total_attempts"],
            correct_count=learning_stats["correct_count"],
            correct_rate=learning_stats["correct_rate"],
            by_result=learning_stats["by_result"],
        ),
        daily_trend=daily_trend,
        checkin_stats={
            "current_streak": current,
            "max_streak": max_streak,
            "total_days": len(checkin_dates),
            "last_checkin_date": max(checkin_dates) if checkin_dates else None,
        },
    )