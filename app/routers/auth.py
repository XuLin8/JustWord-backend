from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional
import os
import secrets
import hashlib
import jwt
import bcrypt
from uuid import uuid4
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from ..database import get_db
from ..models import User, RefreshToken

router = APIRouter()

# ============ 配置 ============
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "30"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ============ 请求 / 响应模型 ============
class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class RefreshRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int

class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    created_at: datetime


# ============ 工具函数 ============
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now() + (expires_delta if expires_delta else timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效Token")

def generate_refresh_token() -> str:
    """生成不透明刷新令牌（只落库哈希，不落库明文）"""
    return secrets.token_urlsafe(48)

def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def create_refresh_token_row(user_id: str):
    """创建刷新令牌记录，返回 (记录, 明文令牌)"""
    raw = generate_refresh_token()
    row = RefreshToken(
        id=str(uuid4()),
        user_id=user_id,
        token_hash=hash_refresh_token(raw),
        expires_at=datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )
    return row, raw

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = decode_access_token(token)
    email = payload.get("sub")
    if not email:
        raise HTTPException(status_code=401, detail="无效Token")
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user

async def resolve_refresh_token(db: AsyncSession, raw: str) -> RefreshToken:
    """根据明文刷新令牌解析出未撤销、未过期的记录，否则抛 401"""
    if not raw:
        raise HTTPException(status_code=401, detail="无效刷新令牌")
    digest = hash_refresh_token(raw)
    result = await db.execute(select(RefreshToken).where(RefreshToken.token_hash == digest))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=401, detail="刷新令牌不存在")
    if row.revoked_at is not None:
        raise HTTPException(status_code=401, detail="刷新令牌已失效，请重新登录")
    if row.expires_at < datetime.utcnow():
        row.revoked_at = datetime.utcnow()
        await db.commit()
        raise HTTPException(status_code=401, detail="刷新令牌已过期，请重新登录")
    return row

# ============ API 端点 ============

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    result = await db.execute(select(User).where(User.username == req.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="用户名已被使用")
    new_user = User(
        id=str(uuid.uuid4()),
        email=req.email,
        username=req.username,
        password_hash=hash_password(req.password),
        created_at=datetime.utcnow(),
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        username=new_user.username,
        created_at=new_user.created_at,
    )

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == req.email))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    access_token = create_access_token(data={"sub": user.email, "username": user.username})
    rt_row, rt_raw = create_refresh_token_row(user.id)
    db.add(rt_row)
    await db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=rt_raw,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.post("/refresh", response_model=TokenResponse)
async def refresh(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """用未过期的 refresh token 换取新 access token，并轮换 refresh token"""
    row = await resolve_refresh_token(db, req.refresh_token)
    user_result = await db.execute(select(User).where(User.id == row.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    access_token = create_access_token(data={"sub": user.email, "username": user.username})
    new_row, new_raw = create_refresh_token_row(user.id)
    row.revoked_at = datetime.utcnow()           # 旧 refresh token 立即失效（轮换）
    row.replaced_by_id = new_row.id
    db.add(new_row)
    await db.commit()
    return TokenResponse(
        access_token=access_token,
        refresh_token=new_raw,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        created_at=current_user.created_at,
    )

@router.post("/logout")
async def logout(req: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """登出：撤销指定的 refresh token"""
    row = await resolve_refresh_token(db, req.refresh_token)
    row.revoked_at = datetime.utcnow()
    await db.commit()
    return {"message": "登出成功"}
