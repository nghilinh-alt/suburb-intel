"""State-wide percentile ranking for average school ICSEA (e.g. "Top 8% of QLD").

Depends on `abs_census_metrics.avg_school_icsea`, populated by
school_icsea_loader.py — which itself depends on ACARA's "School ICSEA
Scores" file, gated behind commercial-use terms not yet accepted (see that
loader's docstring). Returns None until that data exists; no ranking is
fabricated from proxy data (e.g. SEIFA) in the meantime.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ABSCEntensMetrics, SA2Region

_MIN_SAMPLE_SIZE = 5  # below this, a percentile isn't meaningful
_CENSUS_YEAR = 2021


async def fetch_school_percentile(db: AsyncSession, sa2_code: str) -> Optional[Dict[str, Any]]:
    """Return this SA2's avg_school_icsea percentile rank within its state,
    or None if the underlying ICSEA data isn't loaded (or the sample is too
    small to rank meaningfully)."""
    region = await db.get(SA2Region, sa2_code)
    if region is None:
        return None

    metrics = await db.get(ABSCEntensMetrics, (sa2_code, _CENSUS_YEAR))
    if metrics is None or metrics.avg_school_icsea is None:
        return None

    stmt = (
        select(ABSCEntensMetrics.avg_school_icsea)
        .join(SA2Region, SA2Region.sa2_code == ABSCEntensMetrics.sa2_code)
        .where(
            SA2Region.state == region.state,
            ABSCEntensMetrics.year == _CENSUS_YEAR,
            ABSCEntensMetrics.avg_school_icsea.isnot(None),
        )
    )
    values = [row[0] for row in (await db.execute(stmt)).all()]
    if len(values) < _MIN_SAMPLE_SIZE:
        return None

    below_or_equal = sum(1 for v in values if v <= metrics.avg_school_icsea)
    percentile = below_or_equal / len(values) * 100
    top_pct = max(round(100 - percentile), 1)

    return {
        "avg_icsea": metrics.avg_school_icsea,
        "state": region.state,
        "percentile": round(percentile, 1),
        "top_pct_label": f"Top {top_pct}% of {region.state}",
        "sample_size": len(values),
    }
