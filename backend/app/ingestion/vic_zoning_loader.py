"""VIC Planning Scheme Zones loader.

Fetches all Victorian planning scheme zone polygons from the VicPlan ArcGIS
service, intersects them with SA2 boundaries, and writes zone-class percentage
breakdowns to the sa2_zoning table.

Data source
───────────
VicPlan — Vicplan_PlanningSchemeZones MapServer, Layer 0 (All Zones)
URL: https://plan-gis.mapshare.vic.gov.au/arcgis/rest/services/
     Planning/Vicplan_PlanningSchemeZones/MapServer/0
Updated: Continuously (planning scheme amendments reflect within days)
Licence: Creative Commons Attribution 4.0

Key field: ZONE_CODE_GROUP — the parent zone code without schedule suffix
           (e.g. NRZ3 → NRZ, GRZ2 → GRZ)

Zone code → category mapping
─────────────────────────────
See _ZONE_CODE_TO_CAT below.

Tables written
──────────────
sa2_zoning — one row per VIC SA2 with zone percentage breakdown (full reload
             of VIC rows only)

Usage (CLI):
    python -m app.ingestion.vic_zoning
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
    "https://plan-gis.mapshare.vic.gov.au/arcgis/rest/services"
    "/Planning/Vicplan_PlanningSchemeZones/MapServer/0/query"
)
_PAGE_SIZE     = 2000
_REQUEST_DELAY = 0.3
_SOURCE        = "VicPlan Vicplan_PlanningSchemeZones"
_STATE         = "VIC"

# ZONE_CODE_GROUP values to skip
_SKIP_CODES = frozenset({
    "CA",    # Commonwealth land — not state-controlled
    "UFZ",   # Urban Floodway Zone — hazard, not zoning category
})

# ZONE_CODE_GROUP → internal category
# Reference: https://www.planning.vic.gov.au/schemes-and-amendments/
_ZONE_CODE_TO_CAT: dict[str, str] = {
    # ── High-density residential ──────────────────────────────────────────
    "RGZ":  "high_density_res",     # Residential Growth Zone
    "R1Z":  "high_density_res",     # Residential 1 Zone (legacy, high-density)

    # ── Medium-density residential ────────────────────────────────────────
    "GRZ":  "medium_density_res",   # General Residential Zone
    "HCTZ": "medium_density_res",   # Housing Consolidation Transition Zone

    # ── Low-density / neighbourhood residential ───────────────────────────
    "NRZ":  "low_density_res",      # Neighbourhood Residential Zone
    "TZ":   "low_density_res",      # Township Zone (small towns)

    # ── Low-density large-lot / rural residential ─────────────────────────
    "LDRZ": "large_lot_res",        # Low Density Residential Zone
    "RLZ":  "large_lot_res",        # Rural Living Zone

    # ── Mixed use ─────────────────────────────────────────────────────────
    "MUZ":  "mixed_use",            # Mixed Use Zone

    # ── Commercial / activity centres ─────────────────────────────────────
    "C1Z":  "commercial",           # Commercial 1 Zone (main shopping)
    "C2Z":  "commercial",           # Commercial 2 Zone (bulky goods)
    "B1Z":  "commercial",           # Business 1 Zone (legacy)
    "B2Z":  "commercial",           # Business 2 Zone (legacy)
    "B3Z":  "commercial",           # Business 3 Zone (legacy)
    "B4Z":  "commercial",           # Business 4 Zone (legacy)
    "B5Z":  "commercial",           # Business 5 Zone (legacy)

    # ── Industrial / employment ───────────────────────────────────────────
    "IN1Z": "industrial",           # Industrial 1 Zone (general)
    "IN2Z": "industrial",           # Industrial 2 Zone (mixed use industry)
    "IN3Z": "industrial",           # Industrial 3 Zone (special use)

    # ── Public open space / recreation ───────────────────────────────────
    "PPRZ": "public_recreation",    # Public Park and Recreation Zone
    "PUZ":  "public_recreation",    # Public Use Zone (subset used for parks)
    "PCRZ": "environmental",        # Public Conservation and Resource Zone

    # ── Environmental / conservation ──────────────────────────────────────
    "RCZ":  "environmental",        # Rural Conservation Zone
    "FZ":   "environmental",        # Farming Zone (primary production)
    "GWZ":  "environmental",        # Green Wedge Zone
    "GWAZ": "environmental",        # Green Wedge A Zone

    # ── Rural / primary production ────────────────────────────────────────
    "RAZ":  "rural",                # Rural Activity Zone

    # ── Urban development / growth ────────────────────────────────────────
    "UGZ":  "urban_development",    # Urban Growth Zone (greenfield)
    "CDZ":  "urban_development",    # Comprehensive Development Zone
    "PDZ":  "urban_development",    # Priority Development Zone

    # ── Special / infrastructure ──────────────────────────────────────────
    "SUZ":  "infrastructure",       # Special Use Zone
    "CCZ":  "infrastructure",       # Capital City Zone (CBD)
    "DZ":   "infrastructure",       # Docklands Zone
    "ACZ":  "infrastructure",       # Activity Centre Zone
    "PZ":   "infrastructure",       # Port Zone
}

# Categories that roll up into residential_total
_RESIDENTIAL_CATS = frozenset({
    "high_density_res", "medium_density_res", "low_density_res", "large_lot_res",
})


@dataclass
class VICZoningReport:
    polygons_fetched: int = 0
    sa2s_processed:   int = 0
    sa2s_written:     int = 0

    def __str__(self) -> str:
        return (
            f"Polygons fetched: {self.polygons_fetched} | "
            f"VIC SA2s processed: {self.sa2s_processed} | "
            f"SA2 zoning rows written: {self.sa2s_written}"
        )


def load_vic_zoning(db: Session) -> VICZoningReport:
    report = VICZoningReport()

    logger.info("Fetching VIC planning scheme zone polygons ...")
    zone_gdf = _fetch_all_zones(report)
    logger.info("Fetched %d zone polygons", report.polygons_fetched)

    logger.info("Loading VIC SA2 geometries ...")
    sa2_gdf = _load_vic_sa2s(db)
    logger.info("Loaded %d VIC SA2 polygons", len(sa2_gdf))
    report.sa2s_processed = len(sa2_gdf)

    logger.info("Computing zone intersections (this may take several minutes) ...")
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

def _fetch_all_zones(report: VICZoningReport):
    """Fetch all VIC zone polygons and return a GeoDataFrame."""
    import geopandas as gpd

    session = requests.Session()
    session.verify = False
    session.headers["User-Agent"] = "SuburbIntel/1.0"

    records: list[dict] = []
    offset = 0

    while True:
        params = {
            "where":             "1=1",
            "outFields":         "OBJECTID,ZONE_CODE_GROUP,ZONE_DESCRIPTION",
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
            code     = (attrs.get("ZONE_CODE_GROUP") or "").strip()

            if code in _SKIP_CODES:
                continue

            cat = _ZONE_CODE_TO_CAT.get(code, "other")
            geom_raw = feat.get("geometry")
            if not geom_raw:
                continue

            try:
                geom = _rings_to_shapely(geom_raw)
                if geom is not None and not geom.is_empty:
                    records.append({"category": cat, "geometry": geom})
            except Exception:
                pass

        report.polygons_fetched += len(features)

        if offset == 0:
            logger.info("  Page 1: %d features", len(features))
        elif offset % (_PAGE_SIZE * 5) == 0:
            logger.info("  Fetched %d so far ...", report.polygons_fetched)

        if not data.get("exceededTransferLimit", False):
            break

        # Increment by actual records returned, not _PAGE_SIZE — the server
        # may cap per-page records below our requested resultRecordCount.
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

def _load_vic_sa2s(db: Session):
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
    """Return {sa2_code: {category: pct_of_sa2_area}} for all VIC SA2s."""
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
