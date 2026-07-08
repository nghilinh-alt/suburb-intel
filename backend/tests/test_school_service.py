"""Tests for school_service — merges ACARA's rated K-12 schools (SchoolRating)
with Overture's unrated entries (LocalSchool: early childhood/uni/vocational
only, since ACARA already covers K-12), split into local vs adjacent-SA2
("nearby") lists.
"""

from __future__ import annotations

import pytest

from app.db.models import LocalSchool, SA2Region, SchoolRating
from app.db.session import AsyncSessionLocal
from app.services.school_service import fetch_schools


@pytest.mark.asyncio
async def test_fetch_schools_merges_rated_and_unrated_without_duplication():
    async with AsyncSessionLocal() as session:
        session.add(SA2Region(sa2_code="70000001", sa2_name="Home Suburb", state="QLD", adjacent_sa2_codes=["70000002"]))
        session.add(SA2Region(sa2_code="70000002", sa2_name="Next Door", state="QLD"))
        # Rated K-12 school (ACARA)
        session.add(SchoolRating(
            id="r1", name="Home Primary", suburb="Home Suburb", state="QLD",
            sector="Government", is_public=1, school_type="Primary",
            icsea=1050.0, icsea_percentile=68.0, sa2_code="70000001",
        ))
        # Unrated early-childhood (Overture) — should still show up
        session.add(LocalSchool(id="sch1", name="Home Kindy", level="Early Childhood", lat=-27.0, lon=153.0, sa2_code="70000001"))
        # An Overture "Primary School" duplicate of the rated one — must be excluded
        session.add(LocalSchool(id="sch2", name="Home Primary (Overture dup)", level="Primary School", lat=-27.0, lon=153.0, sa2_code="70000001"))
        # Nearby rated school
        session.add(SchoolRating(
            id="r2", name="Next Door High", suburb="Next Door", state="QLD",
            sector="Independent", is_public=0, school_type="Secondary",
            icsea=1120.0, icsea_percentile=88.0, sa2_code="70000002",
        ))
        await session.commit()

        result = await fetch_schools(session, "70000001")

    assert result["local"] == [
        {"name": "Home Kindy", "level": "Early Childhood", "sector": None, "icsea_percentile": None},
        {"name": "Home Primary", "level": "Primary", "sector": "Public", "icsea_percentile": 68.0},
    ]
    assert result["nearby"] == [
        {"name": "Next Door High", "level": "Secondary", "sector": "Private", "icsea_percentile": 88.0, "suburb": "Next Door"},
    ]


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
