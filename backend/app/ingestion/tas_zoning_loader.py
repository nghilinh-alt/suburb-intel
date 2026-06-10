"""TAS Planning Scheme Zones loader.

Fetches all Tasmanian Planning Scheme zone polygons from the LIST (Land
Information System Tasmania) ArcGIS service, intersects them with SA2
boundaries, and writes zone-class percentage breakdowns to sa2_zoning.

Data source
───────────
LIST Public Services — Planning Online MapServer, Layer 13
URL: https://services.thelist.tas.gov.au/arcgis/rest/services/
     Public/PlanningOnline/MapServer/13
Updated: Continuously (Local Provisions Schedule amendments)
Licence: Creative Commons Attribution 3.0 Australia

Key field: ZONE — standardised zone name from the Tasmanian Planning Scheme.
           All 29 Tasmanian LGAs use the same TPS zone names (unlike WA).
           24 unique zone types, 100% exact-match mapping.

Tables written
──────────────
sa2_zoning — one row per TAS SA2 with zone percentage breakdown (full reload
             of TAS rows only)

Usage (CLI):
    python -m app.ingestion.tas_zoning
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date

import requests
import urllib3
from sqlalchemy.orm import Session

from app.db.models import SA2Zoning, SA2Region

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

_SERVICE_URL = (
    "https://services.thelist.tas.gov.au/arcgis/rest/services"
    "/Public/PlanningOnline/MapServer/13/query"
)
_PAGE_SIZE     = 1000   # service returns HTTP 500 at 2000 with geometry
_REQUEST_DELAY = 0.3
_SOURCE        = "TAS LIST PlanningOnline Layer 13 (Tasmanian Planning Scheme Zones)"
_STATE         = "TAS"

# TAS Planning Scheme Zone name → internal category
# Reference: Tasmanian Planning Scheme (TPS) — standard zones used by all LGAs
_TAS_ZONE_TO_CAT: dict[str, str] = {
    # ── Residential ───────────────────────────────────────────────────────────
    "Inner Residential":        "medium_density_res",   # Higher-density inner urban
    "General Residential":      "low_density_res",      # Standard suburban
    "Low Density Residential":  "low_density_res",      # Larger lot sizes
    "Rural Living":             "large_lot_res",        # Semi-rural lifestyle lots
    "Village":                  "low_density_res",      # Small town residential

    # ── Mixed use ─────────────────────────────────────────────────────────────
    "Urban Mixed Use":          "mixed_use",

    # ── Commercial / business ─────────────────────────────────────────────────
    "Local Business":           "commercial",
    "General Business":         "commercial",
    "Central Business":         "commercial",
    "Commercial":               "commercial",
    "Major Tourism":            "commercial",           # Tourism = commercial use

    # ── Industrial ────────────────────────────────────────────────────────────
    "Light Industrial":         "industrial",
    "General Industrial":       "industrial",
    "Port and Marine":          "industrial",           # Working port/marine industry

    # ── Rural / primary production ────────────────────────────────────────────
    "Rural":                    "rural",
    "Agriculture":              "rural",

    # ── Environmental / conservation ──────────────────────────────────────────
    "Landscape Conservation":   "environmental",
    "Environmental Management": "environmental",

    # ── Public open space / recreation ───────────────────────────────────────
    "Recreation":               "public_recreation",
    "Open Space":               "public_recreation",

    # ── Urban development / growth ────────────────────────────────────────────
    "Future Urban":             "urban_development",

    # ── Infrastructure / civic / community ───────────────────────────────────
    "Utilities":                "infrastructure",
    "Community Purpose":        "infrastructure",
    "Particular Purpose":       "infrastructure",
}

# Categories that roll up into residential_total
_RESIDENTIAL_CATS = frozenset({
    "high_density_res", "medium_density_res", "low_density_res", "large_lot_res",
})


@dataclass
class TASZoningReport:
    polygons_fetched: int = 0
    polygons_mapped:  int = 0
    sa2s_processed:   int = 0
    sa2s_written:     int = 0

    def __str__(self) -> str:
        return (
            f"Polygons fetched: {self.polygons_fetched} | "
            f"Mapped to category: {self.polygons_mapped} | "
            f"TAS SA2s processed: {self.sa2s_processed} | "
            f"SA2 zoning rows written: {self.sa2s_written}"
        )


def load_tas_zoning(db: Session) -> TASZoningReport:
    report = TASZoningReport()

    logger.info("Fetching TAS Planning Scheme zone polygons ...")
    zone_gdf = _fetch_all_zones(report)
    logger.info("Fetched %d zone polygons (%d mapped)", report.polygons_fetched, report.polygons_mapped)

    logger.info("Loading TAS SA2 geometries ...")
    sa2_gdf = _load_tas_sa2s(db)
    logger.info("Loaded %d TAS SA2 polygons", len(sa2_gdf))
    report.sa2s_processed = len(sa2_gdf)

    logger.info("Computing zone intersections ...")
    zoning_by_sa2 = _compute_zoning(zone_gdf, sa2_gdf)

    logger.info("Writing to sa2_zoning table ...")
    db.query(SA2Zoning).filter(SA2Zoning.state == _STATE).delete(synchronize_session=False)

    today = date.today().isoformat()
    for sa2_code, cats in zoning_by_sa2.items():
        total_res = sum(cats.get(c, 0.0) for c in _RESIDENTIAL_CATS)
        row = SA2Zoning(
            sa2_code=sa2_code,
            state=_STATE,
            zone_pct_high_density_res   = round(cats.get("high_density_res", 0.0), 2),
            zone_pct_medium_density_res  = round(cats.get("medium_density_res", 0.0), 2),
            zone_pct_low_density_res    = round(cats.get("low_density_res", 0.0), 2),
            zone_pct_large_lot_res      = round(cats.get("large_lot_res", 0.0), 2),
            zone_pct_residential_total  = round(total_res, 2),
            zone_pct_mixed_use          = round(cats.get("mixed_use", 0.0), 2),
            zone_pct_commercial         = round(cats.get("commercial", 0.0), 2),
            zone_pct_industrial         = round(cats.get("industrial", 0.0), 2),
            zone_pct_public_recreation  = round(cats.get("public_recreation", 0.0), 2),
            zone_pct_environmental      = round(cats.get("environmental", 0.0), 2),
            zone_pct_urban_development  = round(cats.get("urban_development", 0.0), 2),
            zone_breakdown_json         = {k: round(v, 2) for k, v in cats.items()},
            source                      = _SOURCE,
            source_date                 = today,
        )
        db.add(row)
        report.sa2s_written += 1

    db.commit()
    return report


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def _fetch_all_zones(report: TASZoningReport):
    import geopandas as gpd

    session = requests.Session()
    session.verify = False
    session.headers["User-Agent"] = "SuburbIntel/1.0"

    records: list[dict] = []
    offset = 0

    while True:
        params = {
            "where":             "1=1",
            "outFields":         "OBJECTID,ZONE",
            "returnGeometry":    "true",
            "outSR":             "4326",
            "resultOffset":      offset,
            "resultRecordCount": _PAGE_SIZE,
            "f":                 "json",
        }
        try:
            resp = session.get(_SERVICE_URL, params=params, timeout=90)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Fetch failed at offset %d: %s", offset, exc)
            break

        features = data.get("features", [])
        for feat in features:
            attrs    = feat.get("attributes", {})
            zone_raw = (attrs.get("ZONE") or "").strip()
            cat      = _TAS_ZONE_TO_CAT.get(zone_raw, "other")

            geom_raw = feat.get("geometry")
            if not geom_raw:
                continue

            try:
                geom = _rings_to_shapely(geom_raw)
                if geom is not None and not geom.is_empty:
                    records.append({"category": cat, "geometry": geom})
                    if cat != "other":
                        report.polygons_mapped += 1
            except Exception:
                pass

        report.polygons_fetched += len(features)

        if offset == 0:
            logger.info("  Page 1: %d features", len(features))
        elif offset % (_PAGE_SIZE * 5) == 0:
            logger.info("  Fetched %d so far ...", report.polygons_fetched)

        if not data.get("exceededTransferLimit", False):
            break

        offset += len(features)
        time.sleep(_REQUEST_DELAY)

    return gpd.GeoDataFrame(records, crs="EPSG:4326")


def _rings_to_shapely(geom_raw: dict):
    from shapely.geometry import shape
    rings = geom_raw.get("rings", [])
    if not rings:
        return None
    if len(rings) == 1:
        geojson = {"type": "Polygon", "coordinates": rings}
    else:
        geojson = {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}
    geom = shape(geojson)
    if not geom.is_valid:
        geom = geom.buffer(0)
    return geom


# ---------------------------------------------------------------------------
# SA2 loader
# ---------------------------------------------------------------------------

def _load_tas_sa2s(db: Session):
    import geopandas as gpd
    from shapely.geometry import shape

    rows = (
        db.query(SA2Region.sa2_code, SA2Region.geometry_geojson)
        .filter(SA2Region.state == _STATE)
        .all()
    )
    records = []
    for sa2_code, geojson_str in rows:
        if not geojson_str:
            continue
        try:
            geom = shape(json.loads(geojson_str))
            records.append({"sa2_code": sa2_code, "geometry": geom})
        except Exception:
            pass

    gdf = gpd.GeoDataFrame(records, crs="EPSG:4326")
    gdf["sa2_area"] = gdf.geometry.area
    return gdf


# ---------------------------------------------------------------------------
# Intersection
# ---------------------------------------------------------------------------

def _compute_zoning(zone_gdf, sa2_gdf) -> dict[str, dict[str, float]]:
    import warnings
    import geopandas as gpd

    logger.info("  Running spatial overlay (zone polygons × SA2s) ...")
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        try:
            intersected = gpd.overlay(
                zone_gdf[["category", "geometry"]],
                sa2_gdf[["sa2_code", "sa2_area", "geometry"]],
                how="intersection",
                keep_geom_type=False,
            )
        except Exception as exc:
            logger.error("Overlay failed: %s", exc)
            return {}

    logger.info("  Overlay produced %d intersection fragments", len(intersected))

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        intersected["isect_area"] = intersected.geometry.area

    agg = (
        intersected.groupby(["sa2_code", "category"])["isect_area"]
        .sum()
        .reset_index()
    )

    sa2_area_map = dict(zip(sa2_gdf["sa2_code"], sa2_gdf["sa2_area"]))
    result: dict[str, dict[str, float]] = {}
    for _, row in agg.iterrows():
        sa2      = row["sa2_code"]
        cat      = row["category"]
        area     = row["isect_area"]
        sa2_area = sa2_area_map.get(sa2, 0)
        if sa2_area > 0:
            pct = (area / sa2_area) * 100.0
            result.setdefault(sa2, {})[cat] = result.get(sa2, {}).get(cat, 0.0) + pct

    return result
