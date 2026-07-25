"""Backfill job: compute and store SuburbScore for every SA2 with census data.

Run after loading a DataPack to populate the suburb_scores table so that
/rankings/ and /search/top respond with real data.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.jobs.backfill_scores [--year 2021]
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.momentum import (
    classify_growth_yield_quadrant,
    compute_momentum,
    compute_sale_velocity,
    compute_supply_scarcity,
    summarize_neighborhood_momentum,
)
from app.core.scoring import calculate_investment_score
from app.db.models import ABSCEntensMetrics, PropertySale, SA2Region, SuburbMarketStats, SuburbScore
from app.db.session import AsyncSessionLocal, init_models
from app.services.scoring_service import build_features, fetch_linked_projects

logger = logging.getLogger(__name__)


@dataclass
class BackfillReport:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0

    def __str__(self) -> str:
        return f"inserted={self.inserted}, updated={self.updated}, skipped={self.skipped}"


@dataclass
class _MomentumRow:
    momentum_score: Optional[float] = None
    momentum_phase: Optional[str] = None
    growth_yield_quadrant: Optional[str] = None
    neighborhood_signal: Optional[str] = None
    scarcity_score: Optional[float] = None


async def _compute_momentum_fields(
    db: AsyncSession, regions: List[SA2Region], census_by_sa2: Dict[str, ABSCEntensMetrics]
) -> Dict[str, _MomentumRow]:
    """Momentum/quadrant/neighborhood-signal for every SA2 in `regions`, batch
    fetching each input once (not once per SA2) to keep this a two-query,
    two-pass job over 2000+ suburbs instead of an N+1 crawl:
      Pass 1 computes each SA2's own momentum phase from batch-fetched
      market_stats + sold_dates. Pass 2 rolls each SA2's neighbors' phases
      (looked up from pass 1's in-memory result, no extra queries) into a
      spillover signal via summarize_neighborhood_momentum.

    A SA2 with no suburb_market_stats coverage gets an all-None row — same
    "not enough data yet" contract as the live suburb report.
    """
    all_codes = [r.sa2_code for r in regions]

    # Latest-period market_stats per real suburb, then alphabetically-first
    # real suburb per SA2 — same two-step "pick one representative row"
    # convention as suburb_market_stats_service.fetch_suburb_market_stats
    # and suburb.py's market_stats[0], so this batch score matches what the
    # live suburb report would compute for the same SA2.
    market_rows = (
        await db.execute(
            select(SuburbMarketStats)
            .where(SuburbMarketStats.sa2_code.in_(all_codes))
            .order_by(SuburbMarketStats.sa2_code, SuburbMarketStats.suburb_name, SuburbMarketStats.period.desc())
        )
    ).scalars().all()
    latest_by_suburb_key: Dict[tuple, SuburbMarketStats] = {}
    for s in market_rows:
        latest_by_suburb_key.setdefault((s.sa2_code, s.suburb_name), s)
    stats_by_sa2: Dict[str, SuburbMarketStats] = {}
    for (sa2_code, _suburb_name), stats in sorted(latest_by_suburb_key.items()):
        stats_by_sa2.setdefault(sa2_code, stats)

    sold_by_sa2: Dict[str, List[str]] = defaultdict(list)
    sold_rows = await db.execute(
        select(PropertySale.sa2_code, PropertySale.sold_date).where(
            PropertySale.sa2_code.in_(all_codes), PropertySale.sold_date.isnot(None)
        )
    )
    for sa2_code, sold_date in sold_rows.all():
        sold_by_sa2[sa2_code].append(sold_date)

    # --- Pass 1: each SA2's own momentum ---
    phase_by_sa2: Dict[str, Optional[str]] = {}
    result_by_sa2: Dict[str, _MomentumRow] = {}
    for region in regions:
        code = region.sa2_code
        stats = stats_by_sa2.get(code)
        if stats is None:
            result_by_sa2[code] = _MomentumRow()
            continue

        census = census_by_sa2.get(code)
        velocity = compute_sale_velocity(sold_by_sa2.get(code, []))
        scarcity = compute_supply_scarcity(
            stock_on_market_pct_house=stats.stock_on_market_pct_house,
            stock_on_market_pct_unit=stats.stock_on_market_pct_unit,
            inventory_months_house=stats.inventory_months_house,
            inventory_months_unit=stats.inventory_months_unit,
            building_approvals_1yr=census.building_approvals_1yr if census else None,
            population=census.population if census else None,
        )
        momentum = compute_momentum(
            sale_velocity_trend_pct=velocity["trend_pct"],
            growth_house_1y_pct=stats.growth_house_1y_pct,
            growth_unit_1y_pct=stats.growth_unit_1y_pct,
            scarcity_score=scarcity["scarcity_score"],
            heat_score_house=stats.heat_score_house,
            heat_score_unit=stats.heat_score_unit,
        )
        quadrant = classify_growth_yield_quadrant(
            growth_house_1y_pct=stats.growth_house_1y_pct,
            gross_yield_house_pct=stats.gross_yield_house_pct,
        )
        phase_by_sa2[code] = momentum["phase"]
        result_by_sa2[code] = _MomentumRow(
            momentum_score=momentum["momentum_score"],
            momentum_phase=momentum["phase"],
            growth_yield_quadrant=quadrant["quadrant"],
            scarcity_score=scarcity["scarcity_score"],
        )

    # --- Pass 2: neighborhood signal, purely from pass 1's in-memory phases ---
    for region in regions:
        neighbor_codes = region.adjacent_sa2_codes or []
        neighbor_phases = [phase_by_sa2.get(n) for n in neighbor_codes]
        result_by_sa2[region.sa2_code].neighborhood_signal = summarize_neighborhood_momentum(neighbor_phases)["signal"]

    return result_by_sa2


async def backfill_scores(
    db: AsyncSession,
    *,
    year: int = 2021,
    sa2_codes: Optional[list[str]] = None,
) -> BackfillReport:
    """Compute investment scores for all SA2 regions that have census data for `year`.

    Args:
        db: Async SQLAlchemy session.
        year: Census year to score (default 2021).
        sa2_codes: If given, restrict backfill to these SA2 codes (useful for tests).
    Returns:
        BackfillReport with inserted/updated/skipped counts.
    """
    report = BackfillReport()

    stmt = (
        select(SA2Region, ABSCEntensMetrics)
        .join(
            ABSCEntensMetrics,
            (ABSCEntensMetrics.sa2_code == SA2Region.sa2_code)
            & (ABSCEntensMetrics.year == year),
        )
    )
    if sa2_codes is not None:
        stmt = stmt.where(SA2Region.sa2_code.in_(sa2_codes))

    result = await db.execute(stmt)
    rows = result.all()

    census_by_sa2 = {region.sa2_code: census for region, census in rows}
    momentum_by_sa2 = await _compute_momentum_fields(db, [region for region, _ in rows], census_by_sa2)

    now = datetime.now(timezone.utc).replace(tzinfo=None)  # naive UTC for DB storage

    for region, census in rows:
        try:
            gov_projects = await fetch_linked_projects(db, region.sa2_code)
            features = build_features(census, gov_projects)
            scores = calculate_investment_score(features)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping score for %s: %s", region.sa2_code, exc)
            report.skipped += 1
            continue

        momentum_fields = momentum_by_sa2.get(region.sa2_code, _MomentumRow())
        existing = await db.get(SuburbScore, region.sa2_code)
        score_row = SuburbScore(
            sa2_code=region.sa2_code,
            investment_score=scores.get("investment_score"),
            demographic_score=scores.get("demographic_score"),
            economic_score=scores.get("economic_score"),
            housing_pressure_score=scores.get("housing_pressure_score"),
            resilience_score=scores.get("resilience_score"),
            gov_investment_score=scores.get("gov_investment_score"),
            risk_flags=scores.get("risk_flags"),
            momentum_score=momentum_fields.momentum_score,
            momentum_phase=momentum_fields.momentum_phase,
            growth_yield_quadrant=momentum_fields.growth_yield_quadrant,
            neighborhood_signal=momentum_fields.neighborhood_signal,
            scarcity_score=momentum_fields.scarcity_score,
            updated_at=now,
        )
        if existing is None:
            db.add(score_row)
            report.inserted += 1
        else:
            await db.merge(score_row)
            report.updated += 1

    await db.commit()
    return report


async def _add_momentum_columns_if_missing() -> None:
    """init_models() only CREATEs tables that don't exist yet — it never
    ALTERs an existing one, so a pre-existing dev DB's suburb_scores table
    needs these four new columns added by hand. Same idempotent pattern as
    building_approvals.py/population_projections.py: try each ADD COLUMN,
    swallow the error if it's already there."""
    from sqlalchemy import text

    new_cols = [
        "ALTER TABLE suburb_scores ADD COLUMN momentum_score REAL",
        "ALTER TABLE suburb_scores ADD COLUMN momentum_phase TEXT",
        "ALTER TABLE suburb_scores ADD COLUMN growth_yield_quadrant TEXT",
        "ALTER TABLE suburb_scores ADD COLUMN neighborhood_signal TEXT",
        "ALTER TABLE suburb_scores ADD COLUMN scarcity_score REAL",
    ]
    async with AsyncSessionLocal() as db:
        for stmt in new_cols:
            try:
                await db.execute(text(stmt))
                await db.commit()
            except Exception:
                await db.rollback()  # column already exists


async def _main(year: int) -> None:
    await init_models()
    await _add_momentum_columns_if_missing()
    async with AsyncSessionLocal() as db:
        logger.info("Starting score backfill for year=%d ...", year)
        report = await backfill_scores(db, year=year)
        logger.info("Backfill complete: %s", report)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    p = argparse.ArgumentParser(description="Backfill SuburbScore table")
    p.add_argument("--year", type=int, default=2021)
    args = p.parse_args()

    asyncio.run(_main(args.year))
