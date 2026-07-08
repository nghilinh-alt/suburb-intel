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
async def test_fetch_pois_empty_when_none_nearby():
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code="71000003", sa2_name="Isolated", state="QLD"))
        await session.commit()

        result = await fetch_points_of_interest(session, "71000003")

    assert result == {"local": [], "nearby": []}
