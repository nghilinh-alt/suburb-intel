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
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.scoring import calculate_investment_score
from app.db.models import ABSCEntensMetrics, SA2Region, SuburbScore
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


async def _main(year: int) -> None:
    await init_models()
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
