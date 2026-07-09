"""Tests for school_service — only ACARA-rated K-12 schools (sector +
percentile both required), sorted best-percentile-first, "nearby" (adjacent
SA2s) capped at a reasonable count.
"""

from __future__ import annotations

import pytest

from app.db.models import LocalSchool, SA2Region, SchoolRating
from app.db.session import AsyncSessionLocal
from app.services.school_service import fetch_schools


@pytest.mark.asyncio
async def test_fetch_schools_excludes_unrated_overture_entries():
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code="70000001", sa2_name="Home Suburb", state="QLD", adjacent_sa2_codes=["70000002"]))
        session.add(SA2Region(sa2_code="70000002", sa2_name="Next Door", state="QLD"))
        session.add(SchoolRating(
            id="r1", name="Home Primary", suburb="Home Suburb", state="QLD",
            sector="Government", is_public=1, school_type="Primary",
            icsea=1050.0, icsea_percentile=68.0, sa2_code="70000001",
        ))
        # Unrated early-childhood (Overture) — must NOT show up (no sector/percentile)
        session.add(LocalSchool(id="sch1", name="Home Kindy", level="Early Childhood", lat=-27.0, lon=153.0, sa2_code="70000001"))
        session.add(SchoolRating(
            id="r2", name="Next Door High", suburb="Next Door", state="QLD",
            sector="Independent", is_public=0, school_type="Secondary",
            icsea=1120.0, icsea_percentile=88.0, sa2_code="70000002",
        ))
        await session.commit()

        result = await fetch_schools(session, "70000001")

    assert result["local"] == [
        {"name": "Home Primary", "level": "Primary", "sector": "Public", "icsea_percentile": 68.0},
    ]
    assert result["nearby"] == [
        {"name": "Next Door High", "level": "Secondary", "sector": "Private", "icsea_percentile": 88.0, "suburb": "Next Door"},
    ]


@pytest.mark.asyncio
async def test_fetch_schools_sorted_best_percentile_first():
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code="70000004", sa2_name="Multi School Suburb", state="QLD"))
        session.add(SchoolRating(
            id="m1", name="Lower School", suburb="Multi", state="QLD",
            sector="Government", is_public=1, school_type="Primary",
            icsea=950.0, icsea_percentile=30.0, sa2_code="70000004",
        ))
        session.add(SchoolRating(
            id="m2", name="Higher School", suburb="Multi", state="QLD",
            sector="Independent", is_public=0, school_type="Secondary",
            icsea=1180.0, icsea_percentile=97.0, sa2_code="70000004",
        ))
        await session.commit()

        result = await fetch_schools(session, "70000004")

    assert [s["name"] for s in result["local"]] == ["Higher School", "Lower School"]


@pytest.mark.asyncio
async def test_fetch_schools_nearby_capped_at_ten():
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code="70000005", sa2_name="Home", state="QLD", adjacent_sa2_codes=["70000006"]))
        session.add(SA2Region(sa2_code="70000006", sa2_name="Crowded Neighbour", state="QLD"))
        for i in range(15):
            session.add(SchoolRating(
                id=f"c{i}", name=f"School {i}", suburb="Crowded Neighbour", state="QLD",
                sector="Government", is_public=1, school_type="Primary",
                icsea=1000.0 + i, icsea_percentile=float(i), sa2_code="70000006",
            ))
        await session.commit()

        result = await fetch_schools(session, "70000005")

    assert len(result["nearby"]) == 10
    # Best (highest percentile) should be first
    assert result["nearby"][0]["name"] == "School 14"


@pytest.mark.asyncio
async def test_fetch_schools_empty_when_no_schools_or_adjacency():
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code="70000003", sa2_name="Isolated", state="QLD"))
        await session.commit()

        result = await fetch_schools(session, "70000003")

    assert result == {"local": [], "nearby": []}


@pytest.mark.asyncio
async def test_fetch_schools_unknown_sa2_returns_empty():
    async with AsyncSessionLocal() as session:
        result = await fetch_schools(session, "00000099")
    assert result == {"local": [], "nearby": []}
