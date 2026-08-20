from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from ..database import get_db
from ..models import Word as WordModel
from ..schemas import WordCreate, WordUpdate, WordResponse

router = APIRouter()

# ============ Pydantic 模型 ============
class WordCreate(BaseModel):
    english: str
    chinese: str

class WordUpdate(BaseModel):
    english: Optional[str] = None
    chinese: Optional[str] = None

class WordResponse(BaseModel):
    id: str
    english: str
    chinese: str
    created_at: datetime


# ============ 辅助函数 ============
def to_word_response(word: WordModel) -> WordResponse:
    """将 SQLAlchemy 模型转换为 Pydantic 响应模型"""
    return WordResponse(
        id=word.id,
        english=word.english,
        chinese=word.chinese,
        created_at=word.created_at,
         updated_at=word.updated_at,
        meta_data=word.meta_data or {}
    )


# ============ API 端点 ============

@router.get("/", response_model=List[WordResponse])
async def get_words(db: AsyncSession = Depends(get_db)):
    """获取所有单词列表"""
    result = await db.execute(select(WordModel))
    words = result.scalars().all()
    return [to_word_response(w) for w in words]


@router.post("/", response_model=WordResponse, status_code=201)
async def create_word(word: WordCreate, db: AsyncSession = Depends(get_db)):
    """创建新单词"""
    # 检查是否已存在相同英文单词
    result = await db.execute(
        select(WordModel).where(WordModel.english == word.english.strip())
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail=f"单词 '{word.english}' 已存在")
    
    # 创建新单词
    new_word = WordModel(
        id=str(uuid.uuid4()),
        english=word.english.strip(),
        chinese=word.chinese.strip(),
        created_at=datetime.now(),
        updated_at=datetime.now(),
        meta_data=word.meta_data or {}
    )
    db.add(new_word)
    await db.commit()
    await db.refresh(new_word)
    
    return to_word_response(new_word)


@router.get("/{word_id}", response_model=WordResponse)
async def get_word(word_id: str, db: AsyncSession = Depends(get_db)):
    """根据 ID 获取单个单词"""
    result = await db.execute(select(WordModel).where(WordModel.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")
    return to_word_response(word)


@router.put("/{word_id}", response_model=WordResponse)
async def update_word(
    word_id: str, 
    word_update: WordUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """更新单词信息"""
    result = await db.execute(select(WordModel).where(WordModel.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")
    
    if word_update.english is not None:
        # 检查英文是否与其他单词重复
        result = await db.execute(
            select(WordModel).where(
                WordModel.english == word_update.english.strip(),
                WordModel.id != word_id
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
    
    word.updated_at = datetime.now()

    await db.commit()
    await db.refresh(word)
    return to_word_response(word)


@router.delete("/{word_id}")
async def delete_word(word_id: str, db: AsyncSession = Depends(get_db)):
    """删除单词"""
    result = await db.execute(select(WordModel).where(WordModel.id == word_id))
    word = result.scalar_one_or_none()
    if not word:
        raise HTTPException(status_code=404, detail="单词不存在")
    
    await db.delete(word)
    await db.commit()
    return {"message": f"单词 '{word.english}' 已删除", "id": word_id}


@router.delete("/")
async def delete_all_words(db: AsyncSession = Depends(get_db)):
    """删除所有单词（危险操作）"""
    result = await db.execute(select(WordModel))
    words = result.scalars().all()
    count = len(words)
    await db.execute(delete(WordModel))
    await db.commit()
    return {"message": f"已删除所有 {count} 个单词"}