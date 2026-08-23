from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date, datetime, timedelta

from ..database import get_db
from ..models import User, Word as WordModel, Checkin, WrongWord, Achievement, LearningRecord
from ..schemas import AchievementResponse, AchievementItem
from ..routers.auth import get_current_user

router = APIRouter()


# 成就定义（key, 名称, 描述, 分类, 目标值, 进展取数键）
def _define_achievements() -> list[dict]:
    defi = []
    def add(key, name, desc, cat, target, metric):
        defi.append({"key": key, "name": name, "description": desc,
                     "category": cat, "target": target, "metric": metric})
    # 词汇
    add("first_word", "初识单词", "学会第一个单词", "words", 1, "learned")
    add("words_50", "小有积累", "累计学会 50 个单词", "words", 50, "learned")
    add("words_200", "渐入佳境", "累计学会 200 个单词", "words", 200, "learned")
    add("words_500", "词汇达人", "累计学会 500 个单词", "words", 500, "learned")
    add("mastered_50", "深度掌握", "掌握 50 个单词（连续答对达标）", "words", 50, "mastered")
    # 打卡
    add("streak_3", "小连击", "连续打卡 3 天", "checkin", 3, "streak")
    add("streak_7", "每周坚持", "连续打卡 7 天", "checkin", 7, "streak")
    add("streak_30", "月度自律", "连续打卡 30 天", "checkin", 30, "streak")
    add("checkin_100", "百日打卡", "累计打卡 100 天", "checkin", 100, "checkin_total")
    # 作答
    add("correct_50", "出手不凡", "累计答对 50 次", "answer", 50, "correct")
    add("correct_500", "题海老手", "累计答对 500 次", "answer", 500, "correct")
    # 错题
    add("wrong_clear_10", "知错就改", "累计解决 10 个错题", "wrong", 10, "wrong_cleared")
    return defi


def _current_streak(checkin_dates: set[date]) -> int:
    if not checkin_dates:
        return 0
    cur = date.today()
    streak = 0
    while cur in checkin_dates:
        streak += 1
        cur = cur - timedelta(days=1)
    return streak


@router.get("", response_model=AchievementResponse)
async def get_achievements(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查询成就/徽章清单：含每项当前进度与是否已解锁；达成的成就自动入库记录解锁时间。"""
    # 汇总统计
    learned = (await db.execute(
        select(func.count()).select_from(WordModel).where(
            WordModel.user_id == current_user.id, WordModel.repetitions > 0)
    )).scalar_one()
    mastered = (await db.execute(
        select(func.count()).select_from(WordModel).where(
            WordModel.user_id == current_user.id, WordModel.repetitions >= 6)
    )).scalar_one()

    checkin_dates = set((await db.execute(
        select(Checkin.date).where(Checkin.user_id == current_user.id)
    )).scalars().all())
    checkin_total = len(checkin_dates)
    streak = _current_streak(checkin_dates)

    correct = (await db.execute(
        select(func.count()).select_from(LearningRecord).where(
            LearningRecord.user_id == current_user.id, LearningRecord.result == "correct")
    )).scalar_one()
    wrong_cleared = (await db.execute(
        select(func.count()).select_from(WrongWord).where(
            WrongWord.user_id == current_user.id, WrongWord.status == "resolved")
    )).scalar_one()

    metrics = {
        "learned": learned, "mastered": mastered, "streak": streak,
        "checkin_total": checkin_total, "correct": correct,
        "wrong_cleared": wrong_cleared,
    }

    # 已解锁记录
    unlocked_map = {a.akey: a.unlocked_at for a in (await db.execute(
        select(Achievement).where(Achievement.user_id == current_user.id)
    )).scalars().all()}

    # 计算每项进度并自动入库新达成
    items = []
    newly_unlocked = []
    for d in _define_achievements():
        metric = metrics[d["metric"]]
        progress = min(metric, d["target"])
        rate = round(progress / d["target"], 3)
        unlocked = metric >= d["target"]
        if unlocked and d["key"] not in unlocked_map:
            newly_unlocked.append(d["key"])
        items.append(AchievementItem(
            key=d["key"], name=d["name"], description=d["description"],
            category=d["category"], target=d["target"], progress=progress,
            progress_rate=rate, unlocked=unlocked,
            unlocked_at=unlocked_map.get(d["key"]),
        ))

    if newly_unlocked:
        now = datetime.utcnow()
        db.add_all(Achievement(user_id=current_user.id, akey=k, unlocked_at=now) for k in newly_unlocked)
        await db.commit()
        unlocked_map.update({k: now for k in newly_unlocked})
        for it in items:
            if it.key in newly_unlocked:
                it.unlocked_at = now

    return AchievementResponse(
        items=items, unlocked_count=sum(1 for it in items if it.unlocked),
        total_count=len(items),
    )