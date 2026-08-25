"""今日学习进度接口（P0：进度条后端化数据源）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User, UserPreference
from ..schemas import ProgressResponse
from ..services import daily_stats, stats as stats_svc
from ..services.learning_common import local_offset
from ..deps import get_current_user

router = APIRouter()


@router.get("/progress", response_model=ProgressResponse)
async def get_progress(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    offset = local_offset()
    today = daily_stats.current_learning_date(offset)
    today_correct = await daily_stats.count_today_correct(db, current_user.id, offset)

    res = await db.execute(select(UserPreference).where(UserPreference.user_id == current_user.id))
    pref = res.scalar_one_or_none()
    daily_target = (pref.daily_target or 20) if pref else 20

    dates = await stats_svc.fetch_checkin_dates(db, current_user.id)
    checked_today = today in dates

    remaining = max(0, daily_target - today_correct)
    progress_percent = round(min(100.0, today_correct / daily_target * 100), 1) if daily_target > 0 else 0.0
    return ProgressResponse(
        learning_date=today,
        daily_target=daily_target,
        today_correct=today_correct,
        progress_percent=progress_percent,
        checked_today=checked_today,
        remaining=remaining,
    )
