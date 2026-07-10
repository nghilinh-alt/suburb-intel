"""Tests for points_of_interest_service — local vs adjacent-SA2 ("nearby")
POI lists, including the best-effort public/private hospital tag."""

from __future__ import annotations

import pytest

from app.db.models import PointOfInterest, SA2Region
from app.db.session import AsyncSessionLocal
from app.services.points_of_interest_service import fetch_points_of_interest


@pytest.mark.asyncio
async def test_fetch_pois_splits_local_and_nearby_with_hospital_type():
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code="71000001", sa2_name="Home Suburb", state="QLD", adjacent_sa2_codes=["71000002"]))
        session.add(SA2Region(sa2_code="71000002", sa2_name="Next Door", state="QLD"))
        session.add(PointOfInterest(
            id="p1", name="Home Public Hospital", category="hospital", group_label="Hospital",
            is_public_hospital=1, lat=-27.0, lon=153.0, sa2_code="71000001",
        ))
        session.add(PointOfInterest(
            id="p2", name="Westfield Home", category="shopping_mall", group_label="Shopping Centre",
            is_public_hospital=None, lat=-27.0, lon=153.0, sa2_code="71000001",
        ))
        session.add(PointOfInterest(
            id="p3", name="Next Door Private Hospital", category="hospital", group_label="Hospital",
            is_public_hospital=0, lat=-27.1, lon=153.1, sa2_code="71000002",
        ))
        await session.commit()

        result = await fetch_points_of_interest(session, "71000001")

    assert result["local"] == [
        {"name": "Home Public Hospital", "group": "Hospital", "hospital_type": "Public"},
        {"name": "Westfield Home", "group": "Shopping Centre", "hospital_type": None},
    ]
    assert result["nearby"] == [
        {"name": "Next Door Private Hospital", "group": "Hospital", "hospital_type": "Private", "suburb": "Next Door"},
    ]


@pytest.mark.asyncio
async def test_fetch_pois_dedupes_case_insensitive_same_name_same_group():
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code="71000004", sa2_name="Dupe Suburb", state="QLD"))
        session.add(PointOfInterest(
            id="d1", name="Westfield Dupe", category="shopping_center", group_label="Shopping Centre",
            is_public_hospital=None, lat=-27.0, lon=153.0, sa2_code="71000004",
        ))
        session.add(PointOfInterest(
            id="d2", name="westfield dupe", category="shopping_center", group_label="Shopping Centre",
            is_public_hospital=None, lat=-27.0001, lon=153.0001, sa2_code="71000004",
        ))
        await session.commit()

        result = await fetch_points_of_interest(session, "71000004")

    assert len(result["local"]) == 1


@pytest.mark.asyncio
async def test_fetch_pois_caps_each_group_at_max():
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code="71000005", sa2_name="Busy Suburb", state="QLD"))
        for i in range(8):
            session.add(PointOfInterest(
                id=f"cap{i}", name=f"Museum {i}", category="museum", group_label="Attraction",
                is_public_hospital=None, lat=-27.0, lon=153.0, sa2_code="71000005",
            ))
        await session.commit()

        result = await fetch_points_of_interest(session, "71000005")

    assert len(result["local"]) == 5


@pytest.mark.asyncio
async def test_fetch_pois_empty_when_none_nearby():
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code="71000003", sa2_name="Isolated", state="QLD"))
        await session.commit()

        result = await fetch_points_of_interest(session, "71000003")

    assert result == {"local": [], "nearby": []}


@pytest.mark.asyncio
async def test_nearby_pois_get_distance_km_from_home_suburb_centroid():
    # A small square polygon centred on (-27.0, 153.0).
    home_geojson = (
        '{"type": "Polygon", "coordinates": [[[152.99, -27.01], [153.01, -27.01], '
        '[153.01, -26.99], [152.99, -26.99], [152.99, -27.01]]]}'
    )
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(
            sa2_code="71000006", sa2_name="Home With Geometry", state="QLD",
            adjacent_sa2_codes=["71000007"], geometry_geojson=home_geojson,
        ))
        session.add(SA2Region(sa2_code="71000007", sa2_name="Neighbour", state="QLD"))
        # ~11.1km due south of the (-27.0, 153.0) centroid.
        session.add(PointOfInterest(
            id="dist1", name="Southern Museum", category="museum", group_label="Attraction",
            is_public_hospital=None, lat=-27.1, lon=153.0, sa2_code="71000007",
        ))
        await session.commit()

        result = await fetch_points_of_interest(session, "71000006")

    assert len(result["nearby"]) == 1
    assert result["nearby"][0]["distance_km"] == pytest.approx(11.1, abs=0.2)
