from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
import os
from dotenv import load_dotenv

load_dotenv()

# 数据库连接：默认本地 MySQL（justword 库，root/123456），可通过环境变量覆盖
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+aiomysql://root:123456@127.0.0.1:3306/justword",
)
SQL_ECHO = os.getenv("SQL_ECHO", "0") == "1"

engine = create_async_engine(DATABASE_URL, echo=SQL_ECHO)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session