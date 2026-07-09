"""SA2 boundary geometry loader.

Reads the ABS SA2 2021 Shapefile, simplifies polygons for web use, and
upserts GeoJSON geometry strings onto SA2Region rows.

Local (SQLite):  stored as TEXT in sa2_regions.geometry_geojson
PostgreSQL:      ALTER COLUMN geometry_geojson TYPE GEOMETRY(MultiPolygon,4326)
                 USING ST_GeomFromGeoJSON(geometry_geojson);
                 CREATE INDEX ON sa2_regions USING GIST (geometry_geojson);

Source file: SA2_2021_AUST_SHP_GDA2020.zip
Download:    https://www.abs.gov.au/.../SA2_2021_AUST_SHP_GDA2020.zip (48 MB)

Simplification tolerance is ADAPTIVE, scaled to each polygon's own bounding-box
diagonal (diagonal / 500), clamped to [~3 m, ~150 m]. A single fixed ~100 m
tolerance (the original approach) is fine for huge sparse rural SA2s but
devastating for small, compact urban suburbs: Algester's ~2 km-wide polygon
collapsed to just 11 vertices at 100 m tolerance, clipping off a real strip
of the suburb (a shopping/dining stretch with "Algester" literally in the
business names) — meaning every downstream point-in-polygon spatial join
(overture_amenity_loader.py, points_of_interest_loader.py) silently
undercounted amenities there. Scaling tolerance to each polygon's own size
keeps small suburbs sharp while still compacting huge rural SA2s.

Usage (CLI):
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.geometry --shp "../data/datapacks/SA2_2021_AUST_SHP_GDA2020.zip"
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
from sqlalchemy.orm import Session

from app.db.models import SA2Region

logger = logging.getLogger(__name__)

# Adaptive simplification: tolerance = bounding-box diagonal / _TOLERANCE_DIVISOR,
# clamped to [_MIN_TOLERANCE, _MAX_TOLERANCE] degrees. At Australian latitudes,
# 1 degree ≈ 100 km, so _MIN_TOLERANCE ≈ 3 m and _MAX_TOLERANCE ≈ 150 m.
_TOLERANCE_DIVISOR = 500.0
_MIN_TOLERANCE = 0.00003
_MAX_TOLERANCE = 0.0015


@dataclass
class GeometryLoadReport:
    updated: int = 0
    skipped_no_region: int = 0

    def __str__(self) -> str:
        return (
            f"Updated: {self.updated} | "
            f"Skipped (SA2 not in DB): {self.skipped_no_region}"
        )


def load_geometries(
    shp_path: Path,
    db: Session,
) -> GeometryLoadReport:
    """Load simplified SA2 polygons from the ABS Shapefile into sa2_regions.

    Args:
        shp_path: Path to the ABS SA2 Shapefile zip (or extracted .shp file).
        db:       Synchronous SQLAlchemy session.
    """
    report = GeometryLoadReport()

    logger.info("Reading shapefile ...")
    gdf = _load_shapefile(shp_path)
    logger.info("Loaded %d SA2 geometries; simplifying ...", len(gdf))

    gdf = _simplify(gdf)
    logger.info("Simplified. Upserting into sa2_regions ...")

    for _, row in gdf.iterrows():
        sa2_code = str(row["SA2_CODE21"]).zfill(9)
        geojson_str = row["geometry_geojson"]

        region = db.get(SA2Region, sa2_code)
        if region is None:
            report.skipped_no_region += 1
            logger.debug("SA2 %s not in DB — skipping", sa2_code)
            continue

        region.geometry_geojson = geojson_str
        report.updated += 1

    db.commit()
    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_shapefile(path: Path) -> gpd.GeoDataFrame:
    """Read the shapefile (zip or .shp) and reproject to WGS84."""
    # geopandas can read directly from a zip path using /vsizip/ if passed as string
    path_str = str(path)
    if path_str.endswith(".zip"):
        # pyogrio / fiona can open zip files directly
        gdf = gpd.read_file(f"zip://{path_str}")
    else:
        gdf = gpd.read_file(path_str)

    # Reproject to WGS84 (EPSG:4326) for web mapping
    if gdf.crs and gdf.crs.to_epsg() != 4326:
        logger.info("Reprojecting from %s to WGS84 ...", gdf.crs.to_epsg())
        gdf = gdf.to_crs(epsg=4326)

    return gdf


def _adaptive_tolerance(geom) -> float:
    """Simplification tolerance scaled to this polygon's own bounding-box
    diagonal, so small suburbs stay detailed while huge rural SA2s still
    compact down reasonably."""
    minx, miny, maxx, maxy = geom.bounds
    diagonal = ((maxx - minx) ** 2 + (maxy - miny) ** 2) ** 0.5
    tolerance = diagonal / _TOLERANCE_DIVISOR
    return max(_MIN_TOLERANCE, min(_MAX_TOLERANCE, tolerance))


def _simplify(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Simplify geometries (adaptive per-polygon tolerance) and serialize to
    GeoJSON strings."""
    gdf = gdf.copy()
    gdf["geometry"] = gdf["geometry"].apply(
        lambda geom: geom.simplify(_adaptive_tolerance(geom), preserve_topology=True)
        if geom is not None else None
    )
    # Ensure all geometries are MultiPolygon for consistency
    gdf["geometry"] = gdf["geometry"].apply(_to_multipolygon)
    # Serialize each geometry to a compact GeoJSON string
    gdf["geometry_geojson"] = gdf["geometry"].apply(
        lambda geom: json.dumps(geom.__geo_interface__, separators=(",", ":"))
        if geom is not None else None
    )
    return gdf


def _to_multipolygon(geom):
    """Convert Polygon → MultiPolygon so the type is consistent."""
    from shapely.geometry import MultiPolygon, Polygon
    if geom is None:
        return None
    if isinstance(geom, Polygon):
        return MultiPolygon([geom])
    return geom
