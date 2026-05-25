import os
from sqlalchemy.ext.asyncio import create_async_engine, async_session, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class DatabaseSettings(BaseSettings):
    DATABASE_URL: str = Field(..., description="Database connection URL")


settings = DatabaseSettings()
DATABASE_URL = settings.DATABASE_URL

# Handle SQLite vs PostgreSQL
is_sqlite = DATABASE_URL.startswith("sqlite://")

if is_sqlite:
    # Use SQLite sync engine for development
    from sqlalchemy import create_engine
    sync_engine = create_engine(DATABASE_URL)
else:
    # Use PostgreSQL async engine
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(DATABASE_URL, echo=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    """Async session factory for PostgreSQL"""
    if is_sqlite:
        raise Exception("SQLite requires synchronous operations - use sync_get_db instead")
    async with async_session(engine) as session:
        yield session


def sync_get_db():
    """Sync session factory for SQLite"""
    from sqlalchemy.orm import sessionmaker
    LocalSession = sessionmaker(bind=sync_engine, autocommit=False, expire_on_commit=False)
    
    def get_session():
        return LocalSession()
    
    # Return the session factory to be called once per operation
    return lambda: LocalSession()


def get_sync_session():
    """Get a new sync session for SQLite operations"""
    from sqlalchemy.orm import sessionmaker, scoped_session
    LocalSession = sessionmaker(bind=sync_engine, autocommit=False, expire_on_commit=False)
    Session = scoped_session(LocalSession)
    return Session()


# Create tables on startup (only works with SQLite in sync mode)
def init_db():
    """Initialize database with sample data (SQLite only)"""
    from app.db import models
    
    if not is_sqlite:
        print("SQLite required for development initialization. Set DATABASE_URL to sqlite://...")
        return
    
    Base.metadata.drop_all(bind=sync_engine)
    Base.metadata.create_all(bind=sync_engine)
    print("Database initialized successfully (SQLite)")
