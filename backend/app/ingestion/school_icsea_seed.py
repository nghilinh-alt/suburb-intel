"""CLI entry point for loading the committed ICSEA seed CSV.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.school_icsea_seed
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Load the committed per-SA2 ICSEA seed CSV")
    parser.add_argument(
        "--seed",
        type=Path,
        default=Path("../data/seeds/school_icsea_by_sa2.csv"),
        help="Path to the seed CSV (default: ../data/seeds/school_icsea_by_sa2.csv)",
    )
    args = parser.parse_args()

    if not args.seed.exists():
        print(f"Error: file not found: {args.seed}", file=sys.stderr)
        sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.school_icsea_seed_loader import load_school_icsea_seed

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        print(f"Loading ICSEA seed from {args.seed} ...")
        report = load_school_icsea_seed(db, args.seed)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
