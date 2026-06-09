"""SA Planning and Design Code Zones loader.

Reads the SA Planning and Design Code (P&D Code) zone polygons from a local
GeoJSON zip downloaded from data.sa.gov.au, intersects them with SA2 boundaries,
and writes zone-class percentage breakdowns to sa2_zoning.

Data source
───────────
SA Planning and Design Code Zones — GeoJSON download
Download URL: https://www.dptiapps.com.au/dataportal/PDCodeZones_geojson.zip
Dataset page: https://data.sa.gov.au/data/dataset/planning-and-design-code-zones
Updated: Fortnightly
Licence: Creative Commons Attribution 4.0

To refresh:
    curl -L https://www.dptiapps.com.au/dataportal/PDCodeZones_geojson.zip \
         -o data/zoning/sa_zones_geojson.zip
    python -m app.ingestion.sa_zoning --zip data/zoning/sa_zones_geojson.zip

Key field: value — short zone code (e.g. 'N', 'HDN', 'E', 'Con')

Zone code → category mapping
─────────────────────────────
See _SA_CODE_TO_CAT below. Uses SA Planning and Design Code zone definitions.

Tables written
──────────────
sa2_zoning — one row per SA SA2 with zone percentage breakdown (full reload
             of SA rows only)
"""

from __future__ import annotations

import json
import logging
import zipfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import SA2Zoning, SA2Region

logger = logging.getLogger(__name__)

_SOURCE = "SA Planning and Design Code Zones"
_STATE  = "SA"
_GEOJSON_NAME = "PDCodeZones_GDA94.geojson"

# SA P&D Code zone code → internal category
# Reference: https://www.sa.gov.au/topics/planning-and-property/planning-and-design-code
_SA_CODE_TO_CAT: dict[str, str] = {
    # ── High-density residential ──────────────────────────────────────────
    "CC":      "high_density_res",      # Capital City
    "CL":      "high_density_res",      # City Living
    "CR":      "high_density_res",      # City Riverbank
    "URN":     "high_density_res",      # Urban Renewal Neighbourhood
    "HDN":     "high_density_res",      # Housing Diversity Neighbourhood

    # ── Medium-density residential ────────────────────────────────────────
    "UN":      "medium_density_res",    # Urban Neighbourhood
    "WN":      "medium_density_res",    # Waterfront Neighbourhood
    "MPR":     "medium_density_res",    # Master Planned Renewal
    "UC(L)":   "medium_density_res",    # Urban Corridor (Living)

    # ── Low-density / general residential ────────────────────────────────
    "N":       "low_density_res",       # Neighbourhood
    "GN":      "low_density_res",       # General Neighbourhood
    "EN":      "low_density_res",       # Established Neighbourhood
    "SN":      "low_density_res",       # Suburban Neighbourhood
    "HN":      "low_density_res",       # Hills Neighbourhood
    "TN":      "low_density_res",       # Township Neighbourhood
    "MPN":     "low_density_res",       # Master Planned Neighbourhood
    "MPT":     "low_density_res",       # Master Planned Township
    "T":       "low_density_res",       # Township
    "GCE":     "low_density_res",       # Golf Course Estate
    "WS":      "low_density_res",       # Workers' Settlement

    # ── Large-lot / rural residential ─────────────────────────────────────
    "RuL":     "large_lot_res",         # Rural Living
    "RuS":     "large_lot_res",         # Rural Settlement
    "RuShS":   "large_lot_res",         # Rural Shack Settlement
    "RuN":     "large_lot_res",         # Rural Neighbourhood
    "RP":      "large_lot_res",         # Residential Park

    # ── Mixed use ─────────────────────────────────────────────────────────
    "UC(MS)":  "mixed_use",             # Urban Corridor (Main Street)
    "UC(Bu)":  "mixed_use",             # Urban Corridor (Business)
    "UC(Bo)":  "mixed_use",             # Urban Corridor (Boulevard)

    # ── Commercial / activity centres ─────────────────────────────────────
    "LAC":     "commercial",            # Local Activity Centre
    "SAC":     "commercial",            # Suburban Activity Centre
    "UAC":     "commercial",            # Urban Activity Centre
    "TAC":     "commercial",            # Township Activity Centre
    "SMS":     "commercial",            # Suburban Main Street
    "TMS":     "commercial",            # Township Main Street
    "CMS":     "commercial",            # City Main Street
    "SB":      "commercial",            # Suburban Business
    "BN":      "commercial",            # Business Neighbourhood
    "TD":      "commercial",            # Tourism Development
    "CTP":     "commercial",            # Caravan and Tourist Park
    "HIn":     "commercial",            # Home Industry
    "MP":      "commercial",            # Motorsport Park

    # ── Industrial / employment ───────────────────────────────────────────
    "E":       "industrial",            # Employment
    "SE":      "industrial",            # Strategic Employment
    "E(BH)":   "industrial",            # Employment (Bulk Handling)
    "E(En)":   "industrial",            # Employment (Enterprise)
    "SInv":    "industrial",            # Strategic Innovation
    "RE":      "industrial",            # Resource Extraction

    # ── Public open space / recreation ───────────────────────────────────
    "OS":      "public_recreation",     # Open Space
    "Rec":     "public_recreation",     # Recreation
    "APL":     "public_recreation",     # Adelaide Park Lands

    # ── Environmental / conservation ──────────────────────────────────────
    "Con":     "environmental",         # Conservation
    "HF":      "environmental",         # Hills Face
    "CWOI":    "environmental",         # Coastal Waters and Offshore Islands
    "PRuL":    "environmental",         # Productive Rural Landscape

    # ── Rural / primary production ────────────────────────────────────────
    "Ru":      "rural",                 # Rural
    "RuH":     "rural",                 # Rural Horticulture
    "RuAq":    "rural",                 # Rural Aquaculture
    "RuIE":    "rural",                 # Rural Intensive Enterprise
    "RA":      "rural",                 # Remote Areas

    # ── Urban development / growth ────────────────────────────────────────
    "DU":      "urban_development",     # Deferred Urban

    # ── Infrastructure / civic / community ───────────────────────────────
    "Inf":     "infrastructure",        # Infrastructure
    "Inf(A)":  "infrastructure",        # Infrastructure (Airfield)
    "Inf(FMF)":"infrastructure",        # Infrastructure (Ferry and Marina Facilities)
    "CF":      "infrastructure",        # Community Facilities
    "CwF":     "infrastructure",        # Commonwealth Facilities
}

# Categories that roll up into residential_total
_RESIDENTIAL_CATS = frozenset({
    "high_density_res", "medium_density_res", "low_density_res", "large_lot_res",
})


@dataclass
class SAZoningReport:
    polygons_read:   int = 0
    polygons_mapped: int = 0
    sa2s_processed:  int = 0
    sa2s_written:    int = 0

    def __str__(self) -> str:
        return (
            f"Polygons read: {self.polygons_read} | "
            f"Mapped to category: {self.polygons_mapped} | "
            f"SA SA2s processed: {self.sa2s_processed} | "
            f"SA2 zoning rows written: {self.sa2s_written}"
        )


def load_sa_zoning(zip_path: Path, db: Session) -> SAZoningReport:
    report = SAZoningReport()

    logger.info("Reading SA P&D Code zones from %s ...", zip_path.name)
    zone_gdf = _read_zones(zip_path, report)
    logger.info("Read %d polygons, mapped %d to categories", report.polygons_read, report.polygons_mapped)

    logger.info("Loading SA SA2 geometries ...")
    sa2_gdf = _load_sa_sa2s(db)
    logger.info("Loaded %d SA SA2 polygons", len(sa2_gdf))
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
# Read GeoJSON zip
# ---------------------------------------------------------------------------

def _read_zones(zip_path: Path, report: SAZoningReport):
    import geopandas as gpd
    from shapely.geometry import shape

    records: list[dict] = []

    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(_GEOJSON_NAME) as fh:
            data = json.load(fh)

    for feat in data.get("features", []):
        report.polygons_read += 1
        props    = feat.get("properties", {})
        code     = (props.get("value") or "").strip()
        cat      = _SA_CODE_TO_CAT.get(code, "other")

        geom_raw = feat.get("geometry")
        if not geom_raw:
            continue
        try:
            geom = shape(geom_raw)
            if not geom.is_valid:
                geom = geom.buffer(0)
            if not geom.is_empty:
                records.append({"category": cat, "geometry": geom})
                if cat != "other":
                    report.polygons_mapped += 1
        except Exception:
            pass

    return gpd.GeoDataFrame(records, crs="EPSG:4326")


# ---------------------------------------------------------------------------
# SA2 loader
# ---------------------------------------------------------------------------

def _load_sa_sa2s(db: Session):
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
