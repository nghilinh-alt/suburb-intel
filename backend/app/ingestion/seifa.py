"""CLI entry point for the SEIFA 2021 loader.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.seifa --file "../data/datapacks/SEIFA_2021_SA2.xlsx"
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load ABS SEIFA 2021 indexes into the database")
    parser.add_argument("--file", type=Path, required=True, help="Path to SEIFA_2021_SA2.xlsx")
    parser.add_argument("--year", type=int, default=2021, help="Census year to update (default: 2021)")
    args = parser.parse_args()

    if not args.file.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.seifa_loader import load_seifa

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        print(f"Loading SEIFA 2021 (year={args.year}) ...")
        report = load_seifa(args.file, db, year=args.year)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
