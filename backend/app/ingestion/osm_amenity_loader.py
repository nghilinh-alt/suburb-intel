"""OSM amenity count bulk loader.

Uses the public Overpass API to count OpenStreetMap amenities inside each
SA2 boundary and stores per-category counts on abs_census_metrics.

Algorithm per SA2
─────────────────
1. Compute the polygon bounding box (+ 0.005° buffer so boundary features
   are not clipped).
2. Issue a single Overpass QL query that fetches nodes, way centroids, and
   relation centroids for all tracked amenity/shop/leisure tags inside the
   bounding box.
3. Discard any result whose coordinate falls outside the actual SA2 polygon
   (shapely point-in-polygon).
4. Count by category, compute a weighted amenity_score (0–10), upsert.

Overpass notes
──────────────
• No authentication required.
• Endpoint: https://overpass-api.de/api/interpreter (POST).
• Default rate: 1 request / 1.5 s → ~62 min for all 2 472 SA2s.
  Use --state VIC for a ~13 min pilot run (522 SA2s).

Columns written to abs_census_metrics
──────────────────────────────────────
osm_cafes, osm_restaurants, osm_supermarkets, osm_parks,
osm_gyms, osm_hospitals, osm_pharmacies, amenity_score

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.osm_amenities --state VIC
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path

import urllib3
import requests
from shapely.geometry import Point, shape
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics, SA2Region

logger = logging.getLogger(__name__)

_OVERPASS_URL = "https://overpass-api.de/api/interpreter"
_BBOX_BUFFER  = 0.005   # degrees — expand bbox so boundary features aren't clipped
_TIMEOUT      = 60      # Overpass query timeout (seconds)

# ---------------------------------------------------------------------------
# Amenity category → OSM tag matcher
# ---------------------------------------------------------------------------

def _cat(tags: dict) -> str | None:
    """Return the first matching category for a set of OSM tags, or None."""
    amenity = tags.get("amenity", "")
    shop    = tags.get("shop", "")
    leisure = tags.get("leisure", "")

    if amenity == "cafe":                                    return "cafe"
    if amenity in ("restaurant", "fast_food"):               return "restaurant"
    if shop in ("supermarket", "convenience"):               return "supermarket"
    if leisure == "park":                                    return "park"
    if leisure in ("fitness_centre", "sports_centre"):       return "gym"
    if amenity in ("hospital", "clinic", "doctors"):         return "hospital"
    if amenity == "pharmacy":                                return "pharmacy"
    return None

# Column name for each category
_CAT_COLUMN = {
    "cafe":        "osm_cafes",
    "restaurant":  "osm_restaurants",
    "supermarket": "osm_supermarkets",
    "park":        "osm_parks",
    "gym":         "osm_gyms",
    "hospital":    "osm_hospitals",
    "pharmacy":    "osm_pharmacies",
}

# Amenity score: weight × min(count / cap, 1.0), normalised to 0-10
_SCORE_PARAMS: dict[str, tuple[float, int]] = {
    #              weight  cap
    "cafe":        (8.0,   30),   # 30 cafes in a suburb = top score for this category
    "restaurant":  (7.0,   30),
    "supermarket": (9.0,   8),
    "park":        (8.5,   5),
    "gym":         (7.0,   5),
    "hospital":    (9.5,   3),
    "pharmacy":    (8.0,   5),
}
_MAX_SCORE = sum(w for w, _ in _SCORE_PARAMS.values())   # 57.0


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class OSMAmenityReport:
    sa2s_processed: int = 0
    sa2s_updated:   int = 0
    sa2s_no_geom:   int = 0
    sa2s_no_row:    int = 0
    api_errors:     int = 0
    total_features: int = 0

    def __str__(self) -> str:
        return (
            f"Processed: {self.sa2s_processed} | "
            f"Updated: {self.sa2s_updated} | "
            f"No geometry: {self.sa2s_no_geom} | "
            f"No metrics row: {self.sa2s_no_row} | "
            f"API errors: {self.api_errors} | "
            f"Total OSM features counted: {self.total_features}"
        )


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def load_osm_amenities(
    db: Session,
    *,
    year: int = 2021,
    state_filter: str | None = None,
    request_delay: float = 1.5,
) -> OSMAmenityReport:
    """Fetch OSM amenity counts per SA2 and upsert onto abs_census_metrics.

    Args:
        db:             Synchronous SQLAlchemy session.
        year:           Census year whose metrics rows are updated.
        state_filter:   If set (e.g. "VIC"), only process SA2s in that state.
        request_delay:  Seconds to wait between Overpass requests.
    """
    report = OSMAmenityReport()

    q = db.query(SA2Region.sa2_code, SA2Region.sa2_name, SA2Region.geometry_geojson)
    if state_filter:
        q = q.filter(SA2Region.state == state_filter)

    sa2_rows = q.all()
    total = len(sa2_rows)
    logger.info("Processing %d SA2s ...", total)

    # Windows Python installations often lack system CA certs; suppress the
    # warning and use verify=False for this local ingestion-only script.
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "User-Agent": "SuburbIntel/1.0 (suburb intelligence research project)",
        "Accept-Encoding": "gzip",
    })

    for i, (sa2_code, sa2_name, geojson_str) in enumerate(sa2_rows, 1):
        report.sa2s_processed += 1

        if geojson_str is None:
            report.sa2s_no_geom += 1
            continue

        try:
            polygon = shape(json.loads(geojson_str))
        except Exception as exc:
            logger.warning("Bad geometry SA2 %s: %s", sa2_code, exc)
            report.sa2s_no_geom += 1
            continue

        # Bounding box with buffer
        minx, miny, maxx, maxy = polygon.bounds
        bbox = (
            miny - _BBOX_BUFFER,
            minx - _BBOX_BUFFER,
            maxy + _BBOX_BUFFER,
            maxx + _BBOX_BUFFER,
        )

        features = _fetch_overpass(session, bbox, report)
        if features is None:
            time.sleep(request_delay)
            continue

        # Count amenities inside the actual polygon
        counts: dict[str, int] = {cat: 0 for cat in _CAT_COLUMN}
        for feat in features:
            lat, lon = _coords(feat)
            if lat is None:
                continue
            cat = _cat(feat.get("tags", {}))
            if cat is None:
                continue
            if polygon.contains(Point(lon, lat)):
                counts[cat] += 1
                report.total_features += 1

        # Compute amenity score
        score = 0.0
        for cat, (weight, cap) in _SCORE_PARAMS.items():
            score += weight * min(counts[cat] / cap, 1.0)
        amenity_score = round((score / _MAX_SCORE) * 10, 3)

        # Upsert onto abs_census_metrics
        metrics = db.get(ABSCEntensMetrics, (sa2_code, year))
        if metrics is None:
            report.sa2s_no_row += 1
        else:
            for cat, col in _CAT_COLUMN.items():
                setattr(metrics, col, counts[cat])
            metrics.amenity_score = amenity_score
            report.sa2s_updated += 1

        if i % 25 == 0:
            logger.info("  %d / %d  (%s ...)", i, total, sa2_name[:30])
            db.flush()

        time.sleep(request_delay)

    db.commit()
    return report


# ---------------------------------------------------------------------------
# Overpass fetch
# ---------------------------------------------------------------------------

def _fetch_overpass(
    session: requests.Session,
    bbox: tuple[float, float, float, float],
    report: OSMAmenityReport,
) -> list[dict] | None:
    """Run a combined Overpass query for all tracked amenity types.

    Returns a list of OSM elements (nodes + way/relation centroids), or None
    on error.
    """
    s, w, n, e = bbox
    bbox_str = f"{s:.6f},{w:.6f},{n:.6f},{e:.6f}"

    query = (
        f"[out:json][timeout:{_TIMEOUT}];\n"
        "(\n"
        f'  node["amenity"~"cafe|restaurant|fast_food|hospital|clinic|doctors|pharmacy"]({bbox_str});\n'
        f'  node["shop"~"supermarket|convenience"]({bbox_str});\n'
        f'  node["leisure"~"park|fitness_centre|sports_centre"]({bbox_str});\n'
        f'  way["leisure"~"park|fitness_centre|sports_centre"]({bbox_str});\n'
        f'  relation["leisure"="park"]({bbox_str});\n'
        ");\n"
        "out body center qt;"
    )

    try:
        resp = session.post(_OVERPASS_URL, data={"data": query}, timeout=_TIMEOUT + 10)
        resp.raise_for_status()
        return resp.json().get("elements", [])
    except requests.exceptions.Timeout:
        logger.warning("Overpass timeout for bbox %s", bbox_str)
        report.api_errors += 1
        return None
    except requests.exceptions.RequestException as exc:
        logger.warning("Overpass error for bbox %s: %s", bbox_str, exc)
        report.api_errors += 1
        return None
    except (ValueError, KeyError) as exc:
        logger.warning("Bad Overpass JSON for bbox %s: %s", bbox_str, exc)
        report.api_errors += 1
        return None


# ---------------------------------------------------------------------------
# Coordinate extraction
# ---------------------------------------------------------------------------

def _coords(element: dict) -> tuple[float | None, float | None]:
    """Return (lat, lon) for a node, or the center of a way/relation."""
    if "lat" in element and "lon" in element:
        return element["lat"], element["lon"]
    center = element.get("center")
    if center:
        return center.get("lat"), center.get("lon")
    return None, None
