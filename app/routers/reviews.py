"""间隔重复（SM-2）：复习队列、概览与提交复习。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional
from datetime import datetime

from ..database import get_db
from ..models import LearningRecord, User, Word as WordModel, WrongWord, WordSnapshot
from ..schemas import ReviewSubmit, ReviewSummaryResponse
from ..services.srs import apply_sm2
from ..services.learning_common import to_review_item, local_offset
from ..services import daily_stats
from ..deps import get_current_user

router = APIRouter()


async def _upsert_wrong_word(db: AsyncSession, user_id: str, word: WordModel, result: str) -> None:
    """答错（非 correct）自动计入错题/薄弱词本（同一词累计次数）。"""
    if result == "correct":
        return
    res = await db.execute(
        select(WrongWord).where(WrongWord.user_id == user_id, WrongWord.word_id == word.id)
    )
    ww = res.scalar_one_or_none()
    now = datetime.utcnow()
    if ww:
        ww.wrong_count += 1
        ww.last_wrong_at = now
        ww.status = "open"
    else:
        db.add(WrongWord(user_id=user_id, word_id=word.id, wrong_count=1,
                         last_wrong_at=now, status="open"))


@router.get("/reviews/due")
async def get_due_reviews(
    wordbook_id: Optional[int] = None,
    weak_only: bool = False,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户待复习单词队列。

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
    total = await db.execute(select(func.count()).select_from(WordModel).where(*conds))
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
        select(func.count()).select_from(WordModel)
        .where(WordModel.user_id == current_user.id, due_cond)
    )
    new_w = await db.execute(
        select(func.count()).select_from(WordModel)
        .where(WordModel.user_id == current_user.id, WordModel.repetitions == 0)
    )
    learned = await db.execute(
        select(func.count()).select_from(WordModel)
        .where(WordModel.user_id == current_user.id, learned_cond)
    )
    review = await db.execute(
        select(func.count()).select_from(WordModel)
        .where(
            WordModel.user_id == current_user.id,
            WordModel.next_review_at.is_not(None),
            WordModel.next_review_at <= now,
            WordModel.repetitions > 0,
        )
    )
    return ReviewSummaryResponse(
        due_count=due.scalar_one(),
        new_count=new_w.scalar_one(),
        review_count=review.scalar_one(),
        learned_count=learned.scalar_one(),
    )


@router.post("/reviews")
async def submit_review(
    payload: ReviewSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """提交一次复习结果：应用 SM-2 更新调度，并写入一条学习记录。"""
    result = await db.execute(
        select(WordModel).where(WordModel.id == payload.word_id,
                                WordModel.user_id == current_user.id)
    )
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")

    is_new = (word.repetitions or 0) == 0  # SM-2 应用前判定新学/复习
    schedule = apply_sm2(word, payload.result)
    db.add(word)

    # 同步写入一条学习记录（供统计追溯；mode 传规则标识，result 支持 partial）
    db.add(LearningRecord(
        word_id=word.id,
        user_id=current_user.id,
        mode=payload.mode or "review",
        user_answer=payload.user_answer or "",
        correct_answer=payload.correct_answer or "",
        result=payload.result,
        score=schedule["quality"],
        response_ms=payload.response_ms,
        feedback=payload.feedback,
        is_new=is_new,
    ))

    # SM-2 调度历史快照（记忆曲线真实演变数据源）
    db.add(WordSnapshot(
        user_id=current_user.id,
        word_id=word.id,
        repetitions=schedule["repetitions"],
        interval_days=schedule["interval_days"],
        ef=schedule["easiness_factor"],
        next_review_at=schedule["next_review_at"],
    ))

    # 答错自动计入错题本
    await _upsert_wrong_word(db, current_user.id, word, payload.result)

    # 懒聚合：提交后回填当日 DailyStat
    offset = local_offset()
    await daily_stats.recompute_day(db, current_user.id, daily_stats.current_learning_date(offset), offset)

    await db.commit()
    await db.refresh(word)
    return {"word_id": word.id, **schedule}