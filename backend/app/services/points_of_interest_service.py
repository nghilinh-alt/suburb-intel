"""Local + nearby points-of-interest lookups (hospitals, shopping centres,
stadiums/arenas, attractions) for the suburb report's Points of Interest
section. Same local/adjacent-SA2 "nearby" pattern as school_service.py.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PointOfInterest, SA2Region


async def fetch_points_of_interest(db: AsyncSession, sa2_code: str) -> Dict[str, List[Dict[str, Any]]]:
    """Return {"local": [...], "nearby": [...]} POI lists for this SA2."""
    local = await _fetch_for_sa2(db, [sa2_code])

    region = await db.get(SA2Region, sa2_code)
    adjacent_codes = region.adjacent_sa2_codes if region else None
    if not adjacent_codes:
        return {"local": local, "nearby": []}

    nearby = await _fetch_for_sa2(db, adjacent_codes, with_suburb=True)
    return {"local": local, "nearby": nearby}


async def _fetch_for_sa2(
    db: AsyncSession, sa2_codes: List[str], *, with_suburb: bool = False
) -> List[Dict[str, Any]]:
    stmt = select(
        PointOfInterest.name,
        PointOfInterest.group_label,
        PointOfInterest.is_public_hospital,
        PointOfInterest.sa2_code,
    ).where(PointOfInterest.sa2_code.in_(sa2_codes))

    suburb_by_sa2: Dict[str, str] = {}
    if with_suburb:
        rows = (await db.execute(select(SA2Region.sa2_code, SA2Region.sa2_name).where(SA2Region.sa2_code.in_(sa2_codes)))).all()
        suburb_by_sa2 = dict(rows)

    entries: List[Dict[str, Any]] = []
    for name, group_label, is_public_hospital, row_sa2 in (await db.execute(stmt)).all():
        entry: Dict[str, Any] = {
            "name": name,
            "group": group_label,
            "hospital_type": (
                {1: "Public", 0: "Private"}.get(is_public_hospital) if is_public_hospital is not None else None
            ),
        }
        if with_suburb:
            entry["suburb"] = suburb_by_sa2.get(row_sa2)
        entries.append(entry)

    entries.sort(key=lambda e: (e["group"] or "", e["name"]))
    return entries
