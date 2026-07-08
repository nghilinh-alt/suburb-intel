"""Compares a suburb's key metrics against its local city/regional average.

Uses `sa4_name` as the grouping geography. ABS's proper "Greater Capital
City" level (`gcc_code`/`gcc_name` on SA2Region) was intentionally left NULL
during Phase A ingestion (see docs/PHASE_A_PLAN.md) and was never populated,
so it's not usable here.

For the five SA4-split capital cities (Sydney, Melbourne, Brisbane, Perth,
Adelaide), we aggregate across every SA4 sharing that city name as a prefix
(e.g. "Brisbane - East", "Brisbane - North", "Brisbane Inner City" all roll
up to "Brisbane"). Everywhere else uses its own single SA4 as the region —
note this is coarser than an actual town: Rockhampton itself doesn't have
its own SA4, it's part of the "Central Queensland" SA4, so a Rockhampton
suburb's comparison is honestly labeled "Central Queensland", not
"Rockhampton". Non-substantive SA4 categories (migratory/no-fixed-address
pseudo-regions) are excluded entirely — per the brief, "if no local city,
leave this out."
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ABSCEntensMetrics, SA2Region

_CAPITAL_CITY_PREFIXES = ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"]
_EXCLUDED_SA4_SUBSTRINGS = ("migratory", "no usual address")

_COMPARISON_METRICS = [
    ("median_income", "Median Income", "currency"),
    ("renters_pct", "Renters", "pct"),
    ("owners_pct", "Owners", "pct"),
    ("unemployment_pct", "Unemployment Rate", "pct"),
    ("median_rent_weekly", "Median Weekly Rent", "currency"),
    ("uni_degree_pct", "University Educated", "pct"),
]


async def fetch_regional_comparison(db: AsyncSession, sa2_code: str) -> Optional[Dict[str, Any]]:
    """Return {"region_label": str, "metrics": [...]} or None if this SA2 has
    no meaningful local city/region to compare against."""
    region_row = (
        await db.execute(select(SA2Region.sa4_name, SA2Region.state).where(SA2Region.sa2_code == sa2_code))
    ).first()
    if region_row is None or region_row.sa4_name is None:
        return None

    sa4_name, state = region_row
    if any(pattern in sa4_name.lower() for pattern in _EXCLUDED_SA4_SUBSTRINGS):
        return None

    city_prefix = next((c for c in _CAPITAL_CITY_PREFIXES if sa4_name.lower().startswith(c.lower())), None)
    if city_prefix:
        region_label = city_prefix
        sa4_filter = SA2Region.sa4_name.ilike(f"{city_prefix}%")
    else:
        region_label = sa4_name
        sa4_filter = SA2Region.sa4_name == sa4_name

    columns = [getattr(ABSCEntensMetrics, col) for col, _, _ in _COMPARISON_METRICS]

    suburb_row = (
        await db.execute(
            select(*columns).where(ABSCEntensMetrics.sa2_code == sa2_code, ABSCEntensMetrics.year == 2021)
        )
    ).first()
    if suburb_row is None:
        return None

    avg_columns = [func.avg(getattr(ABSCEntensMetrics, col)) for col, _, _ in _COMPARISON_METRICS]
    region_row = (
        await db.execute(
            select(*avg_columns)
            .select_from(ABSCEntensMetrics)
            .join(SA2Region, SA2Region.sa2_code == ABSCEntensMetrics.sa2_code)
            .where(SA2Region.state == state, sa4_filter, ABSCEntensMetrics.year == 2021)
        )
    ).first()

    metrics: List[Dict[str, Any]] = []
    for i, (col, label, fmt) in enumerate(_COMPARISON_METRICS):
        suburb_value = suburb_row[i]
        region_value = region_row[i]
        if suburb_value is None or region_value is None:
            continue
        metrics.append(
            {
                "key": col,
                "label": label,
                "format": fmt,
                "suburb_value": suburb_value,
                "region_average": round(region_value, 2),
            }
        )

    if not metrics:
        return None

    return {"region_label": region_label, "metrics": metrics}
