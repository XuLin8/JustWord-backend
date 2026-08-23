"""遗忘曲线 / 掌握度 / 效率分析。"""
import math
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, date, timedelta

from ..database import get_db
from ..models import User, Word as WordModel
from ..schemas import (
    ForgettingCurveResponse,
    ForgettingPoint,
    WordMasteryItem,
    MasteryResponse,
    EfficiencyResponse,
)
from ..services.learning_common import word_retention, mastery_level
from ..services import stats
from ..deps import get_current_user

router = APIRouter()


@router.get("/forgetting-curve", response_model=ForgettingCurveResponse)
async def get_forgetting_curve(
    word_id: Optional[str] = None,
    days: int = 30,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """预测指定词未来 N 天的遗忘曲线；不传 word_id 时返回全部已学词的平均曲线。

    retention 依据 SM-2 间隔天数作为稳定度拟合 Ebbinghaus 指数衰减。
    """
    days = max(1, min(days, 365))
    today = date.today()

    def _points(stability: float, ref: datetime) -> list[ForgettingPoint]:
        pts = []
        for i in range(days):
            d = today + timedelta(days=i)
            t = (datetime.combine(d, datetime.min.time()) - ref).total_seconds() / 86400.0
            r = math.exp(-max(t, 0.0) / max(stability, 0.5))
            pts.append(ForgettingPoint(date=d, retention=round(min(max(r, 0.0), 1.0), 3)))
        return pts

    if word_id:
        res = await db.execute(
            select(WordModel).where(WordModel.id == word_id, WordModel.user_id == current_user.id)
        )
        word = res.scalar_one_or_none()
        if not word:
            raise HTTPException(status_code=404, detail="单词不存在")
        ref = word.last_reviewed_at or datetime.now()
        stability = float(word.review_interval or 0)
        if (word.repetitions or 0) <= 0 or stability <= 0:
            return ForgettingCurveResponse(
                word_id=word.id, english=word.english, stability_days=None,
                last_reviewed_at=word.last_reviewed_at, curve=[],
            )
        return ForgettingCurveResponse(
            word_id=word.id, english=word.english, stability_days=stability,
            last_reviewed_at=word.last_reviewed_at, curve=_points(stability, ref),
        )

    # 汇总：全部已学词的平均稳定度
    words = await stats.fetch_words(db, current_user.id)
    learned = [
        w for w in words
        if (w.repetitions or 0) > 0 and (w.review_interval or 0) > 0 and w.last_reviewed_at
    ]
    if not learned:
        return ForgettingCurveResponse(curve=[])
    ref = datetime.now()
    avg_stability = sum(float(w.review_interval) for w in learned) / len(learned)
    return ForgettingCurveResponse(
        stability_days=round(avg_stability, 2), last_reviewed_at=ref, curve=_points(avg_stability, ref),
    )


@router.get("/mastery", response_model=MasteryResponse)
async def get_word_mastery(
    page: int = 1,
    page_size: int = 20,
    level: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """词级掌握度列表：记忆保持率 + 熟练度，支持按熟练度筛选与分页。"""
    words = await stats.fetch_words(db, current_user.id)
    words = [w for w in words if not level or mastery_level(w.repetitions or 0) == level]

    items = [
        WordMasteryItem(
            word_id=w.id, english=w.english, chinese=w.chinese,
            repetitions=w.repetitions or 0, interval_days=w.review_interval or 0,
            last_reviewed_at=w.last_reviewed_at, next_review_at=w.next_review_at,
            retention=word_retention(w), mastery_level=mastery_level(w.repetitions or 0),
        )
        for w in words
    ]

    total = len(items)
    # 按掌握程度与记忆保持率排序：已掌握优先、保持率低（易遗忘）靠前
    order = {"未学": 0, "新学": 1, "巩固中": 2, "已掌握": 3}
    items.sort(key=lambda it: (order.get(it.mastery_level, 0),
                               it.retention if it.retention is not None else 1.0))
    start = (max(1, page) - 1) * page_size
    return MasteryResponse(total=total, items=items[start:start + page_size])


@router.get("/efficiency", response_model=EfficiencyResponse)
async def get_efficiency(
    span: str = "week",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """阶段学习效率报告：正确率、结果分布、掌握概况、平均保持率、日均作答。"""
    if span not in ("week", "month", "all"):
        raise HTTPException(status_code=400, detail="span 仅支持 week/month/all")

    now = datetime.now()
    start = {
        "week": now - timedelta(days=7),
        "month": now - timedelta(days=30),
        "all": None,
    }[span]

    records = await stats.fetch_records(db, current_user.id, start=start)
    rec_summary = stats.summarize_records(records)

    # 单词掌握与薄弱概况（全量词，不受 span 限制）
    words = await stats.fetch_words(db, current_user.id)
    word_summary = stats.summarize_words(words, now=now)
    weak_ids = await stats.fetch_weak_word_ids(db, current_user.id)
    weak_words = len(weak_ids)

    retentions = [word_retention(w) for w in words]
    retentions = [r for r in retentions if r is not None]
    retention_avg = round(sum(retentions) / len(retentions), 3) if retentions else None

    per_day_avg = round(rec_summary["total_attempts"] / (7 if span == "week" else 30), 2) if span != "all" else 0.0

    return EfficiencyResponse(
        span=span,
        total_attempts=rec_summary["total_attempts"],
        correct_count=rec_summary["correct_count"],
        correct_rate=rec_summary["correct_rate"],
        by_result=rec_summary["by_result"],
        learned_words=word_summary["learned"],
        mastered_words=word_summary["mastered"],
        weak_words=weak_words,
        retention_avg=retention_avg,
        per_day_avg=per_day_avg,
    )