"""CLI entry point for the Infrastructure Australia Priority List loader.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.infrastructure
    python -m app.ingestion.infrastructure --pdf ../data/infrastructure/2026-ipl.pdf
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Parse Infrastructure Australia 2026 Priority List PDF, "
            "geocode projects via Nominatim, and load into the database."
        )
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path("../data/infrastructure/2026-ipl.pdf"),
        help="Path to the IA 2026 Priority List PDF (default: ../data/infrastructure/2026-ipl.pdf).",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        print(f"Error: PDF not found: {args.pdf}", file=sys.stderr)
        sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.infrastructure_loader import load_infrastructure_projects
    from sqlalchemy import text

    Base.metadata.create_all(bind=sync_engine)
    _migrate_columns(sync_engine, text)

    db = get_sync_session()
    try:
        print(f"Loading Infrastructure Australia projects from {args.pdf.name} ...")
        print("Note: geocoding 68 projects via Nominatim (~75 seconds due to rate limit)")
        report = load_infrastructure_projects(args.pdf, db)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


def _migrate_columns(engine, text) -> None:
    """Add IA-specific columns to infrastructure_projects if they don't exist."""
    new_cols = [
        "ALTER TABLE infrastructure_projects ADD COLUMN state TEXT",
        "ALTER TABLE infrastructure_projects ADD COLUMN timing TEXT",
        "ALTER TABLE infrastructure_projects ADD COLUMN source TEXT",
    ]
    with engine.connect() as conn:
        for stmt in new_cols:
            try:
                conn.execute(text(stmt))
                conn.commit()
            except Exception:
                pass  # column already exists


if __name__ == "__main__":
    main()
