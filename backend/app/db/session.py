"""Async SQLAlchemy session factory.

Supports both PostgreSQL (via asyncpg) and SQLite (via aiosqlite). The driver is
selected automatically from the DATABASE_URL scheme.
"""

from __future__ import annotations

from typing import AsyncGenerator

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

load_dotenv()


class DatabaseSettings(BaseSettings):
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./suburb_intel_dev.db",
        description="SQLAlchemy async database URL",
    )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = DatabaseSettings()
DATABASE_URL: str = settings.DATABASE_URL

# SQLite needs an async driver. We accept either `sqlite://` or `sqlite+aiosqlite://`
# in config and normalize it here so users don't have to remember the driver suffix.
if DATABASE_URL.startswith("sqlite://"):
    DATABASE_URL = DATABASE_URL.replace("sqlite://", "sqlite+aiosqlite://", 1)

is_sqlite: bool = DATABASE_URL.startswith("sqlite+aiosqlite://")

engine = create_async_engine(DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an AsyncSession.

    Use with `Depends(get_db)` in route handlers; do NOT call as a context manager.
    """
    async with AsyncSessionLocal() as session:
        yield session


async def init_models() -> None:
    """Create all tables defined on Base.metadata.

    Intended for dev/test bootstrap only. Production uses migrations.
    """
    from app.db.models import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ---------------------------------------------------------------------------
# Sync helpers (kept for the seed script which uses sync SQLAlchemy directly).
# ---------------------------------------------------------------------------

def _build_sync_url(url: str) -> str:
    """Convert an async URL into its sync equivalent for the seeder."""
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    return url


def get_sync_session():
    """Get a new synchronous session for one-off scripts (e.g. seeding)."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    sync_url = _build_sync_url(DATABASE_URL)
    sync_engine_local = create_engine(sync_url, future=True)
    SessionFactory = sessionmaker(bind=sync_engine_local, expire_on_commit=False)
    return SessionFactory()


# Backwards compatibility for code that imports `sync_engine` directly.
from sqlalchemy import create_engine as _create_engine  # noqa: E402

sync_engine = _create_engine(_build_sync_url(DATABASE_URL), future=True)


def init_db() -> None:
    """Sync-mode initialiser used by the seed script."""
    from app.db import models

    models.Base.metadata.drop_all(bind=sync_engine)
    models.Base.metadata.create_all(bind=sync_engine)
