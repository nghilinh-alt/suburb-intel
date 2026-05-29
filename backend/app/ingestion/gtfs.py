"""CLI entry point for the GTFS PT stop density loader.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1

    # Victoria (PTV multi-feed zip):
    python -m app.ingestion.gtfs --zip "../data/gtfs/vic_gtfs.zip" --state VIC

    # Standard single-feed (e.g. TransLink QLD):
    python -m app.ingestion.gtfs --zip "../data/gtfs/qld_gtfs.zip" --state QLD

Notes:
    --state is recommended when running a state-specific feed so only that
    state's SA2 rows are updated and other states' counts are preserved.

    GTFS source URLs:
      VIC: http://data.ptv.vic.gov.au/downloads/gtfs.zip
      QLD: https://gtfsrt.api.translink.com.au/GTFS/SEQ_GTFS.zip
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Count GTFS PT stops per SA2 and upsert into abs_census_metrics"
    )
    parser.add_argument("--zip", type=Path, required=True, help="Path to GTFS zip file")
    parser.add_argument("--year", type=int, default=2021, help="Census year to update (default: 2021)")
    parser.add_argument(
        "--state",
        type=str,
        default=None,
        help="Restrict to SA2s in this state (e.g. VIC, NSW). Recommended for state-specific feeds.",
    )
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Skip nulling existing PT columns before loading. Use when appending a "
             "supplementary regional feed on top of an already-loaded primary feed.",
    )
    args = parser.parse_args()

    if not args.zip.exists():
        print(f"Error: file not found: {args.zip}", file=sys.stderr)
        sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.gtfs_loader import load_gtfs

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        state_label = f" (state={args.state})" if args.state else ""
        reset_label = " [no-reset]" if args.no_reset else ""
        print(f"Loading GTFS stops from {args.zip.name}{state_label}{reset_label} ...")
        report = load_gtfs(
            args.zip, db,
            year=args.year,
            state_filter=args.state,
            reset_existing=not args.no_reset,
        )
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
