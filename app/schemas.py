from pydantic import BaseModel
from datetime import datetime, date
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

class LearningRecordCreate(BaseModel):
    word_id: str
    mode: str  # 'en2zh' 或 'zh2en'
    user_answer: str
    correct_answer: str
    result: str  # 'correct', 'partial', 'wrong', 'close'
    score: float
    feedback: Optional[str] = None

class LearningRecordResponse(BaseModel):
    id: int
    word_id: str
    user_id: str
    mode: str
    user_answer: str
    correct_answer: str
    result: str
    score: float
    feedback: Optional[str] = None
    created_at: datetime

class LearningStatsResponse(BaseModel):
    total_attempts: int
    correct_count: int
    correct_rate: float
    word_stats: List[dict]

class ReviewSubmit(BaseModel):
    word_id: str
    result: str  # 'correct', 'partial', 'close', 'wrong'
    mode: Optional[str] = "review"  # 可标注 'learn' / 'review'
    user_answer: Optional[str] = ""
    correct_answer: Optional[str] = ""
    feedback: Optional[str] = None

class ReviewSummaryResponse(BaseModel):
    due_count: int      # 今日待复习（含新词）
    new_count: int      # 从未复习过的新词
    review_count: int   # 已到期的复习词
    learned_count: int  # 已学过（repetitions > 0）的单词数

class CheckinStatusResponse(BaseModel):
    checked_today: bool
    current_streak: int
    max_streak: int
    total_days: int
    last_checkin_date: Optional[date] = None

class DashboardWordStats(BaseModel):
    total: int                 # 总单词数
    learned: int               # 已学（repetitions > 0）
    mastered: int              # 已掌握（repetitions >= 6）
    new_words_due: int         # 今日待学新词
    review_words_due: int      # 今日待复习词
    distribution: List[dict]   # 熟练度分布 [{label, count}]

class DashboardLearningStats(BaseModel):
    total_attempts: int
    correct_count: int
    correct_rate: float
    by_result: List[dict]      # [{result, count}]

class DashboardDailyTrend(BaseModel):
    date: date
    attempts: int
    correct: int
    correct_rate: float

class DashboardResponse(BaseModel):
    word_stats: DashboardWordStats
    learning_stats: DashboardLearningStats
    daily_trend: List[DashboardDailyTrend]   # 最近 7 天
    checkin_stats: dict                       # current/max streak、累计、上次打卡