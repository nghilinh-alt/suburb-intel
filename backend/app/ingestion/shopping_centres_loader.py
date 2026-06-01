"""Shopping centres loader — fetches named shopping centres from OpenStreetMap.

Uses Overpass API (free, no key, no CC) with the tag shop=mall which correctly
identifies named shopping centre containers (not individual stores).

Bounding boxes cover all Australian state capital regions.
Covers ~1,500-2,000 named shopping centres nationally.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.shopping_centres_loader
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

# Bounding boxes for Australian states (south, west, north, east)
# Split large states into sub-regions to avoid Overpass timeouts
_STATE_BBOXES: list[tuple[str, tuple[float, float, float, float]]] = [
    ("NSW", (-37.5, 140.9, -28.1, 153.7)),
    ("VIC", (-39.2, 140.9, -33.9, 150.0)),
    # QLD split into SE (populated) and rest
    ("QLD", (-29.2, 148.0, -21.0, 153.6)),  # SE QLD + coast
    ("QLD", (-21.0, 139.0, -10.0, 153.6)),  # North QLD
    ("QLD", (-29.2, 137.9, -21.0, 148.0)),  # Outback QLD
    ("WA",  (-35.1, 113.2, -22.0, 122.0)),  # SW WA
    ("WA",  (-22.0, 113.2, -13.7, 129.0)),  # NW WA
    ("SA",  (-38.1, 129.0, -25.9, 141.0)),
    ("TAS", (-43.7, 143.8, -39.5, 148.5)),
    ("ACT", (-35.9, 148.7, -35.1, 149.4)),
    ("NT",  (-26.0, 129.0, -10.9, 138.1)),
]

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_REQUEST_DELAY = 2.0   # seconds between state queries — respectful use


def _fetch_state_malls(state: str, bbox: tuple) -> list[dict]:
    """Fetch named shopping centres (shop=mall) for one state bounding box."""
    import requests
    s, w, n, e = bbox
    query = f"[out:json][timeout:30];(way[\"shop\"=\"mall\"]({s},{w},{n},{e});node[\"shop\"=\"mall\"]({s},{w},{n},{e}););out center tags;"

    try:
        resp = requests.get(_OVERPASS_URL, params={"data": query}, timeout=35, verify=False,
                           headers={"User-Agent": "SuburbIntel/1.0"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Overpass failed for %s: %s", state, exc)
        return []

    results = []
    for el in data.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name", "").strip()
        if not name:
            continue
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not lat or not lon:
            continue
        osm_id = f"{el['type']}-{el['id']}"
        results.append({
            "osm_id":   osm_id,
            "name":     name,
            "lat":      float(lat),
            "lon":      float(lon),
            "state":    state,
            "suburb":   tags.get("addr:suburb") or tags.get("addr:city", ""),
            "postcode": tags.get("addr:postcode", ""),
        })
    return results


def run_load(db) -> str:
    from app.db.models import ShoppingCentre, Base
    from app.db.session import sync_engine
    Base.metadata.create_all(bind=sync_engine)

    db.query(ShoppingCentre).delete(synchronize_session=False)
    db.commit()

    total = 0
    seen_ids: set[str] = set()

    for state, bbox in _STATE_BBOXES:
        logger.info("Fetching shopping centres for %s bbox %s ...", state, bbox[:2])
        malls = _fetch_state_malls(state, bbox)
        new_malls = [m for m in malls if m["osm_id"] not in seen_ids]
        logger.info("  %s: %d found, %d new", state, len(malls), len(new_malls))
        for m in new_malls:
            db.merge(ShoppingCentre(**m))
            seen_ids.add(m["osm_id"])
        total += len(new_malls)
        db.commit()
        time.sleep(_REQUEST_DELAY)
    return f"Shopping centres loaded: {total} across {len(_STATE_BBOXES)} states"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        result = run_load(db)
        print(f"Done: {result}")
    except Exception:
        logger.exception("Load failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
