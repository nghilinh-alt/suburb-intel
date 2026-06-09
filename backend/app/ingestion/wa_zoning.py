"""CLI entry point for the WA planning scheme zones loader.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.wa_zoning

Source:
    SLIP Public Services — Property_and_Planning MapServer (Layer 112)
    https://public-services.slip.wa.gov.au/public/rest/services/
    SLIP_Public_Services/Property_and_Planning/MapServer/112
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
    from app.ingestion.wa_zoning_loader import load_wa_zoning

    Base.metadata.create_all(bind=sync_engine)
    db = get_sync_session()
    try:
        print("Loading WA planning scheme zones ...")
        report = load_wa_zoning(db)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
