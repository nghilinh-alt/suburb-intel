"""CLI entry point for the school location loader.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1

    # Step 1 — download AU school places from Overture S3 (one-time):
    python -m app.ingestion.school_locations --download

    # Step 2 — match to SA2s and load into DB:
    python -m app.ingestion.school_locations
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_DEFAULT_PLACES = Path("../data/overture/au_schools.parquet")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load school locations from Overture Maps into the database")
    parser.add_argument("--download", action="store_true", help="Download AU school places from Overture S3 first")
    parser.add_argument(
        "--places",
        type=Path,
        default=_DEFAULT_PLACES,
        help=f"Path to the local school places parquet (default: {_DEFAULT_PLACES})",
    )
    args = parser.parse_args()

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.school_locations_loader import download_au_schools, load_school_locations

    Base.metadata.create_all(bind=sync_engine)

    if args.download:
        print("Downloading AU school places from Overture S3 ...")
        count = download_au_schools(args.places)
        print(f"Downloaded {count} school places to {args.places}")

    if not args.places.exists():
        print(f"Error: file not found: {args.places}. Run with --download first.", file=sys.stderr)
        sys.exit(1)

    db = get_sync_session()
    try:
        print(f"Loading school locations from {args.places} ...")
        report = load_school_locations(db, args.places)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
