"""CLI entry point for the points-of-interest loader.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1

    # Step 1 — download AU POI places from Overture S3 (one-time):
    python -m app.ingestion.points_of_interest --download

    # Step 2 — match to SA2s and load into DB:
    python -m app.ingestion.points_of_interest
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_DEFAULT_PLACES = Path("../data/overture/au_pois.parquet")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load points of interest from Overture Maps into the database")
    parser.add_argument("--download", action="store_true", help="Download AU POI places from Overture S3 first")
    parser.add_argument("--places", type=Path, default=_DEFAULT_PLACES)
    args = parser.parse_args()

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.points_of_interest_loader import download_au_pois, load_points_of_interest

    Base.metadata.create_all(bind=sync_engine)

    if args.download:
        print("Downloading AU POI places from Overture S3 ...")
        count = download_au_pois(args.places)
        print(f"Downloaded {count} POI places to {args.places}")

    if not args.places.exists():
        print(f"Error: file not found: {args.places}. Run with --download first.", file=sys.stderr)
        sys.exit(1)

    db = get_sync_session()
    try:
        print(f"Loading points of interest from {args.places} ...")
        report = load_points_of_interest(db, args.places)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
