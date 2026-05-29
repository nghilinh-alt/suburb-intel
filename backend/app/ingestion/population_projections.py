"""CLI entry point for the ABS Population Projections loader.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.population_projections
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch ABS SA2 population projections and load into abs_census_metrics"
    )
    parser.add_argument(
        "--year", type=int, default=2021,
        help="Census year row to update (default: 2021).",
    )
    args = parser.parse_args()

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.population_projections_loader import load_population_projections
    from sqlalchemy import text

    Base.metadata.create_all(bind=sync_engine)

    # Add all new columns if they don't exist yet (idempotent)
    new_cols = [
        "ALTER TABLE abs_census_metrics ADD COLUMN building_approvals_1yr INTEGER",
        "ALTER TABLE abs_census_metrics ADD COLUMN pop_proj_2026 INTEGER",
        "ALTER TABLE abs_census_metrics ADD COLUMN pop_proj_2031 INTEGER",
        "ALTER TABLE abs_census_metrics ADD COLUMN pop_growth_proj_pct REAL",
    ]
    with sync_engine.connect() as conn:
        for stmt in new_cols:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # Column already exists

    db = get_sync_session()
    try:
        print("Fetching ABS population projections (SA2, 2022–2032) ...")
        report = load_population_projections(db, year=args.year)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
