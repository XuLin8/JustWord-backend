"""打卡 / 连续天数。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import date, timedelta

from ..database import get_db
from ..models import User, Checkin, UserPreference
from ..schemas import CheckinStatusResponse
from ..services.learning_common import compute_streaks, local_offset
from ..services import stats, daily_stats
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
    today = daily_stats.current_learning_date(local_offset())
    return CheckinStatusResponse(
        checked_today=today in dates,
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
    """今日打卡（学习日 02:00 边界；同一用户当天只能打卡一次，重复幂等）。
    门槛：今日答对次数 >= 每日目标 才可打卡；未达标返回 403 及还差数量。"""
    offset = local_offset()
    today = daily_stats.current_learning_date(offset)
    result = await db.execute(
        select(Checkin).where(Checkin.user_id == current_user.id, Checkin.date == today)
    )
    existing = result.scalar_one_or_none()

    if existing:
        return {"checked_today": True, "created": False, "message": "今日已打卡"}

    # 打卡门槛：今日答对 >= 每日目标
    today_correct = await daily_stats.count_today_correct(db, current_user.id, offset)
    pref_res = await db.execute(select(UserPreference).where(UserPreference.user_id == current_user.id))
    pref = pref_res.scalar_one_or_none()
    target = (pref.daily_target or 20) if pref else 20
    if today_correct < target:
        remaining = target - today_correct
        raise HTTPException(
            status_code=403,
            detail={"message": f"今日答对还差 {remaining} 个词，达到每日目标后才能打卡", "remaining": remaining},
        )

    db.add(Checkin(user_id=current_user.id, date=today))
    await db.commit()
    return {"checked_today": True, "created": True, "message": "打卡成功"}