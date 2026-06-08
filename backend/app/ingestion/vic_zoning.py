"""CLI entry point for the VIC planning scheme zones loader.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.vic_zoning

Source:
    VicPlan — Vicplan_PlanningSchemeZones MapServer (Layer 0: All Zones)
    https://plan-gis.mapshare.vic.gov.au/arcgis/rest/services/
    Planning/Vicplan_PlanningSchemeZones/MapServer/0
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
    from app.ingestion.vic_zoning_loader import load_vic_zoning

    Base.metadata.create_all(bind=sync_engine)
    db = get_sync_session()
    try:
        print("Loading VIC planning scheme zones ...")
        report = load_vic_zoning(db)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
