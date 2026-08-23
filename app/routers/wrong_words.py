"""错题 / 薄弱词本。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional
from datetime import datetime, date

from ..database import get_db
from ..models import User, Word as WordModel, WrongWord
from ..schemas import WrongWordResponse, WrongWordSummaryResponse
from ..services.learning_common import local_offset
from ..deps import get_current_user

router = APIRouter()


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
            word_id=ww.word_id, english=en, chinese=zh,
            wrong_count=ww.wrong_count, last_wrong_at=ww.last_wrong_at, status=ww.status,
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
    today_start = datetime.combine(date.today(), datetime.min.time()) - local_offset()

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
                WrongWord.user_id == current_user.id, WrongWord.last_wrong_at >= today_start
            )
        )
    ).scalar_one()
    weak_due = (
        await db.execute(
            select(func.count()).select_from(WrongWord)
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
        select(WrongWord).where(WrongWord.word_id == word_id, WrongWord.user_id == current_user.id)
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
        select(WrongWord).where(WrongWord.word_id == word_id, WrongWord.user_id == current_user.id)
    )
    ww = res.scalar_one_or_none()
    if not ww:
        raise HTTPException(status_code=404, detail="错题记录不存在")
    await db.delete(ww)
    await db.commit()
    return {"message": "已删除", "word_id": word_id}