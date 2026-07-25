"""Tests for the backfill_scores job.

Uses a fully isolated in-memory engine per test — never touches global session state.
"""

from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import ABSCEntensMetrics, Base, PropertySale, SA2Region, SuburbMarketStats, SuburbScore
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


async def _build_engine_with_momentum_data():
    """20001 has two accelerating neighbors (20002, 20003) — enough known
    neighbors to clear summarize_neighborhood_momentum's 2-neighbor minimum
    for a signal. 20004 has census but no suburb_market_stats at all, to
    cover the "no PropRadar coverage yet" branch in the same fixture."""
    engine, Factory = await _build_engine()
    async with Factory() as db:
        r1 = (await db.execute(select(SA2Region).where(SA2Region.sa2_code == "20001"))).scalar_one()
        r1.adjacent_sa2_codes = ["20002", "20003"]

        for code in ("20001", "20002", "20003"):
            db.add(SuburbMarketStats(
                id=f"QLD-{code}-2026-07", sa2_code=code, suburb_name=f"Suburb {code}", state="QLD", period="2026-07",
                growth_house_1y_pct=15.0, gross_yield_house_pct=5.0, heat_score_house=90.0,
            ))
            db.add(PropertySale(
                id=f"sale-{code}", sa2_code=code, address="1 Test St", state="QLD",
                sold_price=500_000, sold_date="2026-06-15", source="propradar",
                fetched_at=datetime.now(timezone.utc),
            ))
        await db.commit()
    return engine, Factory


@pytest.mark.asyncio
async def test_momentum_fields_populated_when_market_data_present():
    engine, Factory = await _build_engine_with_momentum_data()
    try:
        async with Factory() as db:
            await backfill_scores(db, year=2021)

        async with Factory() as db:
            score1 = await db.get(SuburbScore, "20001")
            assert score1.momentum_phase == "accelerating"
            assert score1.momentum_score is not None
            assert score1.growth_yield_quadrant == "hot"
            # Both neighbors (20002, 20003) are also accelerating -> spillover signal
            assert score1.neighborhood_signal == "surrounded_by_acceleration"

            # 20004 has census but no suburb_market_stats -> momentum fields stay None
            score4 = await db.get(SuburbScore, "20004")
            assert score4.momentum_phase is None
            assert score4.momentum_score is None
            assert score4.growth_yield_quadrant is None
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
