"""CLI entry point for the SA2 geometry loader.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.geometry --shp "../data/datapacks/SA2_2021_AUST_SHP_GDA2020.zip"
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load SA2 boundary geometries into the database")
    parser.add_argument("--shp", type=Path, required=True, help="Path to SA2_2021_AUST_SHP_GDA2020.zip")
    args = parser.parse_args()

    if not args.shp.exists():
        print(f"Error: file not found: {args.shp}", file=sys.stderr)
        sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.geometry_loader import load_geometries

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        print(f"Loading SA2 geometries from {args.shp.name} ...")
        report = load_geometries(args.shp, db)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
