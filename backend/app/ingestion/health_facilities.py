"""CLI entry point for the health facilities loader.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.health_facilities
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
    from app.ingestion.health_facilities_loader import load_health_facilities

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        from app.ingestion.health_facilities_loader import load_health_facilities
        report = load_health_facilities(db)
        print(f"Done: {report}")
    except Exception:
        logging.exception("Load failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
