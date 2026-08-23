"""跨路由共享的 FastAPI 依赖。

将认证依赖从 auth 路由中解耦，供各业务路由复用，避免业务路由反向依赖 auth 路由。
"""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from .database import get_db
from .models import User
from .routers.auth import decode_access_token, oauth2_scheme


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """解析 JWT 并返回当前登录用户，失败则抛 401。"""
    payload = decode_access_token(token)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="无效Token")

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
