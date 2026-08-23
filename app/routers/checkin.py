"""打卡 / 连续天数。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, timedelta

from ..database import get_db
from ..models import User, Checkin
from ..schemas import CheckinStatusResponse
from ..services.learning_common import compute_streaks
from ..services import stats
from ..deps import get_current_user

router = APIRouter()


@router.get("/checkin/status", response_model=CheckinStatusResponse)
async def get_checkin_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取打卡状态：今日是否已打卡、当前/最大连续天数、累计天数"""
    dates = await stats.fetch_checkin_dates(db, current_user.id)
    current, max_streak = compute_streaks(dates)
    last = max(dates) if dates else None
    return CheckinStatusResponse(
        checked_today=date.today() in dates,
        current_streak=current,
        max_streak=max_streak,
        total_days=len(dates),
        last_checkin_date=last,
    )


@router.get("/checkin/history")
async def get_checkin_history(
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取最近 N 天的打卡历史（用于日历/热力图展示）"""
    from_d = date.today() - timedelta(days=days - 1)
    result = await db.execute(
        select(Checkin.date)
        .where(Checkin.user_id == current_user.id, Checkin.date >= from_d)
        .order_by(Checkin.date)
    )
    dates = [d for d in result.scalars().all()]
    return {"days": days, "start": from_d, "dates": dates, "count": len(dates)}


@router.post("/checkin")
async def do_checkin(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """今日打卡（同一用户当天只能打卡一次，重复打卡幂等返回）"""
    today = date.today()
    result = await db.execute(
        select(Checkin).where(Checkin.user_id == current_user.id, Checkin.date == today)
    )
    existing = result.scalar_one_or_none()

    if existing:
        return {"checked_today": True, "created": False, "message": "今日已打卡"}

    db.add(Checkin(user_id=current_user.id, date=today))
    await db.commit()
    return {"checked_today": True, "created": True, "message": "打卡成功"}