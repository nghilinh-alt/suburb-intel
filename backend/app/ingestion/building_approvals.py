"""CLI entry point for the ABS Building Approvals loader.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1

    # Download the zip first (free, ~8 MB):
    #   https://www.abs.gov.au/statistics/industry/building-and-construction/building-approvals-australia/latest-release
    #   → "Statistical Area Level 2: Australia, <year> (CSV)"

    python -m app.ingestion.building_approvals --zip "../data/building_approvals/sa2_2024-25.zip"
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load ABS building approvals per SA2 into abs_census_metrics"
    )
    parser.add_argument(
        "--zip", type=Path, required=True,
        help="Path to the ABS SA2 building approvals zip file.",
    )
    parser.add_argument(
        "--year", type=int, default=2021,
        help="Census year row to update (default: 2021).",
    )
    args = parser.parse_args()

    if not args.zip.exists():
        print(f"Error: file not found: {args.zip}", file=sys.stderr)
        sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.building_approvals_loader import load_building_approvals
    from sqlalchemy import text

    Base.metadata.create_all(bind=sync_engine)

    # Add all new columns if they don't exist yet (idempotent)
    _migrate_columns(sync_engine, text)

    db = get_sync_session()
    try:
        print(f"Loading building approvals from {args.zip.name} ...")
        report = load_building_approvals(args.zip, db, year=args.year)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


def _migrate_columns(engine, text) -> None:
    """Add new abs_census_metrics columns if they don't already exist."""
    new_cols = [
        "ALTER TABLE abs_census_metrics ADD COLUMN building_approvals_1yr INTEGER",
        "ALTER TABLE abs_census_metrics ADD COLUMN pop_proj_2026 INTEGER",
        "ALTER TABLE abs_census_metrics ADD COLUMN pop_proj_2031 INTEGER",
        "ALTER TABLE abs_census_metrics ADD COLUMN pop_growth_proj_pct REAL",
    ]
    with engine.connect() as conn:
        for stmt in new_cols:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # Column already exists


if __name__ == "__main__":
    main()
