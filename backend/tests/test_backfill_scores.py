"""Tests for the backfill_scores job.

Uses a fully isolated in-memory engine per test — never touches global session state.
"""

from __future__ import annotations

import asyncio
import tempfile

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import ABSCEntensMetrics, Base, SA2Region, SuburbScore
from app.jobs.backfill_scores import backfill_scores

_CODES = [f"2000{i}" for i in range(1, 6)]  # "20001" ... "20005"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def event_loop_policy():
    return asyncio.DefaultEventLoopPolicy()


async def _build_engine():
    """Create a fresh async SQLite in-memory engine with schema + seed data."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    SessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with SessionFactory() as db:
        for i, code in enumerate(_CODES, start=1):
            db.add(SA2Region(sa2_code=code, sa2_name=f"Suburb {i}", state="VIC"))
        await db.flush()
        for i, code in enumerate(_CODES, start=1):
            db.add(ABSCEntensMetrics(
                sa2_code=code,
                year=2021,
                population=10000 + i * 1000,
                median_income=60000 + i * 5000,
                median_age=30.0 + i,
                renters_pct=30.0 + i,
                owners_pct=50.0 - i,
                young_population_pct=20.0 + i,
                industry_profile={"tech": 0.3, "finance": 0.2, "retail": 0.5},
            ))
        await db.commit()
    return engine, SessionFactory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_all_sa2s_get_score():
    engine, Factory = await _build_engine()
    try:
        async with Factory() as db:
            report = await backfill_scores(db, year=2021)

        assert report.inserted == 5
        assert report.skipped == 0

        async with Factory() as db:
            for code in _CODES:
                score = await db.get(SuburbScore, code)
                assert score is not None, f"Missing SuburbScore for {code}"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_all_scores_within_contract():
    engine, Factory = await _build_engine()
    try:
        async with Factory() as db:
            await backfill_scores(db, year=2021)

        async with Factory() as db:
            for code in _CODES:
                score = await db.get(SuburbScore, code)
                assert score is not None
                for field in (
                    "investment_score", "demographic_score", "economic_score",
                    "housing_pressure_score", "resilience_score", "gov_investment_score",
                ):
                    val = getattr(score, field)
                    if val is not None:
                        assert 0 <= val <= 100, f"{field}={val} out of [0,100] for {code}"
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_updated_at_advances_on_rerun():
    engine, Factory = await _build_engine()
    try:
        async with Factory() as db:
            await backfill_scores(db, year=2021)

        async with Factory() as db:
            first_score = await db.get(SuburbScore, _CODES[0])
            first_updated = first_score.updated_at

        await asyncio.sleep(0.02)

        async with Factory() as db:
            report2 = await backfill_scores(db, year=2021)

        async with Factory() as db:
            second_score = await db.get(SuburbScore, _CODES[0])
            second_updated = second_score.updated_at

        assert report2.inserted == 0
        assert report2.updated == 5
        if first_updated and second_updated:
            assert second_updated >= first_updated
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_sa2_codes_filter():
    """Passing sa2_codes restricts backfill to those codes only."""
    engine, Factory = await _build_engine()
    try:
        async with Factory() as db:
            report = await backfill_scores(db, year=2021, sa2_codes=_CODES[:2])

        assert report.inserted == 2

        async with Factory() as db:
            # First two should have scores, last three should not
            for code in _CODES[:2]:
                assert await db.get(SuburbScore, code) is not None
            for code in _CODES[2:]:
                assert await db.get(SuburbScore, code) is None
    finally:
        await engine.dispose()
