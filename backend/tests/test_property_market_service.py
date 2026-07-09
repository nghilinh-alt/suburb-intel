"""Tests for property_market_service's aggregation logic, using synthetic
PropertySale rows since no PropRadar ingestion has run yet (subscription
reactivation pending — see propradar_sold_loader.py docstring)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.db.models import PropertySale
from app.db.session import AsyncSessionLocal
from app.services.property_market_service import (
    fetch_detailed_specs,
    fetch_house_type_breakdown,
    fetch_land_size_breakdown,
    fetch_price_history,
    fetch_price_history_by_spec,
)

async def _seed_sale(session, id_, sa2_code, *, bedrooms=None, bathrooms=None, parking=None, property_type=None, sold_price=None, sold_date=None, land_size_sqm=None):
    session.add(
        PropertySale(
            id=id_,
            sa2_code=sa2_code,
            address=f"{id_} Test St",
            state="QLD",
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            parking=parking,
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
async def test_house_type_breakdown_normalizes_real_propradar_type_synonyms():
    """PropRadar's real property_type values (verified against a live pilot
    pull) are far more varied than house/unit/townhouse — apartment/unit/flat
    should share one bucket set, and villa/duplex get their own labels
    rather than a raw per-bedroom-count fallback."""
    sa2 = "90000006"
    async with AsyncSessionLocal() as session:
        await _seed_sale(session, "syn1", sa2, property_type="apartment", bedrooms=2, sold_price=500_000, sold_date="2025-01-01")
        await _seed_sale(session, "syn2", sa2, property_type="unit", bedrooms=2, sold_price=520_000, sold_date="2025-01-02")
        await _seed_sale(session, "syn3", sa2, property_type="flat", bedrooms=2, sold_price=540_000, sold_date="2025-01-03")
        await _seed_sale(session, "syn4", sa2, property_type="villa", bedrooms=3, sold_price=700_000, sold_date="2025-01-04")
        await _seed_sale(session, "syn5", sa2, property_type="duplex+semi detached", bedrooms=3, sold_price=750_000, sold_date="2025-01-05")
        await _seed_sale(session, "syn6", sa2, property_type="residential+land", bedrooms=4, sold_price=900_000, sold_date="2025-01-06")
        await session.commit()

        breakdown = await fetch_house_type_breakdown(session, sa2)

    labels = {b["label"]: b for b in breakdown}
    assert labels["2 Bed Apartment"]["sale_count"] == 3  # apartment + unit + flat merged
    assert labels["2-4 Bed Villa"]["sale_count"] == 1
    assert labels["2-4 Bed Duplex/Semi-Detached"]["sale_count"] == 1
    assert labels["4 Bed Residential+Land"]["sale_count"] == 1  # unrecognized type — plain fallback


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


@pytest.mark.asyncio
async def test_detailed_specs_buckets_by_exact_bed_bath_parking_combo():
    sa2 = "90000007"
    async with AsyncSessionLocal() as session:
        await _seed_sale(session, "d1", sa2, property_type="apartment", bedrooms=2, bathrooms=1, parking=1, sold_price=500_000, sold_date="2025-01-01")
        await _seed_sale(session, "d2", sa2, property_type="apartment", bedrooms=2, bathrooms=1, parking=1, sold_price=520_000, sold_date="2025-01-02")
        # Same bed/type but different bathroom count — must be a separate bucket
        await _seed_sale(session, "d3", sa2, property_type="apartment", bedrooms=2, bathrooms=2, parking=1, sold_price=600_000, sold_date="2025-01-03")
        await _seed_sale(session, "d4", sa2, property_type="house", bedrooms=5, bathrooms=3, parking=2, sold_price=1_500_000, sold_date="2025-01-04")
        await session.commit()

        specs = await fetch_detailed_specs(session, sa2)

    labels = {s["label"]: s for s in specs}
    assert labels["2 Bed / 1 Bath / 1 Garage Apartment"]["sale_count"] == 2
    assert labels["2 Bed / 1 Bath / 1 Garage Apartment"]["median_price"] == 510_000
    assert labels["2 Bed / 2 Bath / 1 Garage Apartment"]["sale_count"] == 1
    assert labels["5 Bed / 3 Bath / 2 Garage House"]["sale_count"] == 1
    assert labels["5 Bed / 3 Bath / 2 Garage House"]["median_price"] == 1_500_000


@pytest.mark.asyncio
async def test_detailed_specs_omits_garage_when_parking_unknown():
    sa2 = "90000008"
    async with AsyncSessionLocal() as session:
        await _seed_sale(session, "d5", sa2, property_type="house", bedrooms=3, bathrooms=1, parking=None, sold_price=700_000, sold_date="2025-01-01")
        await session.commit()

        specs = await fetch_detailed_specs(session, sa2)

    assert specs == [{"label": "3 Bed / 1 Bath House", "median_price": 700_000, "sale_count": 1}]


@pytest.mark.asyncio
async def test_detailed_specs_skips_rows_missing_bathrooms():
    sa2 = "90000009"
    async with AsyncSessionLocal() as session:
        await _seed_sale(session, "d6", sa2, property_type="house", bedrooms=3, bathrooms=None, sold_price=700_000, sold_date="2025-01-01")
        await session.commit()

        specs = await fetch_detailed_specs(session, sa2)

    assert specs == []


@pytest.mark.asyncio
async def test_detailed_specs_sorted_progressively_by_bed_bath_not_popularity():
    sa2 = "90000010"
    async with AsyncSessionLocal() as session:
        # Seeded out of order and with mismatched popularity, to prove sort
        # isn't by sale_count: 2 Bed/1 Bath has 3 sales (most popular) but
        # must still come after 1 Bed/2 Bath in the progressive ordering.
        await _seed_sale(session, "o1", sa2, property_type="apartment", bedrooms=2, bathrooms=1, parking=1, sold_price=500_000, sold_date="2025-01-01")
        await _seed_sale(session, "o2", sa2, property_type="apartment", bedrooms=2, bathrooms=1, parking=1, sold_price=500_000, sold_date="2025-01-02")
        await _seed_sale(session, "o3", sa2, property_type="apartment", bedrooms=2, bathrooms=1, parking=1, sold_price=500_000, sold_date="2025-01-03")
        await _seed_sale(session, "o4", sa2, property_type="apartment", bedrooms=1, bathrooms=2, parking=1, sold_price=400_000, sold_date="2025-01-01")
        await _seed_sale(session, "o5", sa2, property_type="apartment", bedrooms=1, bathrooms=1, parking=1, sold_price=380_000, sold_date="2025-01-01")
        await session.commit()

        specs = await fetch_detailed_specs(session, sa2)

    assert [s["label"] for s in specs] == [
        "1 Bed / 1 Bath / 1 Garage Apartment",
        "1 Bed / 2 Bath / 1 Garage Apartment",
        "2 Bed / 1 Bath / 1 Garage Apartment",
    ]


@pytest.mark.asyncio
async def test_price_history_by_spec_groups_per_spec_and_month():
    sa2 = "90000011"
    async with AsyncSessionLocal() as session:
        await _seed_sale(session, "p1", sa2, property_type="apartment", bedrooms=2, bathrooms=1, parking=1, sold_price=500_000, sold_date="2025-01-15")
        await _seed_sale(session, "p2", sa2, property_type="apartment", bedrooms=2, bathrooms=1, parking=1, sold_price=520_000, sold_date="2025-01-20")
        await _seed_sale(session, "p3", sa2, property_type="apartment", bedrooms=2, bathrooms=1, parking=1, sold_price=600_000, sold_date="2025-02-05")
        # A different spec entirely — must not blend into the 2 Bed/1 Bath history above
        await _seed_sale(session, "p4", sa2, property_type="house", bedrooms=4, bathrooms=2, parking=2, sold_price=1_000_000, sold_date="2025-01-10")
        await session.commit()

        by_spec = await fetch_price_history_by_spec(session, sa2)

    entries = {e["label"]: e for e in by_spec}
    assert entries["2 Bed / 1 Bath / 1 Garage Apartment"]["history"] == [
        {"period": "2025-01", "median_price": 510_000, "sale_count": 2},
        {"period": "2025-02", "median_price": 600_000, "sale_count": 1},
    ]
    assert entries["4 Bed / 2 Bath / 2 Garage House"]["history"] == [
        {"period": "2025-01", "median_price": 1_000_000, "sale_count": 1},
    ]
    # 4 Bed House sorts before 2 Bed Apartment under progressive bed/bath ordering? No —
    # bedrooms is the primary sort key, so 2 Bed comes before 4 Bed regardless of type.
    assert [e["label"] for e in by_spec] == [
        "2 Bed / 1 Bath / 1 Garage Apartment",
        "4 Bed / 2 Bath / 2 Garage House",
    ]


@pytest.mark.asyncio
async def test_price_history_by_spec_empty_when_no_data():
    async with AsyncSessionLocal() as session:
        by_spec = await fetch_price_history_by_spec(session, "99999996")
    assert by_spec == []
