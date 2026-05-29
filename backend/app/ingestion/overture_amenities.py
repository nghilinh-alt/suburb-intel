"""CLI entry point for the Overture Maps amenity loader.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1

    # Step 1 — download AU places from Overture S3 (one-time, ~5 min):
    python -m app.ingestion.overture_amenities --download

    # Step 2 — load all states into DB (~2-3 min):
    python -m app.ingestion.overture_amenities

    # One state only:
    python -m app.ingestion.overture_amenities --state VIC

    # Custom places file location:
    python -m app.ingestion.overture_amenities --places ../data/overture/au_places.parquet
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_DEFAULT_PLACES = Path("../data/overture/au_places.parquet")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load Overture Maps amenity counts per SA2 into abs_census_metrics"
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download AU places from Overture S3 before loading (one-time setup).",
    )
    parser.add_argument(
        "--places",
        type=Path,
        default=_DEFAULT_PLACES,
        help=f"Path to local AU places parquet (default: {_DEFAULT_PLACES}).",
    )
    parser.add_argument(
        "--state",
        type=str,
        default=None,
        help="Restrict to SA2s in this state (e.g. VIC, NSW).",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2021,
        help="Census year to update (default: 2021).",
    )
    args = parser.parse_args()

    from app.ingestion.overture_amenity_loader import download_au_places, load_overture_amenities

    # --- Download step (download-only — run separately before loading) ---
    if args.download:
        print(f"Downloading AU places from Overture S3 to {args.places} ...")
        print("This queries ~60 GB of S3 data but only transfers matching rows (~300 MB).")
        print("Estimated time: 3–10 minutes depending on connection speed.")
        count = download_au_places(args.places)
        print(f"Download complete: {count:,} places saved to {args.places}")
        return   # download only; run without --download to load into DB

    # --- Load step -------------------------------------------------------
    if not args.places.exists():
        if not args.download:
            print(
                f"Error: places file not found: {args.places}\n"
                "Run with --download first to fetch AU places from Overture S3.",
                file=sys.stderr,
            )
            sys.exit(1)
        # download was just run above, file should now exist
        if not args.places.exists():
            print("Error: download completed but file not found.", file=sys.stderr)
            sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        state_label = f" (state={args.state})" if args.state else " (all states)"
        print(f"Loading Overture amenities{state_label} ...")
        report = load_overture_amenities(
            db,
            args.places,
            year=args.year,
            state_filter=args.state,
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
