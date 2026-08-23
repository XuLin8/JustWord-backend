"""数据导出 / 进度备份。

- 全量 JSON 备份：单词、单词本、学习记录、错题、打卡
- 个人词汇表 CSV 导出（Excel 可直接打开）
- 合并式恢复：不覆盖现有进度，仅补入缺失的单词/错题/打卡/单词本
"""
import csv
import io
import uuid
from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User, Word as WordModel, Wordbook, WrongWord, Checkin, LearningRecord
from ..deps import get_current_user
from ..schemas import RestoreResponse


router = APIRouter()


# ============ 序列化辅助 ============
def _dt(dt) -> Optional[str]:
    return dt.isoformat() if dt else None


def _parse_dt(value):
    """把备份里的 ISO 字符串解析成 datetime；解析失败返回默认值"""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


# ============ 全量 JSON 备份 ============
@router.get("/backup")
async def export_backup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出一份当前用户的完整进度的 JSON 备份。"""
    # 单词本：名称 + 描述 + 词表
    book_res = await db.execute(
        select(Wordbook).where(Wordbook.user_id == current_user.id)
    )
    books = book_res.scalars().all()
    book_map = {b.id: b for b in books}
    wordbooks = [
        {
            "name": b.name,
            "description": b.description or "",
            "created_at": _dt(b.created_at),
            "words": [],
        }
        for b in books
    ]
    book_index = {b.id: idx for idx, b in enumerate(books)}

    # 单词
    word_res = await db.execute(
        select(WordModel).where(WordModel.user_id == current_user.id)
    )
    words = []
    for w in word_res.scalars().all():
        item = {
            "english": w.english,
            "chinese": w.chinese,
            "ef": w.ef,
            "review_interval": w.review_interval,
            "repetitions": w.repetitions,
            "next_review_at": _dt(w.next_review_at),
            "last_reviewed_at": _dt(w.last_reviewed_at),
            "meta_data": w.meta_data or {},
            "created_at": _dt(w.created_at),
            "wordbook": book_map[w.wordbook_id].name if w.wordbook_id in book_map else None,
        }
        words.append(item)
        if w.wordbook_id in book_index:
            wordbooks[book_index[w.wordbook_id]]["words"].append(w.english)

    # 学习记录
    rec_res = await db.execute(
        select(LearningRecord, WordModel.english, WordModel.chinese)
        .outerjoin(WordModel, WordModel.id == LearningRecord.word_id)
        .where(LearningRecord.user_id == current_user.id)
        .order_by(LearningRecord.created_at.asc())
    )
    learning_records = [
        {
            "word": english or "",
            "chinese": chinese or "",
            "mode": r.mode,
            "user_answer": r.user_answer,
            "correct_answer": r.correct_answer,
            "result": r.result,
            "score": r.score,
            "feedback": r.feedback,
            "created_at": _dt(r.created_at),
        }
        for r, english, chinese in rec_res.all()
    ]

    # 错题本（关联 word 取英文）
    wrong_res = await db.execute(
        select(WrongWord, WordModel.english)
        .outerjoin(WordModel, WordModel.id == WrongWord.word_id)
        .where(WrongWord.user_id == current_user.id)
        .order_by(WrongWord.created_at.desc())
    )
    wrong_words = [
        {
            "word": english or "",
            "wrong_count": w.wrong_count,
            "status": w.status,
            "last_wrong_at": _dt(w.last_wrong_at),
            "created_at": _dt(w.created_at),
        }
        for w, english in wrong_res.all()
    ]

    # 打卡记录
    ck_res = await db.execute(
        select(Checkin.date)
        .where(Checkin.user_id == current_user.id)
        .order_by(Checkin.date.asc())
    )
    checkins = [d.isoformat() for (d,) in ck_res.all()]

    return {
        "version": "1.0",
        "exported_at": datetime.utcnow().isoformat(),
        "user": {"id": current_user.id, "username": current_user.username, "email": current_user.email},
        "wordbooks": wordbooks,
        "words": words,
        "learning_records": learning_records,
        "wrong_words": wrong_words,
        "checkins": checkins,
    }


# ============ 词汇表 CSV 导出 ============
@router.get("/vocab.csv")
async def export_vocab_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """导出当前用户的词汇表为 CSV（含间隔重复状态，Excel 可直接打开）。"""
    book_res = await db.execute(
        select(Wordbook).where(Wordbook.user_id == current_user.id)
    )
    book_map = {b.id: b.name for b in (book_res.scalars().all() or [])}

    word_res = await db.execute(
        select(WordModel).where(WordModel.user_id == current_user.id)
    )
    words = word_res.scalars().all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["english", "chinese", "wordbook", "ef", "interval_days",
                     "repetitions", "next_review_at", "last_reviewed_at", "created_at"])
    for w in words:
        writer.writerow([
            w.english,
            w.chinese,
            book_map.get(w.wordbook_id, ""),
            w.ef,
            w.review_interval,
            w.repetitions,
            w.next_review_at.isoformat() if w.next_review_at else "",
            w.last_reviewed_at.isoformat() if w.last_reviewed_at else "",
            w.created_at.isoformat() if w.created_at else "",
        ])
    data = "\ufeff" + buf.getvalue()  # BOM，便于 Excel 识别 UTF-8
    return Response(
        content=data.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="vocab_{current_user.username}.csv"'},
    )


# ============ 合并式恢复 ============
@router.post("/restore", response_model=RestoreResponse)
async def restore_backup(
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """从备份 JSON 合并恢复。

    仅补入缺失内容、不改写现有进度：
    - 单词本：按名称创建缺失的单词本
    - 单词：英文不存在则新建（保留备份中的间隔重复状态与归属）
    - 错题：该词尚未计入错题则补建一条
    - 打卡：仅补入缺失的日期
    """
    # 现有单词（按英文）
    exist_res = await db.execute(
        select(WordModel).where(WordModel.user_id == current_user.id)
    )
    words_exist = {w.english.lower(): w for w in exist_res.scalars().all()}

    # 现有单词本映射（新增的用新 ID 记录）
    book_res = await db.execute(
        select(Wordbook.name, Wordbook.id).where(Wordbook.user_id == current_user.id)
    )
    books = {name: bid for name, bid in book_res.all()}
    new_book_ids = {}  # 本次新建的 name -> id

    async def _get_book_id(name: str) -> Optional[int]:
        """按名称返回单词本 ID；不存在则新建。"""
        if not name:
            return None
        if name in books:
            return books[name]
        if name in new_book_ids:
            return new_book_ids[name]
        nb = Wordbook(user_id=current_user.id, name=name, description="")
        db.add(nb)
        await db.flush()
        new_book_ids[name] = nb.id
        return nb.id

    added_words = 0
    added_wrong = 0
    added_checkins = 0

    # 单词
    for witem in (payload.get("words") or []):
        english = (witem.get("english") or "").strip()
        if not english:
            continue
        chinese = (witem.get("chinese") or "").strip()
        if english.lower() in words_exist:
            continue  # 已存在，保留现有进度
        book_id = await _get_book_id(witem.get("wordbook"))
        new_word = WordModel(
            id=str(uuid.uuid4()),
            english=english,
            chinese=chinese or english,
            user_id=current_user.id,
            meta_data=witem.get("meta_data") or {},
            wordbook_id=book_id,
            ef=witem.get("ef", 2.5),
            review_interval=witem.get("review_interval", 0),
            repetitions=witem.get("repetitions", 0),
            next_review_at=_parse_dt(witem.get("next_review_at")) or datetime.utcnow(),
            last_reviewed_at=_parse_dt(witem.get("last_reviewed_at")),
            created_at=_parse_dt(witem.get("created_at")) or datetime.utcnow(),
        )
        db.add(new_word)
        words_exist[english.lower()] = new_word
        added_words += 1

    # 错题
    for wi in (payload.get("wrong_words") or []):
        word_key = (wi.get("word") or "").strip().lower()
        if not word_key or word_key not in words_exist:
            continue
        w = words_exist[word_key]
        dup_res = await db.execute(
            select(WrongWord.id).where(
                WrongWord.user_id == current_user.id,
                WrongWord.word_id == w.id,
            )
        )
        if dup_res.scalar_one_or_none():
            continue  # 已计入
        db.add(WrongWord(
            user_id=current_user.id,
            word_id=w.id,
            wrong_count=wi.get("wrong_count", 1),
            last_wrong_at=_parse_dt(wi.get("last_wrong_at")) or datetime.utcnow(),
            status=wi.get("status", "open"),
            created_at=_parse_dt(wi.get("created_at")) or datetime.utcnow(),
        ))
        added_wrong += 1

    # 打卡
    for dstr in (payload.get("checkins") or []):
        try:
            d = date.fromisoformat(dstr)
        except (ValueError, TypeError):
            continue
        dup_res = await db.execute(
            select(Checkin.id).where(
                Checkin.user_id == current_user.id,
                Checkin.date == d,
            )
        )
        if dup_res.scalar_one_or_none():
            continue  # 已打卡
        db.add(Checkin(user_id=current_user.id, date=d))
        added_checkins += 1

    await db.commit()

    return RestoreResponse(
        added_words=added_words,
        added_wrong_words=added_wrong,
        added_checkins=added_checkins,
        skipped_words=len(payload.get("words") or []) - added_words,
    )