"""CLI entry point for the SEIFA 2016 + gentrification change loader.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.seifa_change
    python -m app.ingestion.seifa_change --file ../data/datapacks/SEIFA_2016_SA2.xls
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

_DEFAULT_FILE = Path("../data/datapacks/SEIFA_2016_SA2.xls")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load SEIFA 2016 + compute gentrification change signals")
    parser.add_argument("--file", type=Path, default=_DEFAULT_FILE, help="Path to SEIFA_2016_SA2.xls")
    parser.add_argument("--year", type=int, default=2021, help="Census year for abs_census_metrics (default: 2021)")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.seifa_change_loader import load_seifa_change

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        report = load_seifa_change(args.file, db, year=args.year)
        print(f"Done: {report}")
    except Exception:
        logging.exception("Load failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
