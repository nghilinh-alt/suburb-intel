"""Planning zones loader — QLD Priority Development Areas (PDAs).

Fetches PDA polygon boundaries from the QLD Spatial ArcGIS service, intersects
them with SA2 polygons, and writes overlap-weighted links.

Data source
───────────
QLD AdminBoundariesFramework MapServer — layer 196 (Priority development area)
URL: https://spatial-gis.information.qld.gov.au/arcgis/rest/services/
     Boundaries/AdminBoundariesFramework/MapServer/196

Migration history
─────────────────
Previously used EDQ PlanningCadastre/PriorityDevelopmentAreas/MapServer/10.
That service was deprecated 26 June 2026. Migrated to AdminBoundariesFramework
layer 196 which carries the same PDA polygons with identical field names
(pda_name, pda_status, lga_name, gazetted_date, objectid). 43 PDAs as of
June 2026 (was 39 — 4 new PDAs declared since last run).

Tables written
──────────────
planning_zones     — one row per PDA (upsert on zone_id)
sa2_planning_link  — SA2 ↔ PDA with overlap_pct (full reload)

Impact score = fraction of SA2 area covered by the PDA polygon (0–1).
Any SA2 with >0% overlap is linked (no minimum threshold).
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import requests
import urllib3
from sqlalchemy.orm import Session

from app.db.models import PlanningZone, SA2PlanningLink, SA2Region

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

_EDQ_URL   = (
    "https://spatial-gis.information.qld.gov.au/arcgis/rest/services"
    "/Boundaries/AdminBoundariesFramework/MapServer/196/query"
)
_SOURCE    = "QLD AdminBoundariesFramework PDA (layer 196)"
_ZONE_TYPE = "PDA"
_STATE     = "QLD"


@dataclass
class PlanningZoneReport:
    zones_fetched:  int = 0
    zones_upserted: int = 0
    sa2_links:      int = 0

    def __str__(self) -> str:
        return (
            f"Zones fetched: {self.zones_fetched} | "
            f"Zones upserted: {self.zones_upserted} | "
            f"SA2 links: {self.sa2_links}"
        )


def load_planning_zones(db: Session) -> PlanningZoneReport:
    report = PlanningZoneReport()

    logger.info("Fetching EDQ Priority Development Areas ...")
    features = _fetch_pda_features(report)
    logger.info("Fetched %d PDA features", report.zones_fetched)

    logger.info("Loading SA2 geometries for intersection ...")
    sa2_gdf = _load_sa2_gdf(db)
    logger.info("Loaded %d SA2 polygons", len(sa2_gdf))

    # Full reload of links
    db.query(SA2PlanningLink).delete(synchronize_session=False)

    for feat in features:
        attrs    = feat.get("attributes", {})
        geom_raw = feat.get("geometry")
        oid      = attrs.get("objectid")
        zone_id  = f"pda-{oid}"

        name   = (attrs.get("pda_name") or "").strip()
        status = (attrs.get("pda_status") or "").strip()
        lga    = (attrs.get("lga_name") or "").strip()

        # Convert epoch ms to ISO date
        gaz_epoch = attrs.get("gazetted_date")
        gaz_date  = None
        if gaz_epoch:
            try:
                gaz_date = datetime.fromtimestamp(gaz_epoch / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
            except Exception:
                pass

        # Convert ArcGIS ring geometry → GeoJSON polygon
        geojson_str = None
        shapely_geom = None
        if geom_raw:
            try:
                geojson_str, shapely_geom = _arcgis_rings_to_geojson(geom_raw)
            except Exception as exc:
                logger.warning("PDA %s geometry conversion failed: %s", zone_id, exc)

        existing = db.get(PlanningZone, zone_id)
        fields = dict(
            name=name,
            zone_type=_ZONE_TYPE,
            status=status,
            lga_name=lga,
            gazetted_date=gaz_date,
            state=_STATE,
            source=_SOURCE,
            geometry_geojson=geojson_str,
        )
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(PlanningZone(zone_id=zone_id, **fields))
        report.zones_upserted += 1

        # SA2 overlap links
        if shapely_geom is not None:
            links = _compute_sa2_overlaps(shapely_geom, sa2_gdf)
            for sa2_code, overlap_pct in links:
                db.add(SA2PlanningLink(
                    sa2_code=sa2_code,
                    zone_id=zone_id,
                    overlap_pct=round(overlap_pct, 4),
                    impact_score=round(min(overlap_pct, 1.0), 4),
                ))
                report.sa2_links += 1

    db.commit()
    return report


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------

def _fetch_pda_features(report: PlanningZoneReport) -> list[dict]:
    session = requests.Session()
    session.verify = False
    session.headers["User-Agent"] = "SuburbIntel/1.0"

    params = {
        "where":          "1=1",
        "outFields":      "objectid,pda_name,pda_status,lga_name,gazetted_date",
        "returnGeometry": "true",
        "outSR":          "4326",
        "f":              "json",
    }
    try:
        resp = session.get(_EDQ_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.error("EDQ fetch failed: %s", exc)
        return []

    features = data.get("features", [])
    report.zones_fetched = len(features)
    return features


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _arcgis_rings_to_geojson(geom_raw: dict) -> tuple[str, object]:
    """Convert ArcGIS ring geometry dict to (GeoJSON string, shapely geometry)."""
    from shapely.geometry import Polygon, MultiPolygon, shape

    rings = geom_raw.get("rings", [])
    if not rings:
        raise ValueError("No rings in geometry")

    if len(rings) == 1:
        geojson = {"type": "Polygon", "coordinates": rings}
    else:
        geojson = {"type": "MultiPolygon", "coordinates": [[r] for r in rings]}

    shapely_geom = shape(geojson)
    if not shapely_geom.is_valid:
        shapely_geom = shapely_geom.buffer(0)

    return json.dumps(geojson), shapely_geom


def _load_sa2_gdf(db: Session):
    import geopandas as gpd
    from shapely.geometry import shape

    rows = db.query(SA2Region.sa2_code, SA2Region.geometry_geojson).all()
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
    gdf["sa2_area"] = gdf.geometry.area  # in degrees² — fine for relative overlap
    return gdf


def _compute_sa2_overlaps(pda_geom, sa2_gdf) -> list[tuple[str, float]]:
    """Return [(sa2_code, overlap_pct)] for all SA2s that intersect the PDA."""
    import warnings
    results = []

    # Coarse bounding-box filter first
    pda_bounds = pda_geom.bounds  # (minx, miny, maxx, maxy)
    candidates = sa2_gdf[
        (sa2_gdf.geometry.bounds["maxx"] >= pda_bounds[0]) &
        (sa2_gdf.geometry.bounds["minx"] <= pda_bounds[2]) &
        (sa2_gdf.geometry.bounds["maxy"] >= pda_bounds[1]) &
        (sa2_gdf.geometry.bounds["miny"] <= pda_bounds[3])
    ]

    for _, row in candidates.iterrows():
        sa2_geom = row.geometry
        if not sa2_geom.intersects(pda_geom):
            continue
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore")
                intersection = sa2_geom.intersection(pda_geom)
            overlap_pct = intersection.area / row["sa2_area"] if row["sa2_area"] > 0 else 0.0
            if overlap_pct > 0:
                results.append((row["sa2_code"], overlap_pct))
        except Exception as exc:
            logger.debug("Intersection error for SA2 %s: %s", row["sa2_code"], exc)

    return results
