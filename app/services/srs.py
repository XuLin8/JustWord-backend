"""间隔重复系统（Spaced Repetition System）—— SM-2 算法实现。

SuperMemo-2 为每个单词维护三个状态：
  - easiness factor (EF)：易学度因子，初始 2.5，长期记录单词难易；
  - repeat count (n)：连续答对次数；
  - interval：下次复习间隔天数。

用户每次复习给出质量分 quality（0-5），据此更新三态并计算 next_review_at。
"""
from datetime import datetime, timedelta
from typing import Tuple

from ..models import Word

# 复习结果 -> (质量分 quality, 是否记为答对 remembered)
#   correct=完全正确(5) partial=大体正确(4) close=接近(3) wrong=错误(2)
RESULT_QUALITY: dict[str, Tuple[int, bool]] = {
    "correct": (5, True),
    "partial": (4, True),
    "close": (3, True),
    "wrong": (2, False),
}


def apply_sm2(word: Word, result: str) -> dict:
    """对单词应用一次 SM-2 复习，原地更新调度字段，返回调度结果。"""
    quality, remembered = RESULT_QUALITY.get(result, (2, False))
    now = datetime.now()

    ef = word.ef if word.ef is not None else 2.5
    interval = word.review_interval if word.review_interval is not None else 0
    reps = word.repetitions if word.repetitions is not None else 0

    if quality < 3:
        # 答错：重置连续答对次数，明天再战
        reps = 0
        interval = 1
    else:
        reps += 1
        if reps == 1:
            interval = 1
        elif reps == 2:
            interval = 6
        else:
            interval = round(interval * ef)

    # 更新易学度因子（<1.3 时兜底为 1.3）
    new_ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    if new_ef < 1.3:
        new_ef = 1.3

    word.ef = round(new_ef, 2)
    word.review_interval = interval
    word.repetitions = reps
    word.last_reviewed_at = now
    word.next_review_at = now + timedelta(days=interval)

    return {
        "quality": quality,
        "remembered": remembered,
        "easiness_factor": word.ef,
        "interval_days": interval,
        "repetitions": reps,
        "next_review_at": word.next_review_at,
        "last_reviewed_at": now,
    }