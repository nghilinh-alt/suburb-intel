"""NSW Land Zoning loader.

Fetches all NSW LEP (Local Environmental Plan) zoning polygons from the NSW
Planning Portal ArcGIS service, intersects them with SA2 boundaries, and writes
zone-class percentage breakdowns to the sa2_zoning table.

Data source
───────────
NSW Planning Portal — EPI Primary Planning Layers, Layer 2: Land Zoning
URL: https://mapprod3.environment.nsw.gov.au/arcgis/rest/services/Planning/
     EPI_Primary_Planning_Layers/MapServer/2
Updated: Weekly by NSW Planning Portal
Licence: Creative Commons Attribution 4.0

Key field: LAY_CLASS — the zone class name (e.g. 'High Density Residential')

Zone class → category mapping
──────────────────────────────
See _LAY_CLASS_TO_CAT below. Unrecognised classes fall into 'other'.
'Deferred Matter' and 'Unzoned Land'/'Unzoned' are skipped entirely.

Tables written
──────────────
sa2_zoning — one row per NSW SA2 with zone percentage breakdown (full reload)

Usage (CLI):
    python -m app.ingestion.nsw_zoning
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import date

import requests
import urllib3
from sqlalchemy.orm import Session

from app.db.models import SA2Zoning, SA2Region

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

_SERVICE_URL = (
    "https://mapprod3.environment.nsw.gov.au/arcgis/rest/services"
    "/Planning/EPI_Primary_Planning_Layers/MapServer/2/query"
)
_PAGE_SIZE    = 2000
_REQUEST_DELAY = 0.3
_SOURCE       = "NSW Planning Portal EPI Land Zoning"
_STATE        = "NSW"

# LAY_CLASS values to skip (not real zones)
_SKIP_CLASSES = frozenset({
    "Deferred Matter", "Unzoned Land", "Unzoned", "Land Reservation Acquisition",
})

# LAY_CLASS → internal category
_LAY_CLASS_TO_CAT: dict[str, str] = {
    # High density residential
    "High Density Residential":           "high_density_res",
    # Medium density residential
    "Medium Density Residential":         "medium_density_res",
    "Residential Zone - Medium Density Residential": "medium_density_res",
    # Low / general residential
    "Low Density Residential":            "low_density_res",
    "General Residential":                "low_density_res",
    "Village":                            "low_density_res",
    "Residential":                        "low_density_res",
    "Residential (Low Density)":          "low_density_res",
    # Large lot / rural residential
    "Large Lot Residential":              "large_lot_res",
    # Mixed use
    "Mixed Use":                          "mixed_use",
    "Business Zone - Mixed Use":          "mixed_use",
    "Residential - Business":             "mixed_use",
    "Residential – Business":        "mixed_use",
    # Commercial centres
    "Local Centre":                       "commercial",
    "Neighbourhood Centre":               "commercial",
    "Commercial Centre":                  "commercial",
    "Metropolitan Centre":                "commercial",
    "Commercial Core":                    "commercial",
    "Business Development":               "commercial",
    "Business Park":                      "commercial",
    "Business Zone - Commercial Core":    "commercial",
    "Business Zone - Local Centre":       "commercial",
    "Business Zone - Business Park":      "commercial",
    # Industrial / employment
    "General Industrial":                 "industrial",
    "Heavy Industrial":                   "industrial",
    "Light Industrial":                   "industrial",
    "Enterprise":                         "industrial",
    "Enterprise Corridor":                "industrial",
    "Special Activities":                 "industrial",
    "Port and Employment":                "industrial",
    "Agribusiness":                       "industrial",
    "Working Waterfront":                 "industrial",
    "Working Waterways":                  "industrial",
    "Regional Enterprise Zone":           "industrial",
    "Productivity Support":               "industrial",
    "Employment":                         "industrial",
    # Public open space / recreation
    "Public Recreation":                  "public_recreation",
    "Public Recreation - Regional":       "public_recreation",
    "Public Recreation – Preferred Locations": "public_recreation",
    "Recreation Zone - Public Recreation": "public_recreation",
    "Open Space":                         "public_recreation",
    "Regional Open Space":                "public_recreation",
    "Parkland":                           "public_recreation",
    "Regional Park":                      "public_recreation",
    "Environment and Recreation":         "public_recreation",
    "Recreation":                         "public_recreation",
    "Permanent Park Preserve":            "public_recreation",
    # Private recreation / tourism
    "Private Recreation":                 "private_recreation",
    "Tourist":                            "private_recreation",
    "Tourism":                            "private_recreation",
    "Recreation Zone - Private Recreation": "private_recreation",
    # Environmental
    "Environmental Conservation":         "environmental",
    "Environmental Management":           "environmental",
    "Environmental Living":               "environmental",
    "Natural Waterways":                  "environmental",
    "Recreational Waterways":             "environmental",
    "Environment Protection":             "environmental",
    "Environmental Protection (Wetlands and Littoral Rainforests)": "environmental",
    "Environmental Protection (Habitat)": "environmental",
    "Environment":                        "environmental",
    "Marine Park":                        "environmental",
    "National Parks and Nature Reserves": "environmental",
    # Infrastructure
    "Infrastructure":                     "infrastructure",
    "Special Purposes Zone - Infrastructure": "infrastructure",
    "Special Purposes Zone - Comminity":  "infrastructure",
    "Road and Road Widening":             "infrastructure",
    "Railways":                           "infrastructure",
    "Drainage":                           "infrastructure",
    "Waterway":                           "infrastructure",
    "Waterfront Use":                     "infrastructure",
    "Special Uses":                       "infrastructure",
    # Primary production / rural
    "Primary Production":                 "rural",
    "Primary Production Small Lots":      "rural",
    "Rural Landscape":                    "rural",
    "Forestry":                           "rural",
    "Rural":                              "rural",
    "Rural Activity Zone":                "rural",
    # Urban development / transition
    "Urban Development":                  "urban_development",
    "Urban":                              "urban_development",
    "Urban Expansion":                    "urban_development",
    "Settlement":                         "urban_development",
    "Transition":                         "urban_development",
    # Catch-all
    "Port and Employment":                "industrial",
}

# Categories that roll up into residential_total
_RESIDENTIAL_CATS = frozenset({
    "high_density_res", "medium_density_res", "low_density_res", "large_lot_res",
})


@dataclass
class NSWZoningReport:
    polygons_fetched: int = 0
    sa2s_processed:   int = 0
    sa2s_written:     int = 0

    def __str__(self) -> str:
        return (
            f"Polygons fetched: {self.polygons_fetched} | "
            f"NSW SA2s processed: {self.sa2s_processed} | "
            f"SA2 zoning rows written: {self.sa2s_written}"
        )


def load_nsw_zoning(db: Session) -> NSWZoningReport:
    report = NSWZoningReport()

    logger.info("Fetching NSW zoning polygons ...")
    zone_gdf = _fetch_all_zones(report)
    logger.info("Fetched %d zone polygons", report.polygons_fetched)

    logger.info("Loading NSW SA2 geometries ...")
    sa2_gdf = _load_nsw_sa2s(db)
    logger.info("Loaded %d NSW SA2 polygons", len(sa2_gdf))
    report.sa2s_processed = len(sa2_gdf)

    logger.info("Computing zone intersections (this may take a few minutes) ...")
    zoning_by_sa2 = _compute_zoning(zone_gdf, sa2_gdf)

    logger.info("Writing to sa2_zoning table ...")
    # Full reload for NSW
    db.query(SA2Zoning).filter(SA2Zoning.state == _STATE).delete(synchronize_session=False)

    today = date.today().isoformat()
    for sa2_code, cats in zoning_by_sa2.items():
        total_res = sum(cats.get(c, 0.0) for c in _RESIDENTIAL_CATS)
        row = SA2Zoning(
            sa2_code=sa2_code,
            state=_STATE,
            zone_pct_high_density_res  = round(cats.get("high_density_res", 0.0), 2),
            zone_pct_medium_density_res = round(cats.get("medium_density_res", 0.0), 2),
            zone_pct_low_density_res   = round(cats.get("low_density_res", 0.0), 2),
            zone_pct_large_lot_res     = round(cats.get("large_lot_res", 0.0), 2),
            zone_pct_residential_total = round(total_res, 2),
            zone_pct_mixed_use         = round(cats.get("mixed_use", 0.0), 2),
            zone_pct_commercial        = round(cats.get("commercial", 0.0), 2),
            zone_pct_industrial        = round(cats.get("industrial", 0.0), 2),
            zone_pct_public_recreation = round(cats.get("public_recreation", 0.0), 2),
            zone_pct_environmental     = round(cats.get("environmental", 0.0), 2),
            zone_pct_urban_development = round(cats.get("urban_development", 0.0), 2),
            zone_breakdown_json        = {k: round(v, 2) for k, v in cats.items()},
            source                     = _SOURCE,
            source_date                = today,
        )
        db.add(row)
        report.sa2s_written += 1

    db.commit()
    return report


# ---------------------------------------------------------------------------
# Fetch
# ---------------------------------------------------------------------------

def _fetch_all_zones(report: NSWZoningReport):
    """Fetch all NSW zoning polygons and return a GeoDataFrame."""
    import geopandas as gpd
    from shapely.geometry import Polygon, MultiPolygon, shape as shp_shape

    session = requests.Session()
    session.verify = False
    session.headers["User-Agent"] = "SuburbIntel/1.0"

    records: list[dict] = []
    offset = 0

    while True:
        params = {
            "where":             "1=1",
            "outFields":         "OBJECTID,LAY_CLASS",
            "returnGeometry":    "true",
            "outSR":             "4326",
            "resultOffset":      offset,
            "resultRecordCount": _PAGE_SIZE,
            "f":                 "json",
        }
        try:
            resp = session.get(_SERVICE_URL, params=params, timeout=60)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Fetch failed at offset %d: %s", offset, exc)
            break

        features = data.get("features", [])
        for feat in features:
            attrs = feat.get("attributes", {})
            lay_class = attrs.get("LAY_CLASS") or ""

            if lay_class in _SKIP_CLASSES:
                continue

            cat = _LAY_CLASS_TO_CAT.get(lay_class, "other")
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

        # Increment by actual records returned — server may cap below _PAGE_SIZE
        offset += len(features)
        time.sleep(_REQUEST_DELAY)

    return gpd.GeoDataFrame(records, crs="EPSG:4326")


def _rings_to_shapely(geom_raw: dict):
    """Convert ArcGIS ring dict to a valid shapely geometry."""
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

def _load_nsw_sa2s(db: Session):
    """Load NSW SA2 polygons as a GeoDataFrame."""
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

def _compute_zoning(
    zone_gdf,
    sa2_gdf,
) -> dict[str, dict[str, float]]:
    """Return {sa2_code: {category: pct_of_sa2_area}} for all NSW SA2s."""
    import warnings
    import geopandas as gpd

    # Spatial join: assign each zone polygon to the SA2s it overlaps
    logger.info("  Running spatial overlay (zone polygons × SA2s) ...")

    # Use overlay to compute intersections
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

    # Compute intersection area
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore")
        intersected["isect_area"] = intersected.geometry.area

    # Aggregate: sum intersection area per (sa2_code, category)
    agg = (
        intersected.groupby(["sa2_code", "category"])["isect_area"]
        .sum()
        .reset_index()
    )

    # Build result dict: pct = isect_area / sa2_area * 100
    sa2_area_map = dict(zip(sa2_gdf["sa2_code"], sa2_gdf["sa2_area"]))
    result: dict[str, dict[str, float]] = {}

    for _, row in agg.iterrows():
        sa2 = row["sa2_code"]
        cat = row["category"]
        area = row["isect_area"]
        sa2_area = sa2_area_map.get(sa2, 0)
        if sa2_area > 0:
            pct = (area / sa2_area) * 100.0
            result.setdefault(sa2, {})[cat] = result.get(sa2, {}).get(cat, 0.0) + pct

    return result
