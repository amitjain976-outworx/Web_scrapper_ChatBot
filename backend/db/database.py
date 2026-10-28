from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import declarative_base
import os

from config import settings


# =========================
# DATABASE URL
# =========================

DATABASE_URL = settings.DATABASE_URL


# =========================
# SQLALCHEMY BASE
# =========================

Base = declarative_base()


# =========================
# ASYNC ENGINE
# =========================

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DB_ECHO,
    future=True,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=40,
)


# =========================
# SESSION MAKER
# =========================

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# =========================
# DEPENDENCY
# =========================

async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
