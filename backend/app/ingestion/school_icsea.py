"""CLI entry point for the School ICSEA loader.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.school_icsea ^
        --icsea  "../data/datapacks/School ICSEA Scores 2025.xlsx" ^
        --mb     ../data/datapacks/MB_2021_AUST.xlsx ^
        --poa    ../data/datapacks/POA_2021_AUST.xlsx
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load school ICSEA scores into the database")
    parser.add_argument("--icsea", type=Path, required=True, help="Path to School ICSEA Scores 2025.xlsx")
    parser.add_argument("--mb",   type=Path, required=True, help="Path to MB_2021_AUST.xlsx")
    parser.add_argument("--poa",  type=Path, required=True, help="Path to POA_2021_AUST.xlsx")
    parser.add_argument("--year", type=int,  default=2021,  help="Census year to update (default: 2021)")
    args = parser.parse_args()

    for label, path in [("--icsea", args.icsea), ("--mb", args.mb), ("--poa", args.poa)]:
        if not path.exists():
            print(f"Error: file not found: {path} ({label})", file=sys.stderr)
            sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.school_icsea_loader import load_school_icsea

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        print(f"Loading ICSEA scores (year={args.year}) …")
        report = load_school_icsea(args.icsea, args.mb, args.poa, db, year=args.year)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
