"""用户偏好（背诵模式 / 每日目标）落库接口。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import User, UserPreference
from ..schemas import PreferencesResponse, PreferencesUpdate
from ..deps import get_current_user

router = APIRouter()

DEFAULT_RULE = "judge"
DEFAULT_TARGET = 20


async def _get_or_create(db: AsyncSession, user_id: str) -> UserPreference:
    res = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    pref = res.scalar_one_or_none()
    if not pref:
        pref = UserPreference(user_id=user_id, recitation_rule=DEFAULT_RULE, daily_target=DEFAULT_TARGET)
        db.add(pref)
        await db.commit()
        await db.refresh(pref)
    return pref


def _to_response(pref: UserPreference) -> PreferencesResponse:
    return PreferencesResponse(
        recitation_rule=pref.recitation_rule or DEFAULT_RULE,
        daily_target=pref.daily_target or DEFAULT_TARGET,
        updated_at=pref.updated_at,
    )


@router.get("", response_model=PreferencesResponse)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = await _get_or_create(db, current_user.id)
    return _to_response(pref)


@router.put("", response_model=PreferencesResponse)
async def update_preferences(
    payload: PreferencesUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    pref = await _get_or_create(db, current_user.id)
    if payload.recitation_rule is not None:
        pref.recitation_rule = payload.recitation_rule
    if payload.daily_target is not None:
        pref.daily_target = max(1, min(200, int(payload.daily_target)))
    await db.commit()
    await db.refresh(pref)
    return _to_response(pref)
