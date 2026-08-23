"""学习记录：学习历史的增删查与单维度统计。"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func
from typing import Optional

from ..database import get_db
from ..models import LearningRecord, User
from ..schemas import (
    LearningRecordCreate,
    LearningRecordResponse,
    LearningStatsResponse,
)
from ..services.learning_common import to_record_response
from ..deps import get_current_user

router = APIRouter()


@router.post("/records", response_model=LearningRecordResponse, status_code=201)
async def create_learning_record(
    record: LearningRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """保存学习记录（写入数据库，绑定当前用户）"""
    new_record = LearningRecord(
        word_id=record.word_id,
        user_id=current_user.id,
        mode=record.mode,
        user_answer=record.user_answer,
        correct_answer=record.correct_answer,
        result=record.result,
        score=record.score,
        feedback=record.feedback,
    )
    db.add(new_record)
    await db.commit()
    await db.refresh(new_record)
    return to_record_response(new_record)


@router.get("/records", response_model=dict)
async def get_learning_records(
    limit: int = 50,
    offset: int = 0,
    word_id: Optional[str] = None,
    mode: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的学习记录列表"""
    stmt = select(LearningRecord).where(LearningRecord.user_id == current_user.id)
    if word_id:
        stmt = stmt.where(LearningRecord.word_id == word_id)
    if mode:
        stmt = stmt.where(LearningRecord.mode == mode)
    stmt = stmt.order_by(LearningRecord.created_at.desc()).offset(offset).limit(limit)

    result = await db.execute(stmt)
    records = result.scalars().all()

    total = await db.execute(
        select(func.count()).select_from(LearningRecord).where(LearningRecord.user_id == current_user.id)
        .where(LearningRecord.word_id == word_id if word_id else True)
        .where(LearningRecord.mode == mode if mode else True)
    )
    total_count = total.scalar_one()

    return {
        "items": [to_record_response(r) for r in records],
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.delete("/records")
async def clear_learning_records(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """清空当前用户的学习记录"""
    result = await db.execute(delete(LearningRecord).where(LearningRecord.user_id == current_user.id))
    await db.commit()
    return {"message": f"已删除 {result.rowcount} 条学习记录"}


@router.get("/stats", response_model=LearningStatsResponse)
async def get_learning_stats(
    word_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """获取当前用户的学习统计"""
    stmt = select(LearningRecord).where(LearningRecord.user_id == current_user.id)
    if word_id:
        stmt = stmt.where(LearningRecord.word_id == word_id)
    result = await db.execute(stmt)
    records = result.scalars().all()

    total = len(records)
    correct = len([r for r in records if r.result == "correct"])
    word_stats = {}
    for r in records:
        s = word_stats.setdefault(r.word_id, {"total": 0, "correct": 0})
        s["total"] += 1
        if r.result == "correct":
            s["correct"] += 1
    word_stats_list = [
        {"word_id": wid, "total": s["total"], "correct": s["correct"],
         "rate": s["correct"] / s["total"] if s["total"] > 0 else 0}
        for wid, s in word_stats.items()
    ]
    return LearningStatsResponse(
        total_attempts=total,
        correct_count=correct,
        correct_rate=correct / total if total > 0 else 0,
        word_stats=word_stats_list,
    )