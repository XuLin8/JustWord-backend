from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uuid

router = APIRouter()

# ============ 模型 ============
class LearningRecordCreate(BaseModel):
    word_id: str
    mode: str  # 'en2zh' 或 'zh2en'
    user_answer: str
    correct_answer: str
    result: str  # 'correct', 'partial', 'wrong', 'close'
    score: float
    feedback: Optional[str] = None

class LearningRecordResponse(BaseModel):
    id: str
    word_id: str
    mode: str
    user_answer: str
    correct_answer: str
    result: str
    score: float
    feedback: Optional[str]
    created_at: datetime

class LearningStatsResponse(BaseModel):
    total_attempts: int
    correct_count: int
    correct_rate: float
    word_stats: List[dict]


# ============ 模拟数据库 ============
fake_learning_db: List[dict] = []


# ============ API 端点 ============

@router.post("/records", response_model=LearningRecordResponse, status_code=201)
async def create_learning_record(record: LearningRecordCreate):
    """保存学习记录"""
    new_record = {
        "id": str(uuid.uuid4()),
        "word_id": record.word_id,
        "mode": record.mode,
        "user_answer": record.user_answer,
        "correct_answer": record.correct_answer,
        "result": record.result,
        "score": record.score,
        "feedback": record.feedback,
        "created_at": datetime.now()
    }
    fake_learning_db.append(new_record)
    return new_record


@router.get("/records", response_model=List[LearningRecordResponse])
async def get_learning_records(
    limit: int = 50,
    word_id: Optional[str] = None,
    mode: Optional[str] = None
):
    """获取学习记录列表"""
    records = fake_learning_db.copy()
    
    if word_id:
        records = [r for r in records if r["word_id"] == word_id]
    if mode:
        records = [r for r in records if r["mode"] == mode]
    
    records.sort(key=lambda x: x["created_at"], reverse=True)
    return records[:limit]


@router.get("/stats", response_model=LearningStatsResponse)
async def get_learning_stats(word_id: Optional[str] = None):
    """获取学习统计"""
    records = fake_learning_db.copy()
    
    if word_id:
        records = [r for r in records if r["word_id"] == word_id]
    
    total = len(records)
    correct = len([r for r in records if r["result"] == "correct"])
    
    # 按单词统计
    word_stats = {}
    for r in records:
        wid = r["word_id"]
        if wid not in word_stats:
            word_stats[wid] = {"total": 0, "correct": 0}
        word_stats[wid]["total"] += 1
        if r["result"] == "correct":
            word_stats[wid]["correct"] += 1
    
    word_stats_list = [
        {
            "word_id": wid,
            "total": stats["total"],
            "correct": stats["correct"],
            "rate": stats["correct"] / stats["total"] if stats["total"] > 0 else 0
        }
        for wid, stats in word_stats.items()
    ]
    
    return LearningStatsResponse(
        total_attempts=total,
        correct_count=correct,
        correct_rate=correct / total if total > 0 else 0,
        word_stats=word_stats_list
    )


@router.delete("/records")
async def clear_learning_records():
    """清空所有学习记录"""
    count = len(fake_learning_db)
    fake_learning_db.clear()
    return {"message": f"已删除 {count} 条学习记录"}