"""ACT Territory Plan Land Use Zones loader.

Fetches all ACT Territory Plan land use zone polygons from the ACT Government
ArcGIS Online Feature Service, intersects them with SA2 boundaries, and writes
zone-class percentage breakdowns to sa2_zoning.

Data source
───────────
ACT Government ArcGIS Online — ACTGOV_TP_LAND_USE_ZONE FeatureServer, Layer 1
URL: https://services1.arcgis.com/E5n4f1VY84i0xSjy/arcgis/rest/services/
     ACTGOV_TP_LAND_USE_ZONE/FeatureServer/1
Updated: Continuously (Territory Plan variations are gazetted as enacted)
Licence: ACT Government open data

Key field: LAND_USE_ZONE_CODE_ID — standardised zone code from the Territory Plan.
           24 unique zone codes, 100% exact-match mapping.
           Only GAZETTED (current) records are fetched.

Tables written
──────────────
sa2_zoning — one row per ACT SA2 with zone percentage breakdown (full reload
             of ACT rows only)

Usage (CLI):
    python -m app.ingestion.act_zoning
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
    "https://services1.arcgis.com/E5n4f1VY84i0xSjy/arcgis/rest/services"
    "/ACTGOV_TP_LAND_USE_ZONE/FeatureServer/1/query"
)
_PAGE_SIZE     = 2000
_REQUEST_DELAY = 0.3
_SOURCE        = "ACT Government Territory Plan Land Use Zones (ACTGOV_TP_LAND_USE_ZONE)"
_STATE         = "ACT"

# ACT Territory Plan zone code → internal category
# Reference: ACT Planning — Territory Plan 2008 (as varied)
# https://www.planning.act.gov.au/
_ACT_CODE_TO_CAT: dict[str, str] = {
    # ── High-density residential ──────────────────────────────────────────────
    "RZ5": "high_density_res",       # High Density Residential

    # ── Medium-density residential ────────────────────────────────────────────
    "RZ2": "medium_density_res",     # Suburban Core (higher density nodes)
    "RZ3": "medium_density_res",     # Urban Residential
    "RZ4": "medium_density_res",     # Medium Density Residential

    # ── Low-density / general residential ────────────────────────────────────
    "RZ1": "low_density_res",        # Suburban (standard ACT residential)

    # ── Mixed use ─────────────────────────────────────────────────────────────
    "CZ5": "mixed_use",              # Mixed Use

    # ── Commercial / centres ──────────────────────────────────────────────────
    "CZ1": "commercial",             # Core Zone
    "CZ2": "commercial",             # Business Zone
    "CZ3": "commercial",             # Services Zone
    "CZ4": "commercial",             # Local Centre
    "CZ6": "commercial",             # Leisure and Accommodation

    # ── Industrial ────────────────────────────────────────────────────────────
    "IZ1": "industrial",             # General Industry
    "IZ2": "industrial",             # Industrial Mixed Use

    # ── Public open space / recreation ───────────────────────────────────────
    "PRZ1": "public_recreation",     # Urban Open Space
    "PRZ2": "public_recreation",     # Restricted Access Recreation Zone

    # ── Environmental / natural areas ─────────────────────────────────────────
    "NUZ3": "environmental",         # Hills, Ridges and Buffer Areas
    "NUZ4": "environmental",         # River Corridor
    "NUZ5": "environmental",         # Mountains and Bushlands

    # ── Rural / broadacre ────────────────────────────────────────────────────
    "NUZ1": "rural",                 # Broadacre
    "NUZ2": "rural",                 # Rural

    # ── Infrastructure / civic / designated ───────────────────────────────────
    "CF":   "infrastructure",        # Community Facilities
    "DES":  "infrastructure",        # Designated (public land — parks, institutions, roads)
    "TSZ1": "infrastructure",        # Transport
    "TSZ2": "infrastructure",        # Services
}

# Categories that roll up into residential_total
_RESIDENTIAL_CATS = frozenset({
    "high_density_res", "medium_density_res", "low_density_res", "large_lot_res",
})


@dataclass
class ACTZoningReport:
    polygons_fetched: int = 0
    polygons_mapped:  int = 0
    sa2s_processed:   int = 0
    sa2s_written:     int = 0

    def __str__(self) -> str:
        return (
            f"Polygons fetched: {self.polygons_fetched} | "
            f"Mapped to category: {self.polygons_mapped} | "
            f"ACT SA2s processed: {self.sa2s_processed} | "
            f"SA2 zoning rows written: {self.sa2s_written}"
        )


def load_act_zoning(db: Session) -> ACTZoningReport:
    report = ACTZoningReport()

    logger.info("Fetching ACT Territory Plan land use zone polygons ...")
    zone_gdf = _fetch_all_zones(report)
    logger.info("Fetched %d zone polygons (%d mapped)", report.polygons_fetched, report.polygons_mapped)

    logger.info("Loading ACT SA2 geometries ...")
    sa2_gdf = _load_act_sa2s(db)
    logger.info("Loaded %d ACT SA2 polygons", len(sa2_gdf))
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

def _fetch_all_zones(report: ACTZoningReport):
    import geopandas as gpd

    session = requests.Session()
    session.verify = False
    session.headers["User-Agent"] = "SuburbIntel/1.0"

    records: list[dict] = []
    offset = 0

    while True:
        params = {
            "where":             "CURRENT_LIFECYCLE_STAGE='GAZETTED'",
            "outFields":         "OBJECTID,LAND_USE_ZONE_CODE_ID",
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
            code_raw = (attrs.get("LAND_USE_ZONE_CODE_ID") or "").strip()
            cat      = _ACT_CODE_TO_CAT.get(code_raw, "other")

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

def _load_act_sa2s(db: Session):
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

    logger.info("  Running spatial overlay (zone polygons x SA2s) ...")
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
