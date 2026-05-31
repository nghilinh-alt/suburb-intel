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
    """Return the base suburb name for GROUPING, stripping trailing directional qualifier.

    Used to group SA2s that split ONE suburb: "Keysborough - North" + "Keysborough - South" → "Keysborough".
    Does NOT split genuinely combined SA2s ("Parkinson - Drewvale") — those are handled by _suburb_names().

    "Keysborough - North"        → "Keysborough"
    "Parramatta - South"         → "Parramatta"
    "Perth (West) - Northbridge" → "Perth (West) - Northbridge"  (kept as-is; parenthetical)
    "Parkinson - Drewvale"       → "Parkinson - Drewvale"  (kept as-is; two real suburbs)
    "North Sydney"               → "North Sydney"
    """
    if " - " in sa2_name:
        left, right = sa2_name.rsplit(" - ", 1)
        normalised = right.strip().lower().replace("-", "").replace(" ", "")
        if normalised in {d.replace("-", "") for d in _DIRECTIONAL}:
            return left.strip()
    return sa2_name


def _suburb_names(sa2_name: str) -> list[str]:
    """Return the individual suburb names that should get their own aggregate entry.

    Handles three cases:
    1. Plain single suburb: "Algester" → ["Algester"]
    2. Directional ABS split: "Keysborough - North" → ["Keysborough"]  (grouped with South)
    3. Two distinct suburbs in one SA2: "Parkinson - Drewvale" → ["Parkinson", "Drewvale"]

    Note: SA2s with parenthetical qualifiers like "Perth (West) - Northbridge" stay combined
    because "Perth (West)" is not a suburb name people would search for.
    """
    if " - " not in sa2_name:
        return [sa2_name]

    left, right = sa2_name.rsplit(" - ", 1)
    right_norm = right.strip().lower().replace("-", "").replace(" ", "")

    # Directional suffix → it's ONE suburb split for census size
    if right_norm in {d.replace("-", "") for d in _DIRECTIONAL}:
        return [left.strip()]

    # Parenthetical parts → ABS area subdivision notation, keep combined
    if "(" in left or "(" in right:
        return [sa2_name]

    # Three-suburb SA2s: "Balgowlah - Clontarf - Seaforth"
    # Split all " - " parts (none are directional, none have parentheses)
    parts = [p.strip() for p in sa2_name.split(" - ") if p.strip()]
    # All parts must be non-directional for this to be a multi-suburb SA2
    all_non_directional = all(
        p.lower().replace("-", "").replace(" ", "") not in {d.replace("-", "") for d in _DIRECTIONAL}
        for p in parts
    )
    if all_non_directional and len(parts) > 1:
        return parts

    return [sa2_name]


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

    # Step 1: Group SA2s that are directional splits of ONE suburb (e.g. Keysborough N+S)
    # Key = (base_name, state) — only directional splits share the same base_name
    groups: dict[tuple[str, str], list] = {}
    for row in rows:
        key = (_base_name(row.sa2_name), row.state)
        groups.setdefault(key, []).append(row)

    logger.info("Grouped into %d directional groups", len(groups))

    # Step 2: Expand combined SA2s ("Parkinson - Drewvale") into individual suburb entries.
    # For each group, if the SA2 name represents multiple real suburbs, create one entry
    # per suburb name pointing to the same SA2 data.
    expanded_groups: dict[tuple[str, str], list] = {}
    for (group_name, state), members in groups.items():
        # For single-SA2 groups, expand the SA2 name into individual suburb names
        if len(members) == 1:
            individual_names = _suburb_names(members[0].sa2_name)
            for name in individual_names:
                key = (name, state)
                expanded_groups.setdefault(key, []).extend(members)
        else:
            # Multi-SA2 groups (directional splits like Keysborough N+S) — keep as-is
            expanded_groups.setdefault((group_name, state), []).extend(members)

    logger.info("Expanded to %d suburb entries (including individual suburb names from combined SA2s)", len(expanded_groups))
    groups = expanded_groups

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
