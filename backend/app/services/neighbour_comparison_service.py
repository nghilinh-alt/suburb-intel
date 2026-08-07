"""Compares a suburb's headline market metrics against its immediate
neighbours — the adjacent SA2s already precomputed on
`SA2Region.adjacent_sa2_codes` (the same source the Points of Interest
"nearby" list uses). This answers the question a buyer actually asks —
"is this dearer or cheaper than the suburbs next door?" — which the
national-median ruler on its own can't.

Metrics are PropRadar's latest-period suburb-level figures from
`SuburbMarketStats`. A single SA2 can hold more than one real suburb row
(a combined SA2 like "Rochedale - Burbank" — see
suburb_market_stats_loader.py); those are averaged to one figure per SA2
for this side-by-side, mirroring how the rest of the report treats an SA2
as "the suburb". Distances are straight-line km between SA2 centroids,
using the same haversine helper as points_of_interest_service.
"""

from __future__ import annotations

from statistics import mean
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.geo import centroid_from_geojson, haversine_km
from app.db.models import SA2Region, SuburbMarketStats

# (field, label, format, higher_is_better). `higher_is_better` drives the
# frontend's good/bad colouring; None = neutral (a dearer median isn't
# inherently better or worse), matching the ContextRuler convention.
_METRICS: List[Tuple[str, str, str, Optional[bool]]] = [
    ("median_house_price", "Median Price", "currency", None),
    ("gross_yield_house_pct", "Gross Yield", "pct", True),
    ("days_on_market_house", "Days on Market", "days", False),
]

# Cap on how many neighbours to show alongside the subject — enough for
# context without turning the section into a wall of near-identical rows.
_MAX_NEIGHBOURS = 6


async def fetch_neighbour_comparison(db: AsyncSession, sa2_code: str) -> Optional[Dict[str, Any]]:
    """Return ``{"subject_sa2_code", "metrics", "suburbs"}`` comparing this
    suburb to its adjacent SA2s, or ``None`` when there's nothing meaningful
    to compare (no adjacency, or no market data to anchor on)."""
    subject = await db.get(SA2Region, sa2_code)
    if subject is None:
        return None

    adjacent_codes = [c for c in (subject.adjacent_sa2_codes or []) if c != sa2_code]
    if not adjacent_codes:
        return None

    all_codes = [sa2_code, *adjacent_codes]

    region_rows = (
        await db.execute(
            select(SA2Region.sa2_code, SA2Region.sa2_name, SA2Region.geometry_geojson).where(
                SA2Region.sa2_code.in_(all_codes)
            )
        )
    ).all()
    name_by_code = {code: name for code, name, _ in region_rows}
    centroid_by_code = {code: centroid_from_geojson(geo) for code, _, geo in region_rows}
    origin = centroid_by_code.get(sa2_code)

    stats_by_code = await _latest_metrics_by_sa2(db, all_codes)
    # Without market data for the subject there's nothing to anchor the
    # comparison on, so we surface nothing rather than a table of neighbours.
    if sa2_code not in stats_by_code:
        return None

    metric_keys = [k for k, _, _, _ in _METRICS]
    suburbs: List[Dict[str, Any]] = []
    for code in all_codes:
        values = stats_by_code.get(code)
        if not values or all(values.get(k) is None for k in metric_keys):
            continue
        entry: Dict[str, Any] = {
            "sa2_code": code,
            "name": name_by_code.get(code) or code,
            "is_subject": code == sa2_code,
            "distance_km": None,
            "values": {k: values.get(k) for k in metric_keys},
        }
        dest = centroid_by_code.get(code)
        if code != sa2_code and origin is not None and dest is not None:
            entry["distance_km"] = round(haversine_km(origin, dest), 1)
        suburbs.append(entry)

    # Subject plus at least one neighbour is the minimum for a comparison.
    if len(suburbs) < 2:
        return None

    # Subject first, then neighbours nearest-first (unknown distance last).
    suburbs.sort(
        key=lambda s: (not s["is_subject"], s["distance_km"] is None, s["distance_km"] or 0.0)
    )
    suburbs = [suburbs[0], *suburbs[1 : 1 + _MAX_NEIGHBOURS]]

    metrics_meta = [
        {"key": k, "label": label, "format": fmt, "higher_is_better": higher_is_better}
        for k, label, fmt, higher_is_better in _METRICS
    ]
    return {"subject_sa2_code": sa2_code, "metrics": metrics_meta, "suburbs": suburbs}


async def _latest_metrics_by_sa2(
    db: AsyncSession, sa2_codes: List[str]
) -> Dict[str, Dict[str, Any]]:
    """Latest-period value of each comparison metric per SA2, averaged across
    whatever real suburbs that SA2 contains. Only the comparison metrics are
    selected. `period` is a sortable 'YYYY-MM' string, so a descending sort
    puts the newest snapshot first per (sa2_code, suburb_name)."""
    metric_keys = [k for k, _, _, _ in _METRICS]
    columns = [
        SuburbMarketStats.sa2_code,
        SuburbMarketStats.suburb_name,
        SuburbMarketStats.period,
        *[getattr(SuburbMarketStats, k) for k in metric_keys],
    ]
    stmt = (
        select(*columns)
        .where(SuburbMarketStats.sa2_code.in_(sa2_codes))
        .order_by(SuburbMarketStats.period.desc())
    )
    rows = (await db.execute(stmt)).all()

    latest: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        code, suburb_name = row[0], row[1]
        key = (code, suburb_name)
        if key in latest:
            continue  # already have this suburb's newest snapshot
        latest[key] = dict(zip(metric_keys, row[3:]))

    per_sa2: Dict[str, Dict[str, List[float]]] = {}
    for (code, _suburb_name), values in latest.items():
        bucket = per_sa2.setdefault(code, {k: [] for k in metric_keys})
        for k in metric_keys:
            v = values.get(k)
            if v is not None:
                bucket[k].append(v)

    return {
        code: {k: (round(mean(vals), 2) if vals else None) for k, vals in buckets.items()}
        for code, buckets in per_sa2.items()
    }
