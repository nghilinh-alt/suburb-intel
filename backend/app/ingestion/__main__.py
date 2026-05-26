"""CLI entry point for the DataPack loader.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion path/to/2021_GCP_SA2_for_VIC_short-header.zip [--year 2021] [--states VIC NSW]
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load ABS Census GCP DataPack into the database")
    parser.add_argument("zip", type=Path, help="Path to the DataPack zip file")
    parser.add_argument("--year", type=int, default=2021, help="Census year (default: 2021)")
    parser.add_argument(
        "--states",
        nargs="*",
        default=None,
        help="Restrict loading to specific state codes (e.g. VIC NSW). Default: all states",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete existing metrics for the given year before loading",
    )
    args = parser.parse_args()

    if not args.zip.exists():
        print(f"Error: file not found: {args.zip}", file=sys.stderr)
        sys.exit(1)

    # Import here so the sys.path manipulation in session.py runs after arg parsing.
    from app.db.session import get_sync_session
    from app.ingestion.abs_datapack_loader import load_datapack

    db = get_sync_session()
    try:
        print(f"Loading {args.zip} (year={args.year}, states={args.states or 'all'}) ...")
        report = load_datapack(
            args.zip,
            db,
            year=args.year,
            states=args.states,
            truncate_first=args.truncate,
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
