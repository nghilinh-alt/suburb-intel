"""Tests for suburb_market_stats_service — a SA2 can have multiple rows
(one per real suburb it combines, and one per calendar-month snapshot for
each of those suburbs), returned as a list rather than averaged."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.db.models import PropertySale, SuburbMarketStats
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


async def _seed_sale_for_growth(session, id_, sa2_code, sold_date, sold_price, property_type="house"):
    session.add(PropertySale(
        id=id_, sa2_code=sa2_code, address=f"{id_} Test St", state="QLD",
        property_type=property_type, sold_price=sold_price, sold_date=sold_date,
        source="propradar", fetched_at=datetime.now(timezone.utc),
    ))


@pytest.mark.asyncio
async def test_null_propradar_growth_backfilled_from_property_sales():
    sa2 = "91000010"
    as_of = date(2026, 7, 10)
    async with AsyncSessionLocal() as session:
        session.add(SuburbMarketStats(
            id="QLD-growthtest-2026-07", sa2_code=sa2, suburb_name="Growthtest", state="QLD", period="2026-07",
            growth_house_1y_pct=None,  # PropRadar returned null for this field
            growth_house_3y_pct=8.2,   # PropRadar DID return a real figure — must not be overwritten
        ))
        for i, price in enumerate([600_000, 610_000, 620_000]):
            await _seed_sale_for_growth(session, f"g-recent-{i}", sa2, "2026-06-15", price)
        for i, price in enumerate([500_000, 505_000, 510_000]):
            await _seed_sale_for_growth(session, f"g-prior-{i}", sa2, "2025-06-15", price)
        await session.commit()

        result = await fetch_suburb_market_stats(session, sa2, as_of=as_of)

    record = result[0]
    assert record["growth_house_1y_pct"] == 20.8  # backfilled
    assert record["growth_house_3y_pct"] == 8.2  # untouched — real PropRadar value wins
    assert record["growth_derived_fields"] == ["growth_house_1y_pct"]


@pytest.mark.asyncio
async def test_growth_derived_fields_empty_when_nothing_to_backfill():
    sa2 = "91000011"
    async with AsyncSessionLocal() as session:
        session.add(SuburbMarketStats(
            id="QLD-nogrowthtest-2026-07", sa2_code=sa2, suburb_name="Nogrowthtest", state="QLD", period="2026-07",
        ))
        await session.commit()

        result = await fetch_suburb_market_stats(session, sa2)

    assert result[0]["growth_derived_fields"] == []
    assert result[0]["growth_house_1y_pct"] is None
