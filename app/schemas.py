from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class WordCreate(BaseModel):
    english: str
    chinese: str

class WordResponse(BaseModel):
    id: str
    english: str
    chinese: str
    created_at: datetime

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
    similar_words: Optional[list[str]] = None