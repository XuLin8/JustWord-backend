from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from datetime import date, datetime, timedelta
import lunardate

from ..database import get_db
from ..models import User, Word as WordModel, Checkin, WrongWord, Achievement, LearningRecord
from ..schemas import AchievementResponse, AchievementItem
from ..deps import get_current_user

router = APIRouter()


# 节日勋章清单（key, 名称, 类型 solar=公历 / lunar=农历, 月, 日）
_FESTIVALS = [
    ("festival_new_year", "元旦", "solar", 1, 1),
    ("festival_valentine", "情人节", "solar", 2, 14),
    ("festival_women", "妇女节", "solar", 3, 8),
    ("festival_labor", "劳动节", "solar", 5, 1),
    ("festival_children", "儿童节", "solar", 6, 1),
    ("festival_national", "国庆节", "solar", 10, 1),
    ("festival_christmas_eve", "平安夜", "solar", 12, 24),
    ("festival_christmas", "圣诞节", "solar", 12, 25),
    ("festival_spring", "春节", "lunar", 1, 1),
    ("festival_lantern", "元宵节", "lunar", 1, 15),
    ("festival_dragon", "端午节", "lunar", 5, 5),
    ("festival_midautumn", "中秋节", "lunar", 8, 15),
]


def _festival_dates(year: int) -> dict:
    """计算某年所有节日的公历日期（农历节日经 lunardate 换算）。"""
    result = {}
    for key, _name, kind, m, d in _FESTIVALS:
        try:
            if kind == "solar":
                result[key] = date(year, m, d)
            else:
                result[key] = lunardate.LunarDate(year, m, d).toSolarDate()
        except ValueError:
            continue  # 个别年份无该农历日（如闰月错位），跳过
    return result


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

    # 节日勋章（彩蛋）：当年节日 + 往年已解锁的节日
    festival_dates = _festival_dates(date.today().year)
    for key, name, _kind, _m, _d in _FESTIVALS:
        f_date = festival_dates.get(key)
        if f_date is None:
            continue
        unlocked_now = f_date in checkin_dates   # 节日当天有打卡 → 解锁彩蛋
        unlocked = unlocked_now or (key in unlocked_map)  # 往年解锁过的也保留
        if unlocked_now and key not in unlocked_map:
            newly_unlocked.append(key)
        items.append(AchievementItem(
            key=key, name=f"{name}彩蛋", description=f"在{name}当天坚持学习打卡，解锁节日彩蛋",
            category="holiday", target=1,
            progress=1 if unlocked else 0,
            progress_rate=1.0 if unlocked else 0.0,
            unlocked=unlocked,
            unlocked_at=unlocked_map.get(key),
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