"""Tests for school_rating_service's state-wide ICSEA percentile ranking."""

from __future__ import annotations

import pytest

from app.db.models import ABSCEntensMetrics, SA2Region
from app.db.session import AsyncSessionLocal
from app.services.school_rating_service import fetch_school_percentile


async def _seed(session, sa2_code, state, avg_school_icsea):
    session.add(SA2Region(sa2_code=sa2_code, sa2_name=f"Suburb {sa2_code}", state=state))
    session.add(ABSCEntensMetrics(sa2_code=sa2_code, year=2021, avg_school_icsea=avg_school_icsea))


@pytest.mark.asyncio
async def test_percentile_ranks_within_state_only():
    async with AsyncSessionLocal() as session:
        # 5 QLD SA2s spanning a range, plus a higher-ICSEA NSW one that must not affect the QLD ranking
        for i, icsea in enumerate([950, 1000, 1050, 1100, 1150]):
            await _seed(session, f"6000000{i}", "QLD", icsea)
        await _seed(session, "70000000", "NSW", 1400)
        await session.commit()

        result = await fetch_school_percentile(session, "60000004")  # icsea=1150, top of QLD group

    assert result["state"] == "QLD"
    assert result["sample_size"] == 5
    assert result["percentile"] == 100.0
    assert result["top_pct_label"] == "Top 1% of QLD"


@pytest.mark.asyncio
async def test_percentile_none_when_sample_too_small():
    async with AsyncSessionLocal() as session:
        for i, icsea in enumerate([1000, 1050]):
            await _seed(session, f"6100000{i}", "VIC", icsea)
        await session.commit()

        result = await fetch_school_percentile(session, "61000000")

    assert result is None


@pytest.mark.asyncio
async def test_percentile_none_when_suburb_has_no_icsea():
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code="62000000", sa2_name="No ICSEA Suburb", state="SA"))
        session.add(ABSCEntensMetrics(sa2_code="62000000", year=2021, avg_school_icsea=None))
        await session.commit()

        result = await fetch_school_percentile(session, "62000000")

    assert result is None


@pytest.mark.asyncio
async def test_percentile_none_for_unknown_sa2():
    async with AsyncSessionLocal() as session:
        result = await fetch_school_percentile(session, "00000098")
    assert result is None
