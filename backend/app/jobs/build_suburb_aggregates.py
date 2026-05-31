"""Build suburb-level aggregates by grouping SA2s that share a base suburb name.

SA2 names like "Keysborough - North" and "Keysborough - South" both refer to
the same real suburb — the ABS splits them purely for population-size reasons.
This job detects these splits (directional suffix after " - ") and computes
a population-weighted aggregate score for the combined suburb.

Single-SA2 suburbs also get a row (sa2_count=1) so every suburb is queryable
via the suburb_aggregates table without needing to know SA2 codes.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.jobs.build_suburb_aggregates
"""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Directional words that indicate an ABS split of one suburb into multiple SA2s
_DIRECTIONAL = frozenset({
    "north", "south", "east", "west", "central", "inner", "outer",
    "northeast", "northwest", "southeast", "southwest",
    "north-east", "north-west", "south-east", "south-west",
})


def _base_name(sa2_name: str) -> str:
    """Return the base suburb name, stripping trailing ABS directional qualifier.

    "Keysborough - North"        → "Keysborough"
    "Parramatta - South"         → "Parramatta"
    "Perth (West) - Northbridge" → "Perth (West) - Northbridge"  (not directional)
    "Tarneit - North"            → "Tarneit"
    "North Sydney"               → "North Sydney"  (North is part of the name)
    """
    if " - " in sa2_name:
        left, right = sa2_name.rsplit(" - ", 1)
        normalised = right.strip().lower().replace("-", "").replace(" ", "")
        if normalised in {d.replace("-", "") for d in _DIRECTIONAL}:
            return left.strip()
    return sa2_name


def _slug(suburb_name: str, state: str) -> str:
    """URL-safe slug: 'Keysborough' + 'VIC' → 'keysborough-vic'."""
    name_part = re.sub(r"[^a-z0-9]+", "-", suburb_name.lower()).strip("-")
    return f"{name_part}-{state.lower()}"


def _weighted_avg(values: list[tuple[float | None, int]]) -> float | None:
    """Population-weighted average of (score, population) pairs."""
    total_w = total_v = 0.0
    for v, w in values:
        if v is not None and w:
            total_v += v * w
            total_w += w
    return round(total_v / total_w, 3) if total_w > 0 else None


def run_build(db: Session) -> str:
    from app.db.models import SuburbAggregate, Base
    from app.db.session import sync_engine
    Base.metadata.create_all(bind=sync_engine)

    logger.info("Loading SA2 regions + scores + census metrics ...")
    rows = db.execute(text("""
        SELECT
            r.sa2_code, r.sa2_name, r.state,
            m.population,
            m.median_income, m.median_age, m.unemployment_pct,
            m.uni_degree_pct, m.pop_growth_proj_pct,
            s.investment_score, s.liveability_score, s.education_score,
            s.growth_score, s.demographic_score, s.housing_score,
            s.infrastructure_score, s.gentrification_index,
            s.risk_flags, s.score_version
        FROM sa2_regions r
        LEFT JOIN abs_census_metrics m
            ON m.sa2_code = r.sa2_code AND m.year = 2021
        LEFT JOIN suburb_scores s
            ON s.sa2_code = r.sa2_code
        ORDER BY r.state, r.sa2_name
    """)).fetchall()

    logger.info("Loaded %d SA2s", len(rows))

    # Group by (base_name, state)
    groups: dict[tuple[str, str], list] = {}
    for row in rows:
        key = (_base_name(row.sa2_name), row.state)
        groups.setdefault(key, []).append(row)

    logger.info("Grouped into %d suburb entries", len(groups))

    # Clear and rebuild
    db.query(SuburbAggregate).delete(synchronize_session=False)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    written = 0

    for (suburb_name, state), members in groups.items():
        slug = _slug(suburb_name, state)
        sa2_codes  = [m.sa2_code for m in members]
        sa2_names  = [m.sa2_name for m in members]
        total_pop  = sum(m.population or 0 for m in members) or None

        def wavg(attr: str) -> float | None:
            return _weighted_avg([(getattr(m, attr), m.population or 0) for m in members])

        # Union of all risk flags
        all_flags: list[str] = []
        import json
        for m in members:
            flags = m.risk_flags
            if isinstance(flags, str):
                try: flags = json.loads(flags)
                except Exception: flags = []
            for f in (flags or []):
                if f not in all_flags:
                    all_flags.append(f)

        version = next((m.score_version for m in members if m.score_version), None)

        db.add(SuburbAggregate(
            suburb_id    = slug,
            suburb_name  = suburb_name,
            state        = state,
            sa2_codes    = sa2_codes,
            sa2_names    = sa2_names,
            sa2_count    = len(members),
            population   = total_pop,
            investment_score     = wavg("investment_score"),
            liveability_score    = wavg("liveability_score"),
            education_score      = wavg("education_score"),
            growth_score         = wavg("growth_score"),
            demographic_score    = wavg("demographic_score"),
            housing_score        = wavg("housing_score"),
            infrastructure_score = wavg("infrastructure_score"),
            gentrification_index = wavg("gentrification_index"),
            median_income        = wavg("median_income"),
            median_age           = wavg("median_age"),
            unemployment_pct     = wavg("unemployment_pct"),
            uni_degree_pct       = wavg("uni_degree_pct"),
            pop_growth_proj_pct  = wavg("pop_growth_proj_pct"),
            risk_flags   = all_flags,
            score_version = version,
            updated_at   = now,
        ))
        written += 1

    db.commit()
    multi = sum(1 for members in groups.values() if len(members) > 1)
    return (
        f"Suburbs written: {written} | "
        f"Multi-SA2 suburbs: {multi} | "
        f"Single-SA2 suburbs: {written - multi}"
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        result = run_build(db)
        print(f"Done: {result}")
    except Exception:
        logger.exception("Build failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
