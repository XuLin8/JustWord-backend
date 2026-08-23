from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from datetime import datetime
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, or_
from ..database import get_db
from ..models import Word as WordModel
from ..models import User
from ..schemas import WordCreate, WordUpdate, WordResponse
from ..deps import get_current_user


router = APIRouter()

# ============ 辅助函数 ============
def to_word_response(word: WordModel) -> WordResponse:
    """将 SQLAlchemy 模型转换为 Pydantic 响应模型"""
    return WordResponse(
        id=word.id,
        english=word.english,
        chinese=word.chinese,
        phonetic=word.phonetic,
        part_of_speech=word.part_of_speech,
        created_at=word.created_at,
        updated_at=word.updated_at,
        meta_data=word.meta_data or {},
        wordbook_id=word.wordbook_id
    )


# ============ API 端点 ============

# ============ GET 所有单词 ============
@router.get("/", response_model=List[WordResponse])
async def get_words(
    q: Optional[str] = None,
    wordbook_id: Optional[int] = None,
    limit: Optional[int] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户单词列表（支持关键词搜索、按单词本筛选与可选数量限制）"""
    stmt = select(WordModel).where(WordModel.user_id == current_user.id)
    if wordbook_id is not None:
        stmt = stmt.where(WordModel.wordbook_id == wordbook_id)
    if q:
        stmt = stmt.where(
            or_(
                WordModel.english.like(f"%{q.strip()}%"),
                WordModel.chinese.like(f"%{q.strip()}%"),
            )
        )
    stmt = stmt.order_by(WordModel.created_at.desc())
    if limit:
        stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    words = result.scalars().all()
    return [to_word_response(w) for w in words]

# ============ POST 创建单词 ============
@router.post("/", response_model=WordResponse, status_code=201)
async def create_word(word: WordCreate, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """创建新单词（绑定当前用户）"""
    # 检查是否已存在相同英文单词
    result = await db.execute(
        select(WordModel).where(
            WordModel.english == word.english.strip(),
            WordModel.user_id == current_user.id
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"单词 '{word.english}' 已存在")

    # 校验单词本归属（若指定）
    if word.wordbook_id is not None:
        from ..models import Wordbook
        book_res = await db.execute(
            select(Wordbook).where(Wordbook.id == word.wordbook_id, Wordbook.user_id == current_user.id)
        )
        if not book_res.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="单词本不存在")
    
    # 创建新单词
    new_word = WordModel(
        id=str(uuid.uuid4()),
        english=word.english.strip(),
        chinese=word.chinese.strip(),
        phonetic=word.phonetic.strip() if word.phonetic else None,
        part_of_speech=word.part_of_speech.strip() if word.part_of_speech else None,
        created_at=datetime.now(),
        updated_at=datetime.now(),
        meta_data=word.meta_data or {},
        user_id=current_user.id,
        wordbook_id=word.wordbook_id
    )
    db.add(new_word)
    await db.commit()
    await db.refresh(new_word)
    
    return to_word_response(new_word)

# ============ GET 单个单词 ============
@router.get("/{word_id}", response_model=WordResponse)
async def get_word(word_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """根据 ID 获取单个单词"""
    result = await db.execute(select(WordModel).where(
        WordModel.id == word_id,
        WordModel.user_id == current_user.id
    ))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")
    return to_word_response(word)

# ============ PUT 更新单词 ============
@router.put("/{word_id}", response_model=WordResponse)
async def update_word(
    word_id: str, 
    word_update: WordUpdate, 
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """更新当前用户单词信息"""
    result = await db.execute(select(WordModel).where(
        WordModel.id == word_id,
        WordModel.user_id == current_user.id
    ))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")
    
    if word_update.english is not None:
        # 检查英文是否与其他单词重复（当前用户的词库中）
        result = await db.execute(
            select(WordModel).where(
                WordModel.english == word_update.english.strip(),
                WordModel.user_id == current_user.id,
                WordModel.id != word_id,
            )
        )
        existing = result.scalar_one_or_none()
        if existing:
            raise HTTPException(status_code=400, detail=f"单词 '{word_update.english}' 已存在")
        word.english = word_update.english.strip()
    
    if word_update.chinese is not None:
        word.chinese = word_update.chinese.strip()
        
    if word_update.meta_data is not None:
        # 合并 meta_data，保留原有字段
        if word.meta_data is None:
            word.meta_data = {}
        word.meta_data.update(word_update.meta_data)

    if word_update.phonetic is not None:
        word.phonetic = word_update.phonetic.strip()

    if word_update.part_of_speech is not None:
        word.part_of_speech = word_update.part_of_speech.strip()

    word.updated_at = datetime.now()

    await db.commit()
    await db.refresh(word)
    return to_word_response(word)

# ============ DELETE 删除单词 ============
@router.delete("/{word_id}")
async def delete_word(word_id: str, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除单词"""
    result = await db.execute(select(WordModel).where(
        WordModel.id == word_id,
        WordModel.user_id == current_user.id
    ))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")
    
    await db.delete(word)
    await db.commit()
    return {"message": f"单词 '{word.english}' 已删除", "id": word_id}

# ============ DELETE 删除所有单词 ============
@router.delete("/")
async def delete_all_words(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    """删除所有单词（危险操作）"""
    result = await db.execute(select(WordModel).where(WordModel.user_id == current_user.id))
    words = result.scalars().all()
    count = len(words)
    await db.execute(delete(WordModel).where(WordModel.user_id == current_user.id))
    await db.commit()
    return {"message": f"已删除所有 {count} 个单词"}