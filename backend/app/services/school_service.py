"""Local + nearby school lookups for the suburb report's Schools section.

Merges two sources without duplicating entries:
  - SchoolRating (ACARA): every K-12 school, with sector (public/private)
    and ACARA's own ICSEA percentile — this is the rated list.
  - LocalSchool (Overture): only levels ACARA doesn't cover (early
    childhood, university/college, vocational/TAFE) — these have no rating.

"Nearby" means SA2s adjacent to this one (see `adjacent_sa2_codes`,
precomputed once by school_locations_loader.py) — not literal distance, but
a reasonable proxy for "surrounding suburbs" without expensive geometry ops
on every request.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import LocalSchool, SA2Region, SchoolRating

# Overture's LocalSchool levels that ACARA's K-12 ratings already cover —
# excluded from the Overture side to avoid showing the same school twice.
_ACARA_COVERED_LEVELS = {"Primary School", "Middle School", "Secondary School", "School"}

_SECTOR_LABEL = {1: "Public", 0: "Private"}


async def fetch_schools(db: AsyncSession, sa2_code: str) -> Dict[str, List[Dict[str, Any]]]:
    """Return {"local": [...], "nearby": [...]} school lists for this SA2."""
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
    rated_stmt = select(
        SchoolRating.name,
        SchoolRating.school_type,
        SchoolRating.is_public,
        SchoolRating.icsea_percentile,
        SchoolRating.sa2_code,
    ).where(SchoolRating.sa2_code.in_(sa2_codes))

    suburb_by_sa2: Dict[str, str] = {}
    if with_suburb:
        rows = (await db.execute(select(SA2Region.sa2_code, SA2Region.sa2_name).where(SA2Region.sa2_code.in_(sa2_codes)))).all()
        suburb_by_sa2 = dict(rows)

    entries: List[Dict[str, Any]] = []
    for name, school_type, is_public, icsea_percentile, row_sa2 in (await db.execute(rated_stmt)).all():
        entry = {
            "name": name,
            "level": school_type,
            "sector": _SECTOR_LABEL.get(is_public),
            "icsea_percentile": icsea_percentile,
        }
        if with_suburb:
            entry["suburb"] = suburb_by_sa2.get(row_sa2)
        entries.append(entry)

    unrated_stmt = (
        select(LocalSchool.name, LocalSchool.level, LocalSchool.sa2_code)
        .where(LocalSchool.sa2_code.in_(sa2_codes), LocalSchool.level.notin_(_ACARA_COVERED_LEVELS))
    )
    for name, level, row_sa2 in (await db.execute(unrated_stmt)).all():
        entry = {"name": name, "level": level, "sector": None, "icsea_percentile": None}
        if with_suburb:
            entry["suburb"] = suburb_by_sa2.get(row_sa2)
        entries.append(entry)

    entries.sort(key=lambda e: (e["level"] or "", e["name"]))
    return entries
