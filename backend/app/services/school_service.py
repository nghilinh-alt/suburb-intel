"""Local + nearby school lookups for the suburb report's Schools section.

Only shows ACARA-rated K-12 schools — sector (public/private) and ICSEA
percentile both required, so unrated entries (Overture-only early
childhood/university/vocational places, which never have a sector or
percentile) don't appear here.

"Nearby" means SA2s adjacent to this one (see `adjacent_sa2_codes`,
precomputed once by school_locations_loader.py) — not literal distance, but
a reasonable proxy for "surrounding suburbs" without expensive geometry ops
on every request. Capped and sorted by percentile descending (best schools
first) since — unlike points_of_interest_service.py's POIs — ICSEA
percentile is a real, meaningful ranking signal to curate by, not just an
arbitrary cap.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SA2Region, SchoolRating

_SECTOR_LABEL = {1: "Public", 0: "Private"}
_MAX_NEARBY = 10


async def fetch_schools(db: AsyncSession, sa2_code: str) -> Dict[str, List[Dict[str, Any]]]:
    """Return {"local": [...], "nearby": [...]} school lists for this SA2."""
    local = await _fetch_for_sa2(db, [sa2_code])

    region = await db.get(SA2Region, sa2_code)
    adjacent_codes = region.adjacent_sa2_codes if region else None
    if not adjacent_codes:
        return {"local": local, "nearby": []}

    nearby = (await _fetch_for_sa2(db, adjacent_codes, with_suburb=True))[:_MAX_NEARBY]
    return {"local": local, "nearby": nearby}


async def _fetch_for_sa2(
    db: AsyncSession, sa2_codes: List[str], *, with_suburb: bool = False
) -> List[Dict[str, Any]]:
    stmt = select(
        SchoolRating.name,
        SchoolRating.school_type,
        SchoolRating.is_public,
        SchoolRating.icsea_percentile,
        SchoolRating.sa2_code,
    ).where(
        SchoolRating.sa2_code.in_(sa2_codes),
        SchoolRating.is_public.isnot(None),
        SchoolRating.icsea_percentile.isnot(None),
    )

    suburb_by_sa2: Dict[str, str] = {}
    if with_suburb:
        rows = (await db.execute(select(SA2Region.sa2_code, SA2Region.sa2_name).where(SA2Region.sa2_code.in_(sa2_codes)))).all()
        suburb_by_sa2 = dict(rows)

    entries: List[Dict[str, Any]] = []
    for name, school_type, is_public, icsea_percentile, row_sa2 in (await db.execute(stmt)).all():
        entry = {
            "name": name,
            "level": school_type,
            "sector": _SECTOR_LABEL.get(is_public),
            "icsea_percentile": icsea_percentile,
        }
        if with_suburb:
            entry["suburb"] = suburb_by_sa2.get(row_sa2)
        entries.append(entry)

    entries.sort(key=lambda e: e["icsea_percentile"], reverse=True)
    return entries
