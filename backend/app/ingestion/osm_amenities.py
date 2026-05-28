"""CLI entry point for the OSM amenity bulk loader.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1

    # VIC only (~13 min, 522 SA2s):
    python -m app.ingestion.osm_amenities --state VIC

    # All states (~62 min, 2 472 SA2s):
    python -m app.ingestion.osm_amenities

    # Faster (less polite to Overpass — use with caution):
    python -m app.ingestion.osm_amenities --state VIC --delay 0.8
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Count OSM amenities per SA2 polygon via Overpass API"
    )
    parser.add_argument(
        "--state",
        type=str,
        default=None,
        help="Restrict to SA2s in this state (e.g. VIC, NSW). Recommended for a first run.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2021,
        help="Census year whose metrics rows to update (default: 2021).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds between Overpass requests (default: 1.5). Lower = faster but less polite.",
    )
    args = parser.parse_args()

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.osm_amenity_loader import load_osm_amenities

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        state_label = f" (state={args.state})" if args.state else " (all states)"
        print(f"Loading OSM amenities{state_label} with {args.delay}s delay between requests ...")
        report = load_osm_amenities(
            db,
            year=args.year,
            state_filter=args.state,
            request_delay=args.delay,
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
