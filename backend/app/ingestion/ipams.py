"""CLI entry point for the iPAMS infrastructure projects loader.

Fetches all Commonwealth-funded road and rail projects from the Department of
Infrastructure's ArcGIS feature service and loads them into the database.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.ipams
"""

from __future__ import annotations

import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.ipams_loader import load_ipams_projects
    from sqlalchemy import text

    Base.metadata.create_all(bind=sync_engine)
    _migrate_columns(sync_engine, text)

    db = get_sync_session()
    try:
        print("Fetching Commonwealth infrastructure projects from iPAMS ...")
        report = load_ipams_projects(db)
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
    """Add iPAMS-specific columns to infrastructure_projects if absent."""
    new_cols = [
        "ALTER TABLE infrastructure_projects ADD COLUMN agc_aud INTEGER",
        "ALTER TABLE infrastructure_projects ADD COLUMN sub_program TEXT",
        "ALTER TABLE infrastructure_projects ADD COLUMN expected_start TEXT",
        "ALTER TABLE infrastructure_projects ADD COLUMN expected_end TEXT",
        "ALTER TABLE infrastructure_projects ADD COLUMN project_url TEXT",
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
