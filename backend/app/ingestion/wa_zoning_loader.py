"""WA Local Planning Scheme Zones loader.

Fetches all Western Australian planning scheme zone polygons from the public
SLIP (Spatial Land Information Platform) ArcGIS service, intersects them with
SA2 boundaries, and writes zone-class percentage breakdowns to sa2_zoning.

Data source
───────────
SLIP Public Services — Property_and_Planning MapServer, Layer 112
URL: https://public-services.slip.wa.gov.au/public/rest/services/
     SLIP_Public_Services/Property_and_Planning/MapServer/112
Updated: Continuously (WAPC and local scheme amendments propagate within days)
Licence: Creative Commons Attribution 4.0 (public tier)

Key field: zone — free-text zone name from the local planning scheme.
           WA aggregates 137+ individual LGA planning schemes, so there are
           434+ distinct zone name variants. We use keyword matching.

Tables written
──────────────
sa2_zoning — one row per WA SA2 with zone percentage breakdown (full reload
             of WA rows only)

Usage (CLI):
    python -m app.ingestion.wa_zoning
"""

from __future__ import annotations

import json
import logging
import re
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
    "https://public-services.slip.wa.gov.au/public/rest/services"
    "/SLIP_Public_Services/Property_and_Planning/MapServer/112/query"
)
_PAGE_SIZE     = 2000
_REQUEST_DELAY = 0.3
_SOURCE        = "WA SLIP Property_and_Planning Layer 112"
_STATE         = "WA"

# Zones to skip entirely (non-zoned, water, roads-only)
_SKIP_PATTERNS = re.compile(
    r"^(no zone|ocean|waterway|water way|lake|road$|roads$|highway$|railway$|"
    r"district road|local road|regional road|major road|primary distributor|"
    r"state.*road|important.*road|major highway|drainage$|crown reserve$)$",
    re.IGNORECASE,
)

# Ordered rules: first match wins.
# Each rule: (compiled regex, category)
_ZONE_RULES: list[tuple[re.Pattern, str]] = [
    # ── High-density residential ──────────────────────────────────────────
    (re.compile(r"medium and high density|high density|mixed use residential|"
                r"residential redevelopment|normalised redevelopment", re.I),  "high_density_res"),

    # ── Medium-density residential ────────────────────────────────────────
    (re.compile(r"medium density|townsite\b|townsite zone|town(site)? development|"
                r"special mix residential|residential.*office|office.*residential|"
                r"residential.*commercial|commercial.*residential|residential.*business",
                re.I),                                                          "medium_density_res"),

    # ── Large-lot / rural residential ────────────────────────────────────
    (re.compile(r"rural living|rural residential|rural small.?holding|"
                r"rural retreat|rural multiple|rural village|rural.*townsite|"
                r"residential bushland|residential and stables|"
                r"large.?lot|special residential|special rural",
                re.I),                                                          "large_lot_res"),

    # ── Low-density / general residential ────────────────────────────────
    (re.compile(r"\bresidential\b|urban [0-9].*residential|urban 4|settlement\b",
                re.I),                                                          "low_density_res"),

    # ── Mixed use ─────────────────────────────────────────────────────────
    (re.compile(r"mixed use|mixed business.*residential|business.*residential|"
                r"mixed.*commercial|village centre|foreshore centre",
                re.I),                                                          "mixed_use"),

    # ── Commercial / activity centres ─────────────────────────────────────
    (re.compile(r"city centre|town centre|strategic.*centre|regional centre|"
                r"district centre|neighbourhood centre|local centre|"
                r"neighbourhood commercial|neighbourhood.*mixed|"
                r"commercial|business\b|business development|business park|"
                r"showroom|service commercial|hotel|tourist enterprise|"
                r"tourism\b|tourist\b|viticulture|service station|"
                r"medical\b|medical service|professional office|"
                r"civic.*commercial|market square|enterprise\b|"
                r"smart growth|foreshore.*commercial|special.*business|"
                r"shopping|caravan park|caravan.*cabin|chalet",
                re.I),                                                          "commercial"),

    # ── Industrial / employment ───────────────────────────────────────────
    (re.compile(r"general industrial|light industrial|light industry|"
                r"general industry|heavy industry|strategic industry|"
                r"marine.*industry|composite industry|industrial.*development|"
                r"industrial.*business|mixed business|special industry|"
                r"port installation|harbour|strategic infrastructure|"
                r"rural industry|industrial\b|industry\b",
                re.I),                                                          "industrial"),

    # ── Public open space / recreation ───────────────────────────────────
    (re.compile(r"public open space|local open space|parks and recreation|"
                r"park.*recreation|recreation.*park|local parks|"
                r"public.*recreation|open space\b|recreation\b|recreational\b|"
                r"local reserve.*recreation|local public open",
                re.I),                                                          "public_recreation"),

    # ── Environmental / conservation ──────────────────────────────────────
    (re.compile(r"national park|nature reserve|conservation|bushland|"
                r"foreshore protection|landscape protection|"
                r"hills landscape|leeuwin|environmental.*conservation|"
                r"cultural and natural|state forest|"
                r"environmental\b|landscape\b|heritage\b|"
                r"water supply|water production",
                re.I),                                                          "environmental"),

    # ── Rural / primary production ────────────────────────────────────────
    (re.compile(r"agriculture|agricultural|farming|general farming|pastoral|"
                r"rural.*agriculture|rural.*farming|general rural|"
                r"rural composite|rural enterprise|horticulture|"
                r"local horticulture|rural [a-z0-9]|rural$|"
                r"swan valley rural",
                re.I),                                                          "rural"),

    # ── Urban development / growth ────────────────────────────────────────
    (re.compile(r"future development|urban development|development\b|"
                r"special development|urban [0-9]",
                re.I),                                                          "urban_development"),

    # ── Infrastructure / civic / community ───────────────────────────────
    (re.compile(r"infrastructure|civic|community|education|educational|"
                r"public purpose|public use|public utilities|special use|"
                r"special purpose|place of.*assembly|church|institution|"
                r"cemetery|car park|emergency|social care|"
                r"government service|resource\b",
                re.I),                                                          "infrastructure"),
]


def _classify_zone(zone: str) -> str:
    """Map a WA zone name to one of our 11 internal categories."""
    z = zone.strip()
    if not z or _SKIP_PATTERNS.match(z):
        return "__skip__"
    for pattern, cat in _ZONE_RULES:
        if pattern.search(z):
            return cat
    return "other"


# Categories that roll up into residential_total
_RESIDENTIAL_CATS = frozenset({
    "high_density_res", "medium_density_res", "low_density_res", "large_lot_res",
})


@dataclass
class WAZoningReport:
    polygons_fetched: int = 0
    polygons_skipped: int = 0
    sa2s_processed:   int = 0
    sa2s_written:     int = 0

    def __str__(self) -> str:
        return (
            f"Polygons fetched: {self.polygons_fetched} | "
            f"Skipped (no-zone/roads): {self.polygons_skipped} | "
            f"WA SA2s processed: {self.sa2s_processed} | "
            f"SA2 zoning rows written: {self.sa2s_written}"
        )


def load_wa_zoning(db: Session) -> WAZoningReport:
    report = WAZoningReport()

    logger.info("Fetching WA planning scheme zone polygons ...")
    zone_gdf = _fetch_all_zones(report)
    logger.info("Fetched %d zone polygons (%d skipped)", report.polygons_fetched, report.polygons_skipped)

    logger.info("Loading WA SA2 geometries ...")
    sa2_gdf = _load_wa_sa2s(db)
    logger.info("Loaded %d WA SA2 polygons", len(sa2_gdf))
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

def _fetch_all_zones(report: WAZoningReport):
    import geopandas as gpd

    session = requests.Session()
    session.verify = False
    session.headers["User-Agent"] = "SuburbIntel/1.0"

    records: list[dict] = []
    offset = 0

    while True:
        params = {
            "where":             "1=1",
            "outFields":         "objectid,zone",
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
            zone_raw = (attrs.get("zone") or "").strip()
            cat      = _classify_zone(zone_raw)

            if cat == "__skip__":
                report.polygons_skipped += 1
                continue

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

def _load_wa_sa2s(db: Session):
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
