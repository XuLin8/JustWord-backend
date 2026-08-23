from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, or_
import math
from typing import Optional
from datetime import datetime, date, timedelta

from ..database import get_db
from ..models import LearningRecord, User, Word as WordModel, Checkin, WrongWord
from ..schemas import (
    LearningRecordCreate,
    LearningRecordResponse,
    LearningStatsResponse,
    ReviewSubmit,
    ReviewSummaryResponse,
    CheckinStatusResponse,
    DashboardResponse,
    DashboardWordStats,
    DashboardLearningStats,
    DashboardDailyTrend,
    WrongWordResponse,
    WrongWordSummaryResponse,
    ForgettingCurveResponse,
    ForgettingPoint,
    WordMasteryItem,
    MasteryResponse,
    EfficiencyResponse,
)
from ..services.srs import apply_sm2
from ..routers.auth import get_current_user

router = APIRouter()


def _local_offset() -> timedelta:
    """本机时区相对 UTC 的偏移（学习记录 created_at 存 UTC）"""
    return datetime.now() - datetime.utcnow()


def to_record_response(r: LearningRecord) -> LearningRecordResponse:
    return LearningRecordResponse(
        id=r.id,
        word_id=r.word_id,
        user_id=r.user_id,
        mode=r.mode,
        user_answer=r.user_answer,
        correct_answer=r.correct_answer,
        result=r.result,
        score=r.score,
        feedback=r.feedback,
        created_at=r.created_at,
    )


@router.post("/records", response_model=LearningRecordResponse, status_code=201)
async def create_learning_record(
    record: LearningRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存学习记录（写入数据库，绑定当前用户）"""
    new_record = LearningRecord(
        word_id=record.word_id,
        user_id=current_user.id,
        mode=record.mode,
        user_answer=record.user_answer,
        correct_answer=record.correct_answer,
        result=record.result,
        score=record.score,
        feedback=record.feedback,
    )
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)
    return to_record_response(new_record)


@router.get("/records", response_model=dict)
async def get_learning_records(
    limit: int = 50,
    offset: int = 0,
    word_id: Optional[str] = None,
    mode: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的学习记录列表"""
    stmt = select(LearningRecord).where(LearningRecord.user_id == current_user.id)
    if word_id:
        stmt = stmt.where(LearningRecord.word_id == word_id)
    if mode:
        stmt = stmt.where(LearningRecord.mode == mode)
    stmt = stmt.order_by(LearningRecord.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    records = result.scalars().all()

    total = await db.execute(
        select(func.count()).select_from(LearningRecord).where(LearningRecord.user_id == current_user.id)
        .where(LearningRecord.word_id == word_id if word_id else True)
        .where(LearningRecord.mode == mode if mode else True)
    )
    total_count = total.scalar_one()

    return {
        "items": [to_record_response(r) for r in records],
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/stats", response_model=LearningStatsResponse)
async def get_learning_stats(
    word_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的学习统计"""
    stmt = select(LearningRecord).where(LearningRecord.user_id == current_user.id)
    if word_id:
        stmt = stmt.where(LearningRecord.word_id == word_id)

    result = await db.execute(stmt)
    records = result.scalars().all()

    total = len(records)
    correct = len([r for r in records if r.result == "correct"])

    word_stats = {}
    for r in records:
        stats = word_stats.setdefault(r.word_id, {"total": 0, "correct": 0})
        stats["total"] += 1
        if r.result == "correct":
            stats["correct"] += 1

    word_stats_list = [
        {
            "word_id": wid,
            "total": s["total"],
            "correct": s["correct"],
            "rate": s["correct"] / s["total"] if s["total"] > 0 else 0,
        }
        for wid, s in word_stats.items()
    ]

    return LearningStatsResponse(
        total_attempts=total,
        correct_count=correct,
        correct_rate=correct / total if total > 0 else 0,
        word_stats=word_stats_list,
    )


@router.delete("/records")
async def clear_learning_records(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清空当前用户的学习记录"""
    result = await db.execute(
        delete(LearningRecord).where(LearningRecord.user_id == current_user.id)
    )
    await db.commit()
    return {"message": f"已删除 {result.rowcount} 条学习记录"}


# ============ 间隔重复（SM-2） ============

def to_review_item(word: WordModel) -> dict:
    """将单词转为复习队列条目"""
    return {
        "id": word.id,
        "english": word.english,
        "chinese": word.chinese,
        "meta_data": word.meta_data or {},
        "repetitions": word.repetitions or 0,
        "interval_days": word.review_interval or 0,
        "next_review_at": word.next_review_at,
    }


@router.get("/reviews/due")
async def get_due_reviews(
    wordbook_id: Optional[int] = None,
    weak_only: bool = False,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户待复习单词队列

    可按单词本(wordbook_id)筛选；weak_only=True 仅返回待巩固的错题/薄弱词。
    NULL/已到期的按到期优先排序。
    """
    now = datetime.now()
    conds = (
        WordModel.user_id == current_user.id,
        or_(WordModel.next_review_at.is_(None), WordModel.next_review_at <= now),
    )
    if wordbook_id is not None:
        conds = conds + (WordModel.wordbook_id == wordbook_id,)
    if weak_only:
        conds = conds + (
            WordModel.id.in_(
                select(WrongWord.word_id).where(
                    WrongWord.user_id == current_user.id,
                    WrongWord.status == "open",
                )
            ),
        )
    base = (
        select(WordModel)
        .where(*conds)
        .order_by(WordModel.next_review_at.asc())
    )
    total = await db.execute(
        select(func.count()).select_from(WordModel).where(*conds)
    )
    result = await db.execute(base.offset(offset).limit(limit))
    words = result.scalars().all()

    return {
        "items": [to_review_item(w) for w in words],
        "total": total.scalar_one(),
        "limit": limit,
        "offset": offset,
    }


@router.get("/reviews/summary", response_model=ReviewSummaryResponse)
async def get_review_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取复习概览：待复习/新词/复习词/已学数量"""
    now = datetime.now()
    due_cond = or_(WordModel.next_review_at.is_(None), WordModel.next_review_at <= now)
    learned_cond = WordModel.repetitions > 0

    due = await db.execute(
        select(func.count())
        .select_from(WordModel)
        .where(WordModel.user_id == current_user.id, due_cond)
    )
    new_w = await db.execute(
        select(func.count())
        .select_from(WordModel)
        .where(WordModel.user_id == current_user.id, WordModel.repetitions == 0)
    )
    learned = await db.execute(
        select(func.count())
        .select_from(WordModel)
        .where(WordModel.user_id == current_user.id, learned_cond)
    )
    review = await db.execute(
        select(func.count())
        .select_from(WordModel)
        .where(
            WordModel.user_id == current_user.id,
            WordModel.next_review_at.is_not(None),
            WordModel.next_review_at <= now,
            WordModel.repetitions > 0,
        )
    )
    due_count = due.scalar_one()
    new_count = new_w.scalar_one()
    learned_count = learned.scalar_one()
    review_count = review.scalar_one()

    return ReviewSummaryResponse(
        due_count=due_count,
        new_count=new_count,
        review_count=review_count,
        learned_count=learned_count,
    )


@router.post("/reviews")
async def submit_review(
    payload: ReviewSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交一次复习结果：应用 SM-2 更新调度，并写入一条学习记录"""
    result = await db.execute(
        select(WordModel).where(
            WordModel.id == payload.word_id,
            WordModel.user_id == current_user.id,
        )
    )
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")

    schedule = apply_sm2(word, payload.result)
    db.add(word)

    # 同步写入一条学习记录（供统计追溯）
    record = LearningRecord(
        word_id=word.id,
        user_id=current_user.id,
        mode=payload.mode or "review",
        user_answer=payload.user_answer or "",
        correct_answer=payload.correct_answer or "",
        result=payload.result,
        score=schedule["quality"],
        feedback=payload.feedback,
    )
    db.add(record)

    # 答错（非 correct）自动计入错题/薄弱词本（同一词累计次数）
    if payload.result != "correct":
        ww_res = await db.execute(
            select(WrongWord).where(
                WrongWord.user_id == current_user.id,
                WrongWord.word_id == word.id,
            )
        )
        ww = ww_res.scalar_one_or_none()
        if ww:
            ww.wrong_count += 1
            ww.last_wrong_at = datetime.utcnow()
            ww.status = "open"
        else:
            db.add(WrongWord(
                user_id=current_user.id,
                word_id=word.id,
                wrong_count=1,
                last_wrong_at=datetime.utcnow(),
                status="open",
            ))

    await db.commit()
    await db.refresh(word)

    return {"word_id": word.id, **schedule}


# ============ 错题 / 薄弱词本 ============

@router.get("/wrong-words", response_model=dict)
async def list_wrong_words(
    status: Optional[str] = "open",
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """错题/薄弱词列表（默认待巩固，时间倒序，附单词信息）"""
    conds = [WrongWord.user_id == current_user.id]
    if status:
        if status not in ("open", "resolved"):
            raise HTTPException(status_code=400, detail="status 仅支持 open/resolved")
        conds.append(WrongWord.status == status)

    page = max(1, page)
    page_size = max(1, min(page_size, 100))
    total = (
        await db.execute(select(func.count()).select_from(WrongWord).where(*conds))
    ).scalar_one()

    rows = (
        await db.execute(
            select(WrongWord, WordModel.english, WordModel.chinese)
            .join(WordModel, WordModel.id == WrongWord.word_id)
            .where(*conds)
            .order_by(WrongWord.last_wrong_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    items = [
        WrongWordResponse(
            word_id=ww.word_id,
            english=en,
            chinese=zh,
            wrong_count=ww.wrong_count,
            last_wrong_at=ww.last_wrong_at,
            status=ww.status,
        )
        for ww, en, zh in rows
    ]
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/wrong-words/summary", response_model=WrongWordSummaryResponse)
async def wrong_words_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """错题汇总：待巩固数 / 今日新增答错 / 错题中今日待复习数"""
    now = datetime.now()
    today_start = (datetime.combine(date.today(), datetime.min.time()) - _local_offset())

    open_count = (
        await db.execute(
            select(func.count()).select_from(WrongWord).where(
                WrongWord.user_id == current_user.id, WrongWord.status == "open"
            )
        )
    ).scalar_one()

    today_wrong = (
        await db.execute(
            select(func.count()).select_from(WrongWord).where(
                WrongWord.user_id == current_user.id,
                WrongWord.last_wrong_at >= today_start,
            )
        )
    ).scalar_one()

    weak_due = (
        await db.execute(
            select(func.count())
            .select_from(WrongWord)
            .join(WordModel, WordModel.id == WrongWord.word_id)
            .where(
                WrongWord.user_id == current_user.id,
                WrongWord.status == "open",
                or_(WordModel.next_review_at.is_(None), WordModel.next_review_at <= now),
            )
        )
    ).scalar_one()

    return WrongWordSummaryResponse(
        open_count=open_count, today_wrong_count=today_wrong, weak_due_count=weak_due
    )


@router.post("/wrong-words/{word_id}/resolve")
async def resolve_wrong_word(
    word_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """把某错题标记为已解决（移出待巩固）"""
    res = await db.execute(
        select(WrongWord).where(
            WrongWord.word_id == word_id, WrongWord.user_id == current_user.id
        )
    )
    ww = res.scalar_one_or_none()
    if not ww:
        raise HTTPException(status_code=404, detail="错题记录不存在")
    ww.status = "resolved"
    await db.commit()
    return {"message": "已标记为已解决", "word_id": word_id, "status": "resolved"}


@router.delete("/wrong-words/{word_id}")
async def delete_wrong_word(
    word_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """删除错题记录（彻底移除出错题本）"""
    res = await db.execute(
        select(WrongWord).where(
            WrongWord.word_id == word_id, WrongWord.user_id == current_user.id
        )
    )
    ww = res.scalar_one_or_none()
    if not ww:
        raise HTTPException(status_code=404, detail="错题记录不存在")
    await db.delete(ww)
    await db.commit()
    return {"message": "已删除", "word_id": word_id}


# ============ 打卡 / 连续天数 ============

def compute_streaks(dates: set) -> tuple:
    """根据打卡日期集合，返回 (当前连续天数, 最大连续天数)。
    当前连续天数：若今天已打卡则从今天往前数，否则从昨天往前数。"""
    if not dates:
        return 0, 0

    today = date.today()
    current = 0
    d = today
    if d not in dates:
        d = today - timedelta(days=1)
    while d in dates:
        current += 1
        d -= timedelta(days=1)

    max_streak = 0
    run = 0
    prev = None
    for d in sorted(dates):
        if prev is not None and (d - prev).days == 1:
            run += 1
        else:
            run = 1
        max_streak = max(max_streak, run)
        prev = d

    return current, max_streak


async def _get_checkin_dates(db: AsyncSession, user_id: str) -> set:
    result = await db.execute(
        select(Checkin.date).where(Checkin.user_id == user_id)
    )
    return set(result.scalars().all())


@router.get("/checkin/status", response_model=CheckinStatusResponse)
async def get_checkin_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取打卡状态：今日是否已打卡、当前/最大连续天数、累计天数"""
    dates = await _get_checkin_dates(db, current_user.id)
    current, max_streak = compute_streaks(dates)
    total = len(dates)
    last = max(dates) if dates else None
    return CheckinStatusResponse(
        checked_today=date.today() in dates,
        current_streak=current,
        max_streak=max_streak,
        total_days=total,
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


# ============ 学习统计看板 ============

def _mastery_bucket(reps: int) -> dict:
    if reps >= 6:
        return {"label": "已掌握", "count": 0}
    if reps >= 3:
        return {"label": "巩固中", "count": 0}
    if reps >= 1:
        return {"label": "新学", "count": 0}
    return {"label": "未学", "count": 0}


def _build_daily_trend(
    records, days: int, local_offset: timedelta, end: date
) -> List[DashboardDailyTrend]:
    """构建近 `days` 天每日学习趋势，保证输出连续日期序列（含 `end`）。

    细化工项：
      - 天数钳制到 [1, 365]，避免异常入参；
      - 每个窗口日期都预先置零，无数据的天自动补零（attempts/correct/rate=0）；
      - 仅统计窗口内的记录（created_at 为 UTC，先按 local_offset 换算成环境本地日期）；
      - dict 按插入顺序即日期升序，天然保证返回按时序排列。
    """
    days = max(1, min(days, 365))
    day_map = {}
    for i in range(days - 1, -1, -1):
        d = end - timedelta(days=i)
        day_map[d] = {"attempts": 0, "correct": 0}

    for r in records:
        d = (r.created_at + local_offset).date() if r.created_at else end
        if d in day_map:
            day_map[d]["attempts"] += 1
            if r.result == "correct":
                day_map[d]["correct"] += 1

    return [
        DashboardDailyTrend(
            date=d,
            attempts=agg["attempts"],
            correct=agg["correct"],
            correct_rate=agg["correct"] / agg["attempts"] if agg["attempts"] > 0 else 0.0,
        )
        for d, agg in day_map.items()
    ]


@router.get("/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    trend_days: int = 7,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """学习统计看板：单词掌握概况、SRS 熟练度分布、练习正确率、近 N 天趋势、打卡统计"""
    now = datetime.now()

    # ---- 单词概况 & 熟练度分布 ----
    words_res = await db.execute(
        select(WordModel).where(WordModel.user_id == current_user.id)
    )
    words = words_res.scalars().all()
    total_words = len(words)
    learned_words = sum(1 for w in words if (w.repetitions or 0) > 0)
    mastered_words = sum(1 for w in words if (w.repetitions or 0) >= 6)

    bucket_map = {"未学": 0, "新学": 0, "巩固中": 0, "已掌握": 0}
    for w in words:
        bucket_map[_mastery_bucket(w.repetitions or 0)["label"]] += 1
    distribution = [{"label": k, "count": v} for k, v in bucket_map.items()]

    new_words_due = sum(1 for w in words if (w.repetitions or 0) == 0)
    review_words_due = sum(
        1
        for w in words
        if (w.repetitions or 0) > 0
        and w.next_review_at is not None
        and w.next_review_at <= now
    )

    # ---- 学习记录统计 & 近 N 天趋势 ----
    rec_res = await db.execute(
        select(LearningRecord).where(LearningRecord.user_id == current_user.id)
    )
    records = rec_res.scalars().all()
    attempts = len(records)
    correct_count = sum(1 for r in records if r.result == "correct")

    by_result_map = {"correct": 0, "partial": 0, "close": 0, "wrong": 0}
    for r in records:
        by_result_map[r.result] = by_result_map.get(r.result, 0) + 1
    by_result = [{"result": k, "count": v} for k, v in by_result_map.items()]

    # 近 N 天每日趋势（无数据的天自动补零，见 _build_daily_trend）
    local_offset = _local_offset()
    daily_trend = _build_daily_trend(records, trend_days, local_offset, date.today())

    # ---- 打卡统计 ----
    checkin_dates = await _get_checkin_dates(db, current_user.id)
    current, max_streak = compute_streaks(checkin_dates)

    word_stats = DashboardWordStats(
        total=total_words,
        learned=learned_words,
        mastered=mastered_words,
        new_words_due=new_words_due,
        review_words_due=review_words_due,
        distribution=distribution,
    )
    learning_stats = DashboardLearningStats(
        total_attempts=attempts,
        correct_count=correct_count,
        correct_rate=correct_count / attempts if attempts > 0 else 0,
        by_result=by_result,
    )
    return DashboardResponse(
        word_stats=word_stats,
        learning_stats=learning_stats,
        daily_trend=daily_trend,
        checkin_stats={
            "current_streak": current,
            "max_streak": max_streak,
            "total_days": len(checkin_dates),
            "last_checkin_date": max(checkin_dates) if checkin_dates else None,
        },
    )


# ============ 遗忘曲线 / 效率分析 ============

def _word_retention(word: WordModel, at: Optional[datetime] = None) -> Optional[float]:
    """按 Ebbinghaus 指数衰减模型估算某词的当前记忆保持率。

    以 SM-2 复习间隔天数作为记忆稳定度 S，从 last_reviewed_at 起随时间衰减：
    R(t) = exp(-t / S)。未学过或尚未定间隔的词返回 None（无法评估）。
    """
    if (word.repetitions or 0) <= 0 or (word.review_interval or 0) <= 0 or not word.last_reviewed_at:
        return None
    at = at or datetime.now()
    t_days = (at - word.last_reviewed_at).total_seconds() / 86400.0
    stability = max(float(word.review_interval), 0.5)
    r = math.exp(-max(t_days, 0.0) / stability)
    return round(min(max(r, 0.0), 1.0), 3)


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

    def _points(stability: float):
        pts = []
        for i in range(days):
            d = today + timedelta(days=i)
            t = (datetime.combine(d, datetime.min.time()) - word_datetime).total_seconds() / 86400.0
            r = math.exp(-max(t, 0.0) / max(stability, 0.5))
            pts.append(ForgettingPoint(date=d, retention=round(min(max(r, 0.0), 1.0), 3)))
        return pts

    if word_id:
        res = await db.execute(
            select(WordModel).where(
                WordModel.id == word_id, WordModel.user_id == current_user.id
            )
        )
        word = res.scalar_one_or_none()
        if not word:
            raise HTTPException(status_code=404, detail="单词不存在")
        word_datetime = word.last_reviewed_at or datetime.now()
        stability = float(word.review_interval or 0)
        if (word.repetitions or 0) <= 0 or stability <= 0:
            return ForgettingCurveResponse(
                word_id=word.id, english=word.english, stability_days=None,
                last_reviewed_at=word.last_reviewed_at, curve=[],
            )
        return ForgettingCurveResponse(
            word_id=word.id,
            english=word.english,
            stability_days=stability,
            last_reviewed_at=word.last_reviewed_at,
            curve=_points(stability),
        )

    # 汇总：全部已学词的平均稳定度
    words_res = await db.execute(
        select(WordModel).where(WordModel.user_id == current_user.id)
    )
    learned = [
        w for w in words_res.scalars().all()
        if (w.repetitions or 0) > 0 and (w.review_interval or 0) > 0 and w.last_reviewed_at
    ]
    if not learned:
        return ForgettingCurveResponse(curve=[])
    word_datetime = datetime.now()
    avg_stability = sum(float(w.review_interval) for w in learned) / len(learned)
    return ForgettingCurveResponse(
        stability_days=round(avg_stability, 2), last_reviewed_at=word_datetime, curve=_points(avg_stability),
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
    words_res = await db.execute(
        select(WordModel).where(WordModel.user_id == current_user.id)
    )
    words = [w for w in words_res.scalars().all() if not level or _mastery_bucket(w.repetitions or 0)["label"] == level]

    items = []
    for w in words:
        items.append(WordMasteryItem(
            word_id=w.id,
            english=w.english,
            chinese=w.chinese,
            repetitions=w.repetitions or 0,
            interval_days=w.review_interval or 0,
            last_reviewed_at=w.last_reviewed_at,
            next_review_at=w.next_review_at,
            retention=_word_retention(w),
            mastery_level=_mastery_bucket(w.repetitions or 0)["label"],
        ))

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

    # 记录统计（只取当前阶段内）
    rec_q = select(LearningRecord).where(LearningRecord.user_id == current_user.id)
    if start:
        rec_q = rec_q.where(LearningRecord.created_at >= start)
    rec_res = await db.execute(rec_q)
    records = rec_res.scalars().all()
    attempts = len(records)
    correct_count = sum(1 for r in records if r.result == "correct")
    by_result_map = {"correct": 0, "partial": 0, "close": 0, "wrong": 0}
    for r in records:
        by_result_map[r.result] = by_result_map.get(r.result, 0) + 1
    by_result = [{"result": k, "count": v} for k, v in by_result_map.items()]

    # 单词掌握与薄弱概况（全量词，不受 span 限制）
    words_res = await db.execute(
        select(WordModel).where(WordModel.user_id == current_user.id)
    )
    words = words_res.scalars().all()
    learned_words = sum(1 for w in words if (w.repetitions or 0) > 0)
    mastered_words = sum(1 for w in words if (w.repetitions or 0) >= 6)
    weak_ids = set()
    weak_res = await db.execute(
        select(WrongWord.word_id).where(
            WrongWord.user_id == current_user.id, WrongWord.status == "open"
        )
    )
    weak_ids = set(weak_res.scalars().all())
    weak_words = len(weak_ids)

    # 平均记忆保持率（已学且可评估的词）
    retentions = [_word_retention(w) for w in words]
    retentions = [r for r in retentions if r is not None]
    retention_avg = round(sum(retentions) / len(retentions), 3) if retentions else None

    per_day_avg = round(attempts / (7 if span == "week" else 30), 2) if span != "all" else 0.0

    return EfficiencyResponse(
        span=span,
        total_attempts=attempts,
        correct_count=correct_count,
        correct_rate=correct_count / attempts if attempts > 0 else 0,
        by_result=by_result,
        learned_words=learned_words,
        mastered_words=mastered_words,
        weak_words=weak_words,
        retention_avg=retention_avg,
        per_day_avg=per_day_avg,
    )