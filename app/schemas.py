from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Dict, Any, List

class WordCreate(BaseModel):
    chinese: str
    english: str  # ⚠️ 你漏了 english 字段！
    meta_data: Optional[Dict[str, Any]] = {}

class WordUpdate(BaseModel):
    english: Optional[str] = None
    chinese: Optional[str] = None
    meta_data: Optional[Dict[str, Any]] = None

class WordResponse(BaseModel):
    id: str
    english: str
    chinese: str
    created_at: datetime
    updated_at: datetime
    meta_data: Dict[str, Any] = {}

    class Config:
        from_attributes = True

class JudgeRequest(BaseModel):
    word: str
    user_answer: str
    correct_answer: str
    mode: str  # 'en2zh' 或 'zh2en'

class JudgeResponse(BaseModel):
    is_correct: bool
    score: float
    feedback: str
    suggestion: Optional[str] = None
    similar_words: Optional[List[str]] = None  # ✅ 用 List，不是 list

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    created_at: datetime

class LearningRecordResponse(BaseModel):
    id: int
    word_id: str
    mode: str
    user_answer: str
    correct_answer: str
    result: str
    score: int
    feedback: Optional[str]
    created_at: datetime