"""CLI entry point for the ACT Territory Plan Land Use Zones loader.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.act_zoning

Source:
    ACT Government ArcGIS Online — ACTGOV_TP_LAND_USE_ZONE FeatureServer, Layer 1
    Territory Plan Land Use Zones (current gazetted zones only)
    https://services1.arcgis.com/E5n4f1VY84i0xSjy/arcgis/rest/services/ACTGOV_TP_LAND_USE_ZONE/FeatureServer/1
    Updated: Continuously (Territory Plan variations are gazetted as enacted).
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
    from app.ingestion.act_zoning_loader import load_act_zoning

    Base.metadata.create_all(bind=sync_engine)
    db = get_sync_session()
    try:
        print("Loading ACT Territory Plan land use zones ...")
        report = load_act_zoning(db)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
