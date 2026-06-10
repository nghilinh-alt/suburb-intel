"""CLI entry point for the TAS planning scheme zones loader.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.tas_zoning

Source:
    LIST Public Services — PlanningOnline MapServer, Layer 13
    Tasmanian Planning Scheme Zones (all LGAs unified under TPS)
    https://services.thelist.tas.gov.au/arcgis/rest/services/Public/PlanningOnline/MapServer/13
    Updated: Continuously (LPS amendments propagate within days).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.tas_zoning_loader import load_tas_zoning

    Base.metadata.create_all(bind=sync_engine)
    db = get_sync_session()
    try:
        print("Loading TAS Planning Scheme zones ...")
        report = load_tas_zoning(db)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
