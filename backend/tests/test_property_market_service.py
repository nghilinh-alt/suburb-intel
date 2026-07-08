"""Tests for property_market_service's aggregation logic, using synthetic
PropertySale rows since no PropRadar ingestion has run yet (subscription
reactivation pending — see propradar_sold_loader.py docstring)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db.models import PropertySale
from app.db.session import AsyncSessionLocal
from app.services.property_market_service import (
    fetch_house_type_breakdown,
    fetch_land_size_breakdown,
    fetch_price_history,
)

async def _seed_sale(session, id_, sa2_code, *, bedrooms=None, property_type=None, sold_price=None, sold_date=None, land_size_sqm=None):
    session.add(
        PropertySale(
            id=id_,
            sa2_code=sa2_code,
            address=f"{id_} Test St",
            state="QLD",
            bedrooms=bedrooms,
            property_type=property_type,
            sold_price=sold_price,
            sold_date=sold_date,
            land_size_sqm=land_size_sqm,
            source="propradar",
            fetched_at=datetime.now(timezone.utc),
        )
    )


@pytest.mark.asyncio
async def test_price_history_groups_by_month_and_computes_median():
    sa2 = "90000001"
    async with AsyncSessionLocal() as session:
        await _seed_sale(session, "s1", sa2, sold_price=500_000, sold_date="2025-01-15")
        await _seed_sale(session, "s2", sa2, sold_price=520_000, sold_date="2025-01-20")
        await _seed_sale(session, "s3", sa2, sold_price=600_000, sold_date="2025-02-05")
        await session.commit()

        history = await fetch_price_history(session, sa2)

    assert history == [
        {"period": "2025-01", "median_price": 510_000, "sale_count": 2},
        {"period": "2025-02", "median_price": 600_000, "sale_count": 1},
    ]


@pytest.mark.asyncio
async def test_price_history_empty_when_no_sales():
    async with AsyncSessionLocal() as session:
        history = await fetch_price_history(session, "99999999")
    assert history == []


@pytest.mark.asyncio
async def test_house_type_breakdown_buckets_by_type_and_bedrooms():
    sa2 = "90000002"
    async with AsyncSessionLocal() as session:
        await _seed_sale(session, "h1", sa2, property_type="unit", bedrooms=2, sold_price=400_000, sold_date="2025-01-01")
        await _seed_sale(session, "h2", sa2, property_type="unit", bedrooms=2, sold_price=420_000, sold_date="2025-01-02")
        await _seed_sale(session, "h3", sa2, property_type="house", bedrooms=4, sold_price=800_000, sold_date="2025-01-03")
        await session.commit()

        breakdown = await fetch_house_type_breakdown(session, sa2)

    labels = {b["label"]: b for b in breakdown}
    assert labels["2 Bed Apartment"]["sale_count"] == 2
    assert labels["2 Bed Apartment"]["median_price"] == 410_000
    assert labels["3-5 Bed House"]["sale_count"] == 1
    assert labels["3-5 Bed House"]["median_price"] == 800_000


@pytest.mark.asyncio
async def test_house_type_breakdown_skips_rows_missing_type_or_bedrooms():
    sa2 = "90000003"
    async with AsyncSessionLocal() as session:
        await _seed_sale(session, "x1", sa2, property_type=None, bedrooms=3, sold_price=500_000, sold_date="2025-01-01")
        await _seed_sale(session, "x2", sa2, property_type="house", bedrooms=None, sold_price=500_000, sold_date="2025-01-01")
        await session.commit()

        breakdown = await fetch_house_type_breakdown(session, sa2)

    assert breakdown == []


@pytest.mark.asyncio
async def test_land_size_breakdown_buckets_into_bands():
    sa2 = "90000004"
    async with AsyncSessionLocal() as session:
        await _seed_sale(session, "l1", sa2, sold_price=400_000, sold_date="2025-01-01", land_size_sqm=250)
        await _seed_sale(session, "l2", sa2, sold_price=500_000, sold_date="2025-01-01", land_size_sqm=450)
        await _seed_sale(session, "l3", sa2, sold_price=600_000, sold_date="2025-01-01", land_size_sqm=700)
        await _seed_sale(session, "l4", sa2, sold_price=700_000, sold_date="2025-01-01", land_size_sqm=850)
        await _seed_sale(session, "l5", sa2, sold_price=750_000, sold_date="2025-01-01", land_size_sqm=1200)
        await session.commit()

        breakdown = await fetch_land_size_breakdown(session, sa2)

    counts = {b["label"]: b["sale_count"] for b in breakdown}
    assert counts == {
        "Under 400m²": 1,
        "400-600m²": 1,
        "600-800m²": 1,
        "800m²+": 2,
    }


@pytest.mark.asyncio
async def test_land_size_breakdown_empty_when_no_data():
    async with AsyncSessionLocal() as session:
        breakdown = await fetch_land_size_breakdown(session, "99999998")
    assert breakdown == []
