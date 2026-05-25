from sqlalchemy.ext.asyncio import create_async_engine, async_session, AsyncSession
from sqlalchemy.orm import DeclarativeBase


DATABASE_URL = "postgresql+asyncpg://sa2:census@localhost:5432/suburb_intel"

engine = create_async_engine(DATABASE_URL, echo=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session(engine) as session:
        yield session


# Create tables on startup
async def init_db():
    from app.db import models
    from sqlalchemy import text
    
    async with engine.begin() as conn:
        await conn.run_sync(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.run_sync(text("CREATE SCHEMA public"))
        await conn.execute(text("""
            CREATE TABLE sa2_regions (
                sa2_code TEXT PRIMARY KEY,
                sa2_name TEXT,
                state TEXT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE abs_census_metrics (
                sa2_code TEXT,
                year INT,
                population INT,
                median_income INT,
                median_age FLOAT,
                renters_pct FLOAT,
                owners_pct FLOAT,
                industry_profile JSONB,
                PRIMARY KEY (sa2_code, year)
            )
        """))
        await conn.execute(text("""
            CREATE TABLE infrastructure_projects (
                project_id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                value_aud BIGINT,
                status TEXT,
                lat FLOAT,
                lon FLOAT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE sa2_project_link (
                sa2_code TEXT,
                project_id TEXT,
                impact_score FLOAT
            )
        """))
        await conn.execute(text("""
            CREATE TABLE suburb_scores (
                sa2_code TEXT PRIMARY KEY,
                investment_score FLOAT,
                demographic_score FLOAT,
                economic_score FLOAT,
                housing_pressure_score FLOAT,
                resilience_score FLOAT,
                gov_investment_score FLOAT,
                risk_flags JSONB,
                updated_at TIMESTAMP
            )
        """))
    print("Database initialized successfully")
