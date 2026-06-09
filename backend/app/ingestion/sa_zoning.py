"""CLI entry point for the SA P&D Code zones loader.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1

    # Download the zip first (one-time or refresh):
    # curl -L https://www.dptiapps.com.au/dataportal/PDCodeZones_geojson.zip \
    #      -o ../data/zoning/sa_zones_geojson.zip

    python -m app.ingestion.sa_zoning --zip ../data/zoning/sa_zones_geojson.zip

Source:
    SA Planning and Design Code Zones — GeoJSON download
    https://data.sa.gov.au/data/dataset/planning-and-design-code-zones
    Updated fortnightly; re-download zip to get the latest amendments.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load SA Planning and Design Code zones into sa2_zoning"
    )
    parser.add_argument(
        "--zip", type=Path, required=True,
        help="Path to PDCodeZones_geojson.zip (download from data.sa.gov.au)",
    )
    args = parser.parse_args()

    if not args.zip.exists():
        print(f"Error: file not found: {args.zip}", file=sys.stderr)
        sys.exit(1)

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.sa_zoning_loader import load_sa_zoning

    Base.metadata.create_all(bind=sync_engine)
    db = get_sync_session()
    try:
        print(f"Loading SA P&D Code zones from {args.zip.name} ...")
        report = load_sa_zoning(args.zip, db)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
