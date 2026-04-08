import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.tables import Base

def _normalise_db_url(raw: str) -> str:
    """Normalise Neon/Railway postgres URLs for asyncpg compatibility."""
    if raw.startswith("postgres://"):
        raw = raw.replace("postgres://", "postgresql+asyncpg://", 1)
    elif raw.startswith("postgresql://") and "+asyncpg" not in raw:
        raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
    # asyncpg uses ssl=require, not sslmode=require
    raw = raw.replace("sslmode=require", "ssl=require")
    # asyncpg doesn't support channel_binding
    import re
    raw = re.sub(r"[&?]channel_binding=[^&]*", "", raw)
    return raw

_raw_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./golf.db")
DATABASE_URL = _normalise_db_url(_raw_url)

_is_sqlite = DATABASE_URL.startswith("sqlite")

engine = create_async_engine(
    DATABASE_URL,
    # pool_pre_ping handles Neon cold-start TCP resets gracefully
    pool_pre_ping=not _is_sqlite,
    # SQLite doesn't support connection pools; disable for it
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a DB session, rolls back on error."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_tables() -> None:
    """Create all tables (dev/test only — production uses Alembic migrations)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_tables() -> None:
    """Drop all tables (test teardown only)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
