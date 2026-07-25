"""Tests for momentum_service's DB-fetch wrapper, using synthetic
PropertySale rows (mirrors test_property_market_service.py's pattern)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db.models import PropertySale, SA2Region, SuburbMarketStats
from app.db.session import AsyncSessionLocal
from app.services.momentum_service import fetch_neighborhood_momentum, fetch_sale_velocity


async def _seed_sale(session, id_, sa2_code, sold_date):
    session.add(
        PropertySale(
            id=id_,
            sa2_code=sa2_code,
            address=f"{id_} Test St",
            state="QLD",
            sold_price=500_000,
            sold_date=sold_date,
            source="propradar",
            fetched_at=datetime.now(timezone.utc),
        )
    )


@pytest.mark.asyncio
async def test_fetch_sale_velocity_reads_sold_dates_for_sa2():
    sa2 = "90000301"
    async with AsyncSessionLocal() as session:
        await _seed_sale(session, "sv1", sa2, "2026-06-01")
        await _seed_sale(session, "sv2", sa2, "2026-06-15")
        await _seed_sale(session, "sv3", sa2, "2026-05-01")
        await session.commit()

        result = await fetch_sale_velocity(session, sa2)

    assert result["monthly_counts"] == [
        {"period": "2026-05", "count": 1},
        {"period": "2026-06", "count": 2},
    ]


@pytest.mark.asyncio
async def test_fetch_sale_velocity_empty_when_no_sales():
    async with AsyncSessionLocal() as session:
        result = await fetch_sale_velocity(session, "99999997")

    assert result["monthly_counts"] == []
    assert result["trend_pct"] is None


@pytest.mark.asyncio
async def test_fetch_sale_velocity_only_reads_own_sa2():
    async with AsyncSessionLocal() as session:
        await _seed_sale(session, "sv4", "90000302", "2026-06-01")
        await _seed_sale(session, "sv5", "90000303", "2026-06-01")
        await session.commit()

        result = await fetch_sale_velocity(session, "90000302")

    assert result["monthly_counts"] == [{"period": "2026-06", "count": 1}]


def _seed_accelerating_stats(session, id_, sa2_code):
    session.add(SuburbMarketStats(
        id=id_, sa2_code=sa2_code, suburb_name="Test", state="QLD", period="2026-07",
        growth_house_1y_pct=20.0, heat_score_house=100.0,
    ))


def _seed_cooling_stats(session, id_, sa2_code):
    session.add(SuburbMarketStats(
        id=id_, sa2_code=sa2_code, suburb_name="Test", state="QLD", period="2026-07",
        growth_house_1y_pct=-20.0, heat_score_house=0.0,
    ))


@pytest.mark.asyncio
async def test_fetch_neighborhood_momentum_surrounded_by_acceleration():
    center, n1, n2 = "90000410", "90000411", "90000412"
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code=center, sa2_name="Centre", state="QLD", adjacent_sa2_codes=[n1, n2]))
        _seed_accelerating_stats(session, "nb1", n1)
        _seed_accelerating_stats(session, "nb2", n2)
        await session.commit()

        result = await fetch_neighborhood_momentum(session, center)

    assert result["total_neighbors"] == 2
    assert result["counts"]["accelerating"] == 2
    assert result["signal"] == "surrounded_by_acceleration"


@pytest.mark.asyncio
async def test_fetch_neighborhood_momentum_mixed_neighbors_no_signal():
    center, n1, n2 = "90000420", "90000421", "90000422"
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code=center, sa2_name="Centre", state="QLD", adjacent_sa2_codes=[n1, n2]))
        _seed_accelerating_stats(session, "nb3", n1)
        _seed_cooling_stats(session, "nb4", n2)
        await session.commit()

        result = await fetch_neighborhood_momentum(session, center)

    assert result["total_neighbors"] == 2
    assert result["signal"] is None


@pytest.mark.asyncio
async def test_fetch_neighborhood_momentum_no_adjacency_data():
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code="90000430", sa2_name="Isolated", state="QLD"))
        await session.commit()

        result = await fetch_neighborhood_momentum(session, "90000430")

    assert result["total_neighbors"] == 0
    assert result["signal"] is None


@pytest.mark.asyncio
async def test_fetch_neighborhood_momentum_missing_sa2_returns_empty():
    async with AsyncSessionLocal() as session:
        result = await fetch_neighborhood_momentum(session, "99999996")

    assert result["total_neighbors"] == 0
    assert result["signal"] is None
