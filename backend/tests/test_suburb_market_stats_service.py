"""Tests for suburb_market_stats_service — a SA2 can have multiple rows
(one per real suburb it combines, and one per calendar-month snapshot for
each of those suburbs), returned as a list rather than averaged."""

from __future__ import annotations

import pytest

from app.db.models import SuburbMarketStats
from app.db.session import AsyncSessionLocal
from app.services.suburb_market_stats_service import (
    fetch_rental_market_history,
    fetch_suburb_market_stats,
)


@pytest.mark.asyncio
async def test_fetch_returns_one_row_per_real_suburb_in_sa2():
    sa2 = "91000001"
    async with AsyncSessionLocal() as session:
        session.add(SuburbMarketStats(
            id="QLD-rochedale-2026-07", sa2_code=sa2, suburb_name="Rochedale", state="QLD", period="2026-07",
            median_house_price=900_000, gross_yield_house_pct=3.5,
        ))
        session.add(SuburbMarketStats(
            id="QLD-burbank-2026-07", sa2_code=sa2, suburb_name="Burbank", state="QLD", period="2026-07",
            median_house_price=1_100_000, gross_yield_house_pct=3.1,
        ))
        await session.commit()

        result = await fetch_suburb_market_stats(session, sa2)

    assert len(result) == 2
    names = {r["suburb_name"] for r in result}
    assert names == {"Rochedale", "Burbank"}
    burbank = next(r for r in result if r["suburb_name"] == "Burbank")
    assert burbank["median_house_price"] == 1_100_000
    assert burbank["gross_yield_house_pct"] == 3.1


@pytest.mark.asyncio
async def test_fetch_returns_only_the_latest_period_per_suburb():
    sa2 = "91000002"
    async with AsyncSessionLocal() as session:
        session.add(SuburbMarketStats(
            id="QLD-cleveland-2026-06", sa2_code=sa2, suburb_name="Cleveland", state="QLD", period="2026-06",
            median_house_price=1_200_000,
        ))
        session.add(SuburbMarketStats(
            id="QLD-cleveland-2026-07", sa2_code=sa2, suburb_name="Cleveland", state="QLD", period="2026-07",
            median_house_price=1_280_000,
        ))
        await session.commit()

        result = await fetch_suburb_market_stats(session, sa2)

    assert len(result) == 1
    assert result[0]["median_house_price"] == 1_280_000


@pytest.mark.asyncio
async def test_fetch_empty_when_no_stats():
    async with AsyncSessionLocal() as session:
        result = await fetch_suburb_market_stats(session, "99999997")
    assert result == []


@pytest.mark.asyncio
async def test_rental_history_ordered_chronologically_per_suburb():
    sa2 = "91000003"
    async with AsyncSessionLocal() as session:
        session.add(SuburbMarketStats(
            id="QLD-rentalhistorytest-2026-06", sa2_code=sa2, suburb_name="Rentalhistorytest", state="QLD", period="2026-06",
            median_house_rent_weekly=780, vacancy_rate_pct=1.2,
        ))
        session.add(SuburbMarketStats(
            id="QLD-rentalhistorytest-2026-07", sa2_code=sa2, suburb_name="Rentalhistorytest", state="QLD", period="2026-07",
            median_house_rent_weekly=795, vacancy_rate_pct=1.1,
        ))
        session.add(SuburbMarketStats(
            id="QLD-rentalhistorytest-other-2026-07", sa2_code=sa2, suburb_name="Rentalhistorytestother", state="QLD", period="2026-07",
            median_house_rent_weekly=650, vacancy_rate_pct=0.9,
        ))
        await session.commit()

        result = await fetch_rental_market_history(session, sa2)

    by_suburb = {r["suburb_name"]: r["history"] for r in result}
    assert [h["period"] for h in by_suburb["Rentalhistorytest"]] == ["2026-06", "2026-07"]
    assert by_suburb["Rentalhistorytest"][0]["median_house_rent_weekly"] == 780
    assert by_suburb["Rentalhistorytest"][1]["median_house_rent_weekly"] == 795
    assert by_suburb["Rentalhistorytestother"] == [
        {
            "period": "2026-07",
            "median_house_rent_weekly": 650,
            "median_unit_rent_weekly": None,
            "gross_yield_house_pct": None,
            "gross_yield_unit_pct": None,
            "days_on_market_house": None,
            "days_on_market_unit": None,
            "vacancy_rate_pct": 0.9,
        }
    ]


@pytest.mark.asyncio
async def test_rental_history_empty_when_no_stats():
    async with AsyncSessionLocal() as session:
        result = await fetch_rental_market_history(session, "99999995")
    assert result == []
