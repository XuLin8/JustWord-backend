from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User, Wordbook, Word as WordModel
from ..schemas import (
    WordbookCreate,
    WordbookUpdate,
    WordbookResponse,
    WordbookStatsResponse,
    WordResponse,
)
from ..deps import get_current_user
from ..routers.words import to_word_response


router = APIRouter()


async def _get_owned_book(db: AsyncSession, user_id: str, book_id: int) -> Wordbook:
    """获取当前用户拥有的单词本，否则 404"""
    res = await db.execute(
        select(Wordbook).where(Wordbook.id == book_id, Wordbook.user_id == user_id)
    )
    book = res.scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="单词本不存在")
    return book


# ============ 创建单词本 ============
@router.post("/", response_model=WordbookResponse, status_code=201)
async def create_wordbook(
    payload: WordbookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="单词本名称不能为空")
    book = Wordbook(user_id=current_user.id, name=name, description=payload.description or "")
    db.add(book)
    await db.commit()
    await db.refresh(book)
    return WordbookResponse(id=book.id, name=book.name, description=book.description or "",
                            word_count=0, created_at=book.created_at)


# ============ 单词本列表（含单词数） ============
@router.get("/", response_model=List[WordbookResponse])
async def list_wordbooks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = await db.execute(
        select(Wordbook, func.count(WordModel.id))
        .outerjoin(WordModel, WordModel.wordbook_id == Wordbook.id)
        .where(Wordbook.user_id == current_user.id)
        .group_by(Wordbook.id)
        .order_by(Wordbook.created_at.desc())
    )
    return [
        WordbookResponse(
            id=book.id, name=book.name,
            description=book.description or "", word_count=count,
            created_at=book.created_at,
        )
        for book, count in rows.all()
    ]




# ============ 单词本学习占比统计 ============
@router.get("/stats", response_model=List[WordbookStatsResponse])
async def get_wordbook_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """各单词本学习进度统计（总词数/已学/已掌握及比率）"""
    rows = await db.execute(
        select(
            Wordbook,
            func.count(WordModel.id).label("total"),
            func.sum(case((WordModel.repetitions > 0, 1), else_=0)).label("learned"),
            func.sum(case((WordModel.repetitions >= 6, 1), else_=0)).label("mastered"),
        )
        .outerjoin(WordModel, WordModel.wordbook_id == Wordbook.id)
        .where(Wordbook.user_id == current_user.id)
        .group_by(Wordbook.id)
        .order_by(Wordbook.created_at.desc())
    )
    result = []
    for book, total, learned, mastered in rows.all():
        total = total or 0
        learned = learned or 0
        mastered = mastered or 0
        result.append(
            WordbookStatsResponse(
                id=book.id,
                name=book.name,
                total=total,
                learned=learned,
                mastered=mastered,
                learned_rate=round(learned / total, 4) if total else 0,
                mastered_rate=round(mastered / total, 4) if total else 0,
            )
        )
    return result

# ============ 单词本详情（含单词列表） ============
@router.get("/{book_id}")
async def get_wordbook(
    book_id: int,
    q: Optional[str] = None,
    limit: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    book = await _get_owned_book(db, current_user.id, book_id)
    stmt = select(WordModel).where(
        WordModel.wordbook_id == book_id, WordModel.user_id == current_user.id
    )
    if q:
        from sqlalchemy import or_
        stmt = stmt.where(
            or_(
                WordModel.english.like(f"%{q.strip()}%"),
                WordModel.chinese.like(f"%{q.strip()}%"),
            )
        )
    if limit:
        stmt = stmt.limit(limit)
    res = await db.execute(stmt)
    words = res.scalars().all()
    return {
        "id": book.id,
        "name": book.name,
        "description": book.description or "",
        "word_count": len(words),
        "words": [to_word_response(w) for w in words],
    }


# ============ 更新单词本 ============
@router.put("/{book_id}", response_model=WordbookResponse)
async def update_wordbook(
    book_id: int,
    payload: WordbookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    book = await _get_owned_book(db, current_user.id, book_id)
    if payload.name is not None and payload.name.strip():
        book.name = payload.name.strip()
    if payload.description is not None:
        book.description = payload.description
    await db.commit()
    await db.refresh(book)
    count = (
        await db.execute(
            select(func.count(WordModel.id)).where(WordModel.wordbook_id == book.id)
        )
    ).scalar() or 0
    return WordbookResponse(id=book.id, name=book.name, description=book.description or "",
                            word_count=count, created_at=book.created_at)


# ============ 删除单词本（其中单词回退为未分组） ============
@router.delete("/{book_id}")
async def delete_wordbook(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    book = await _get_owned_book(db, current_user.id, book_id)
    # 单词解除归属
    await db.execute(
        WordModel.__table__.update()
        .where(WordModel.wordbook_id == book_id)
        .values(wordbook_id=None)
    )
    await db.delete(book)
    await db.commit()
    return {"message": f"单词本 '{book.name}' 已删除"}


# ============ 单词加入本 ============
@router.post("/{book_id}/words/{word_id}", response_model=WordResponse)
async def add_word_to_book(
    book_id: int,
    word_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_book(db, current_user.id, book_id)
    res = await db.execute(
        select(WordModel).where(WordModel.id == word_id, WordModel.user_id == current_user.id)
    )
    word = res.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")
    word.wordbook_id = book_id
    await db.commit()
    await db.refresh(word)
    return to_word_response(word)


# ============ 单词移出本 ============
@router.delete("/{book_id}/words/{word_id}", response_model=WordResponse)
async def remove_word_from_book(
    book_id: int,
    word_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await _get_owned_book(db, current_user.id, book_id)
    res = await db.execute(
        select(WordModel).where(WordModel.id == word_id, WordModel.user_id == current_user.id)
    )
    word = res.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")
    word.wordbook_id = None
    await db.commit()
    await db.refresh(word)
    return to_word_response(word)