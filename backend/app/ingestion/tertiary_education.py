"""CLI entry point for the tertiary education facilities loader.

Fetches university and TAFE campus locations from the Geoscience Australia
Foundation Facilities ArcGIS service (Education layer, layer 0) and upserts
them into the existing schools table alongside ACARA K-12 data.

Coverage note: GA education data covers QLD, NSW, VIC and TAS only due to
licensing limitations with other states.

Records used:
  main_function = 'Tertiary Institution'  → school_type = 'University'
  main_function = 'Technical College'     → school_type = 'TAFE'

Records with name = 'Unknown' or '' are skipped.
All operational statuses are included — many real campuses have
operationalstatus = 'Unknown' due to GA data age.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.tertiary_education
"""

from __future__ import annotations

import logging
import sys
import time
import json

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.tertiary_education_loader import load_tertiary_education

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        report = load_tertiary_education(db)
        print(f"Done: {report}")
    except Exception:
        logger.exception("Load failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
