import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User, Word as WordModel, WordLibrary, LibraryWord, Wordbook, UserLibrarySubscription
from ..schemas import (
    LibraryResponse,
    LibraryWordResponse,
    LibraryImportRequest,
    LibraryImportResult,
)
from ..deps import get_current_user


router = APIRouter()


def _library_tags(lib) -> List[str]:
    """词库标签：优先取库上配置，否则按名称推断（兼容未回填的数据）。"""
    if getattr(lib, "tags", None):
        return [str(x) for x in lib.tags]
    name = lib.name or ""
    for kw in ("四级", "六级", "考研", "托福", "雅思", "GRE", "高考", "专四", "专八", "商务英语"):
        if kw in name:
            return [kw]
    return []



async def _get_library(db: AsyncSession, lib_id: int) -> WordLibrary:
    res = await db.execute(select(WordLibrary).where(WordLibrary.id == lib_id))
    lib = res.scalar_one_or_none()
    if not lib:
        raise HTTPException(status_code=404, detail="词库不存在")
    return lib


# ============ 词库列表 ============
@router.get("/", response_model=List[LibraryResponse])
async def list_libraries(db: AsyncSession = Depends(get_db)):
    rows = await db.execute(
        select(WordLibrary, func.count(LibraryWord.id))
        .outerjoin(LibraryWord, LibraryWord.library_id == WordLibrary.id)
        .group_by(WordLibrary.id)
        .order_by(WordLibrary.id.asc())
    )
    return [
        LibraryResponse(id=lib.id, name=lib.name,
                        description=lib.description or "", words_count=count,
                        tags=_library_tags(lib))
        for lib, count in rows.all()
    ]


# ============ 已订阅词库（服务端为准，账号级） ============
@router.get("/enrolled")
async def enrolled_libraries(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """返回当前用户已订阅的词库 ID 列表（服务端为唯一事实来源，替代前端本地存储）"""
    rows = await db.execute(
        select(UserLibrarySubscription.library_id)
        .where(UserLibrarySubscription.user_id == current_user.id)
        .order_by(UserLibrarySubscription.created_at.asc())
    )
    return [rid for (rid,) in rows.all()]


# ============ 词库详情（词列表，支持搜索与分页） ============
@router.get("/{lib_id}")
async def get_library_words(
    lib_id: int,
    q: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    lib = await _get_library(db, lib_id)
    stmt = select(LibraryWord).where(LibraryWord.library_id == lib_id)
    if q:
        kw = q.strip()
        stmt = stmt.where(
            (LibraryWord.english.like(f"%{kw}%")) | (LibraryWord.chinese.like(f"%{kw}%"))
        )
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
    rows = (
        await db.execute(stmt.order_by(LibraryWord.english.asc()).offset(offset).limit(limit))
    ).scalars().all()
    return {
        "id": lib.id,
        "name": lib.name,
        "description": lib.description or "",
        "total": total,
        "limit": limit,
        "offset": offset,
        "words": [LibraryWordResponse(id=w.id, english=w.english, chinese=w.chinese,
                                      phonetic=w.phonetic, part_of_speech=w.part_of_speech,
                                      example=w.example,
                                      tags=(w.tags or _library_tags(lib)))
                  for w in rows],
    }


# ============ 导入词库 -> 用户单词本 ============
@router.post("/{lib_id}/import", response_model=LibraryImportResult)
async def import_library(
    lib_id: int,
    payload: LibraryImportRequest = LibraryImportRequest(),  # 可省略 body，默认导入整个词库
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """把词库中的词复制进当前用户的 words（可按 word_ids 选词、可落到某个单词本）"""
    lib = await _get_library(db, lib_id)

    # 记录订阅关系（服务端为准，幂等；新用户订阅即在此落库）
    sub_exists = await db.execute(
        select(UserLibrarySubscription).where(
            UserLibrarySubscription.user_id == current_user.id,
            UserLibrarySubscription.library_id == lib_id,
        )
    )
    if not sub_exists.scalar_one_or_none():
        db.add(UserLibrarySubscription(user_id=current_user.id, library_id=lib_id))

    # 校验目标单词本归属
    wordbook_id = None
    if payload.wordbook_id is not None:
        res = await db.execute(
            select(Wordbook).where(Wordbook.id == payload.wordbook_id,
                                   Wordbook.user_id == current_user.id)
        )
        if not res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="单词本不存在")
        wordbook_id = payload.wordbook_id

    # 取词源
    words_stmt = select(LibraryWord).where(LibraryWord.library_id == lib_id)
    if payload.word_ids:
        words_stmt = words_stmt.where(LibraryWord.id.in_(payload.word_ids))
    lib_words = (await db.execute(words_stmt)).scalars().all()
    # 校验 word_ids 有效性（仅当显式指定时跳过无效项）
    if payload.word_ids:
        lib_words = [w for w in lib_words if w.id in set(payload.word_ids)]

    # 查出用户已有的英文，用于去重
    existing = set(
        (await db.execute(
            select(WordModel.english).where(WordModel.user_id == current_user.id)
        )).scalars().all()
    )

    imported = 0
    skipped_english: List[str] = []
    for lw in lib_words:
        en = lw.english.strip()
        if en in existing:
            skipped_english.append(en)
            continue
        db.add(WordModel(
            id=str(uuid.uuid4()),
            english=en,
            chinese=lw.chinese.strip(),
            phonetic=lw.phonetic,
            part_of_speech=lw.part_of_speech,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            meta_data={"tags": _library_tags(lib)},
            user_id=current_user.id,
            wordbook_id=wordbook_id,
        ))
        existing.add(en)
        imported += 1

    await db.commit()
    return LibraryImportResult(
        library_id=lib.id,
        imported=imported,
        skipped=len(skipped_english),
        skipped_english=skipped_english,
    )


# ============ 取消订阅（仅移除订阅关系，保留已导入单词与学习记录） ============
@router.delete("/{lib_id}/subscribe")
async def unsubscribe_library(
    lib_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(UserLibrarySubscription).where(
            UserLibrarySubscription.user_id == current_user.id,
            UserLibrarySubscription.library_id == lib_id,
        )
    )
    sub = res.scalar_one_or_none()
    if not sub:
        raise HTTPException(status_code=404, detail="未订阅该词库")
    await db.delete(sub)
    await db.commit()
    return {"unsubscribed": True, "library_id": lib_id}
