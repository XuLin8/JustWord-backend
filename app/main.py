from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .database import engine, Base
from .routers import (
    words, ai, auth, wordbooks, library, export, achievements,
    records, reviews, wrong_words, checkin, dashboard, analysis,
    preferences, progress, sessions,
)
from .exceptions import register_exception_handlers

# 数据库表创建
@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(
    title="JustWord API",
    version="0.1.0",
    description="JustWord 学习应用后端 API",
    lifespan=lifespan
)

# CORS 配置（允许前端访问）
app.add_middleware(
    CORSMiddleware,
     allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://192.168.31.214:5173",   # ✅ 前端地址
        "http://192.168.31.221:3000",   # ✅ 后端地址
        "http://192.168.31.214",        # ✅ 前端 IP
        "http://192.168.31.221",        # ✅ 后端 IP
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册异常处理器
register_exception_handlers(app)

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["认证"])
app.include_router(words.router, prefix="/api/words", tags=["单词"])
app.include_router(wordbooks.router, prefix="/api/wordbooks", tags=["单词本"])
app.include_router(library.router, prefix="/api/library", tags=["词库"])
app.include_router(export.router, prefix="/api/export", tags=["导出/备份"])
app.include_router(achievements.router, prefix="/api/achievements", tags=["成就"])
app.include_router(ai.router, prefix="/api/ai", tags=["AI"])

# 学习域（原 learning.py 拆分而来，路径不变）
app.include_router(records.router, prefix="/api/learning", tags=["学习-记录"])
app.include_router(reviews.router, prefix="/api/learning", tags=["学习-复习"])
app.include_router(wrong_words.router, prefix="/api/learning", tags=["学习-错题"])
app.include_router(checkin.router, prefix="/api/learning", tags=["学习-打卡"])
app.include_router(dashboard.router, prefix="/api/learning", tags=["学习-看板"])
app.include_router(analysis.router, prefix="/api/learning", tags=["学习-分析"])
app.include_router(preferences.router, prefix="/api/preferences", tags=["偏好"])
app.include_router(progress.router, prefix="/api", tags=["进度"])
app.include_router(sessions.router, prefix="/api/learning", tags=["学习-会话/统计"])

@app.get("/api/health")
async def health():
    return {"status": "OK", "service": "JustWord Backend"}