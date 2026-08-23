"""学习域共享的纯逻辑助手（无 DB 依赖）。

从 learning.py 抽出的无副作用函数，供各业务路由复用：
时区偏移、序列化、打卡连击、掌握分级、遗忘曲线拟合、每日趋势补零。
"""
import math
from datetime import datetime, date, timedelta
from typing import List, Optional

from ..models import Word as WordModel, LearningRecord
from ..schemas import LearningRecordResponse, DashboardDailyTrend


def local_offset() -> timedelta:
    """本机时区相对 UTC 的偏移（created_at / next_review_at 均按本机实际时区处理）"""
    return datetime.now() - datetime.utcnow()


def to_record_response(r: LearningRecord) -> LearningRecordResponse:
    return LearningRecordResponse(
        id=r.id,
        word_id=r.word_id,
        user_id=r.user_id,
        mode=r.mode,
        user_answer=r.user_answer,
        correct_answer=r.correct_answer,
        result=r.result,
        score=r.score,
        feedback=r.feedback,
        created_at=r.created_at,
    )


def to_review_item(word: WordModel) -> dict:
    """将单词转为复习队列条目"""
    return {
        "id": word.id,
        "english": word.english,
        "chinese": word.chinese,
        "meta_data": word.meta_data or {},
        "repetitions": word.repetitions or 0,
        "interval_days": word.review_interval or 0,
        "next_review_at": word.next_review_at,
    }


def compute_streaks(dates: set) -> tuple:
    """根据打卡日期集合，返回 (当前连续天数, 最大连续天数)。
    当前连续天数：若今天已打卡则从今天往前数，否则从昨天往前数。"""
    if not dates:
        return 0, 0

    today = date.today()
    current = 0
    d = today
    if d not in dates:
        d = today - timedelta(days=1)
    while d in dates:
        current += 1
        d -= timedelta(days=1)

    max_streak = 0
    run = 0
    prev = None
    for d in sorted(dates):
        if prev is not None and (d - prev).days == 1:
            run += 1
        else:
            run = 1
        max_streak = max(max_streak, run)
        prev = d

    return current, max_streak


def mastery_level(reps: int) -> str:
    """按连续答对次数(rep)划分熟练度：未学/新学/巩固中/已掌握"""
    if reps >= 6:
        return "已掌握"
    if reps >= 3:
        return "巩固中"
    if reps >= 1:
        return "新学"
    return "未学"


def word_retention(word: WordModel, at: Optional[datetime] = None) -> Optional[float]:
    """按 Ebbinghaus 指数衰减模型估算某词的当前记忆保持率。

    以 SM-2 复习间隔天数作为记忆稳定度 S，从 last_reviewed_at 起随时间衰减：
    R(t) = exp(-t / S)。未学过或尚未定间隔的词返回 None（无法评估）。
    """
    if (word.repetitions or 0) <= 0 or (word.review_interval or 0) <= 0 or not word.last_reviewed_at:
        return None
    at = at or datetime.now()
    t_days = (at - word.last_reviewed_at).total_seconds() / 86400.0
    stability = max(float(word.review_interval), 0.5)
    r = math.exp(-max(t_days, 0.0) / stability)
    return round(min(max(r, 0.0), 1.0), 3)


def build_daily_trend(
    records, days: int, offset: timedelta, end: date
) -> List[DashboardDailyTrend]:
    """构建近 `days` 天每日学习趋势，保证输出连续日期序列（含 `end`）。

    - 天数钳制到 [1, 365]；
    - 每个窗口日期都预先置零，无数据天自动补零；
    - created_at 为 UTC，先按 offset 换算成本地日期；
    - dict 按插入顺序即日期升序，保证按时序返回。
    """
    days = max(1, min(days, 365))
    day_map = {}
    for i in range(days - 1, -1, -1):
        d = end - timedelta(days=i)
        day_map[d] = {"attempts": 0, "correct": 0}

    for r in records:
        d = (r.created_at + offset).date() if r.created_at else end
        if d in day_map:
            day_map[d]["attempts"] += 1
            if r.result == "correct":
                day_map[d]["correct"] += 1

    return [
        DashboardDailyTrend(
            date=d,
            attempts=agg["attempts"],
            correct=agg["correct"],
            correct_rate=agg["correct"] / agg["attempts"] if agg["attempts"] > 0 else 0.0,
        )
        for d, agg in day_map.items()
    ]