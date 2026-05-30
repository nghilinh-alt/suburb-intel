"""CLI entry point for the planning zones loader.

Currently ingests QLD Priority Development Areas (PDAs) from the EDQ
ArcGIS MapServer.

⚠️  The EDQ MapServer is deprecated on 26 June 2026. Check for a
    replacement URL after that date.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.planning_zones
"""

from __future__ import annotations

import logging
import sys

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.planning_zones_loader import load_planning_zones

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        report = load_planning_zones(db)
        print(f"Done: {report}")
    except Exception:
        logging.exception("Load failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
