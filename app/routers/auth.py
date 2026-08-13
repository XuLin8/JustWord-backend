from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional, Dict
import os
import jwt
from passlib.context import CryptContext

router = APIRouter()

# ============ 配置 ============
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-this-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ============ 模型 ============
class User(BaseModel):
    email: str
    username: str
    password_hash: str
    created_at: datetime = datetime.now()

class RegisterRequest(BaseModel):
    email: str
    username: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int

class UserResponse(BaseModel):
    email: str
    username: str
    created_at: datetime

# ============ 模拟数据库（临时） ============
# 实际项目请用真实数据库
fake_db: Dict[str, User] = {}

# ============ 工具函数 ============
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now() + expires_delta
    else:
        expire = datetime.now() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token已过期")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="无效Token")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    payload = decode_access_token(token)
    email = payload.get("sub")
    if email not in fake_db:
        raise HTTPException(status_code=401, detail="用户不存在")
    return fake_db[email]

# ============ API 端点 ============

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(req: RegisterRequest):
    """用户注册"""
    # 检查邮箱是否已存在
    if req.email in fake_db:
        raise HTTPException(status_code=400, detail="邮箱已被注册")
    
    # 检查用户名是否已存在
    for user in fake_db.values():
        if user.username == req.username:
            raise HTTPException(status_code=400, detail="用户名已被使用")
    
    # 创建用户
    new_user = User(
        email=req.email,
        username=req.username,
        password_hash=hash_password(req.password)
    )
    fake_db[req.email] = new_user
    
    return UserResponse(
        email=new_user.email,
        username=new_user.username,
        created_at=new_user.created_at
    )

@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """用户登录 - 返回 JWT Token"""
    # 查找用户
    user = fake_db.get(req.email)
    if not user:
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    
    # 验证密码
    if not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="邮箱或密码错误")
    
    # 创建 Token
    access_token = create_access_token(
        data={"sub": user.email, "username": user.username}
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """获取当前用户信息（需要登录）"""
    return UserResponse(
        email=current_user.email,
        username=current_user.username,
        created_at=current_user.created_at
    )

@router.post("/logout")
async def logout():
    """登出（客户端丢弃 Token 即可）"""
    return {"message": "登出成功"}