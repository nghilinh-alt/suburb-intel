"""Tests for regional_comparison_service — grouping SA4-split capital cities
and excluding non-substantive pseudo-regions."""

from __future__ import annotations

import pytest

from app.db.models import ABSCEntensMetrics, SA2Region
from app.db.session import AsyncSessionLocal
from app.services.regional_comparison_service import fetch_regional_comparison


async def _seed_region(session, sa2_code, sa4_name, state, *, median_income=None, renters_pct=None):
    session.add(SA2Region(sa2_code=sa2_code, sa2_name=f"Suburb {sa2_code}", state=state, sa4_name=sa4_name))
    session.add(
        ABSCEntensMetrics(
            sa2_code=sa2_code,
            year=2021,
            median_income=median_income,
            renters_pct=renters_pct,
        )
    )


@pytest.mark.asyncio
async def test_capital_city_aggregates_across_split_sa4s():
    async with AsyncSessionLocal() as session:
        await _seed_region(session, "80000001", "Brisbane - East", "QLD", median_income=60000, renters_pct=30)
        await _seed_region(session, "80000002", "Brisbane Inner City", "QLD", median_income=80000, renters_pct=50)
        await _seed_region(session, "80000003", "Toowoomba", "QLD", median_income=55000, renters_pct=25)
        await session.commit()

        result = await fetch_regional_comparison(session, "80000001")

    assert result["region_label"] == "Brisbane"
    income = next(m for m in result["metrics"] if m["key"] == "median_income")
    # Average of the two Brisbane* SA2s only (60000, 80000), not Toowoomba's 55000
    assert income["region_average"] == 70000
    assert income["suburb_value"] == 60000


@pytest.mark.asyncio
async def test_regional_sa4_uses_its_own_name():
    async with AsyncSessionLocal() as session:
        await _seed_region(session, "80000004", "Central Queensland", "QLD", median_income=50000, renters_pct=20)
        await _seed_region(session, "80000005", "Central Queensland", "QLD", median_income=70000, renters_pct=40)
        await session.commit()

        result = await fetch_regional_comparison(session, "80000004")

    assert result["region_label"] == "Central Queensland"
    income = next(m for m in result["metrics"] if m["key"] == "median_income")
    assert income["region_average"] == 60000


@pytest.mark.asyncio
async def test_excludes_migratory_pseudo_region():
    async with AsyncSessionLocal() as session:
        await _seed_region(session, "80000006", "Migratory - Offshore - Shipping (QLD)", "QLD", median_income=50000)
        await session.commit()

        result = await fetch_regional_comparison(session, "80000006")

    assert result is None


@pytest.mark.asyncio
async def test_excludes_no_usual_address_pseudo_region():
    async with AsyncSessionLocal() as session:
        await _seed_region(session, "80000007", "No usual address (QLD)", "QLD", median_income=50000)
        await session.commit()

        result = await fetch_regional_comparison(session, "80000007")

    assert result is None


@pytest.mark.asyncio
async def test_returns_none_for_unknown_sa2():
    async with AsyncSessionLocal() as session:
        result = await fetch_regional_comparison(session, "00000000")
    assert result is None
