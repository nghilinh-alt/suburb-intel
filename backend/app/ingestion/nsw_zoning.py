"""CLI entry point for the NSW land zoning loader.

Fetches ~70,000 NSW LEP zoning polygons from the NSW Planning Portal,
intersects them with SA2 boundaries, and writes zone-class percentage
breakdowns to the sa2_zoning table.

Runtime: ~3-5 minutes (download ~35 pages + spatial overlay).

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.nsw_zoning
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
    from app.ingestion.nsw_zoning_loader import load_nsw_zoning

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        report = load_nsw_zoning(db)
        print(f"Done: {report}")
    except Exception:
        logging.exception("Load failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
