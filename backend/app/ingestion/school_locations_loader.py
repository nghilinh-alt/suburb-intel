"""School location loader — name/type/coordinates from Overture Maps places.

Not ratings. ACARA's School ICSEA data (school_icsea_loader.py) is gated
behind commercial-use terms we didn't accept, so there's no quality/index
score here — just "what schools exist and where", which needs no such
agreement (Overture Maps places are ODbL-licensed open data).

The main Overture amenity download (overture_amenity_loader.py) explicitly
excludes education categories from its S3 query. This is a separate,
narrower download scoped to just school-shaped categories, verified by
querying the real category names present in Overture's AU places directly
(see category list below — deliberately excludes hobby/vocational
"schools" like dance_school, driving_school, music_school etc, which
aren't K-12/tertiary education).

Also computes and stores `sa2_regions.adjacent_sa2_codes` (SA2s sharing a
border) if not already populated — that's what powers "schools in
surrounding suburbs" on the suburb report, without expensive per-request
geometry operations.

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.school_locations --download
    python -m app.ingestion.school_locations
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import LocalSchool, SA2Region

logger = logging.getLogger(__name__)

_OVERTURE_RELEASE = "2026-05-20.0"
_S3_PATH = (
    f"s3://overturemaps-us-west-2/release/{_OVERTURE_RELEASE}"
    "/theme=places/type=place/*"
)
_AU_BBOX = (112.0, -44.5, 155.0, -9.0)  # west, south, east, north

# Overture categories.primary -> friendly level label. Verified against the
# real category values present in Overture's AU places (queried live via
# DuckDB against the S3 source) — deliberately excludes non-K-12/tertiary
# "schools" (dance_school, driving_school, music_school, cosmetology_school,
# flight_school, cooking_school, language_school, massage_school,
# bartending_school, surfing_school, ski_and_snowboard_school, circus_school,
# drama_school, art_school, sports_school) and admin/support categories
# (educational_services, school_district_offices, board_of_education_offices,
# university_housing, educational_supply_store, educational_research_institute).
_OVERTURE_SCHOOL_CATEGORIES: dict[str, str] = {
    "preschool": "Early Childhood",
    "day_care_preschool": "Early Childhood",
    "elementary_school": "Primary School",
    "middle_school": "Middle School",
    "high_school": "Secondary School",
    "school": "School",
    "public_school": "School",
    "private_school": "School",
    "religious_school": "School",
    "charter_school": "School",
    "montessori_school": "School",
    "waldorf_school": "School",
    "college_university": "University/College",
    "vocational_and_technical_school": "Vocational/TAFE",
}


@dataclass
class SchoolLoadReport:
    schools_loaded: int = 0
    schools_matched: int = 0
    adjacency_computed_for: int = 0

    def __str__(self) -> str:
        return (
            f"Schools loaded: {self.schools_loaded} | "
            f"Matched to an SA2: {self.schools_matched} | "
            f"SA2s with adjacency computed: {self.adjacency_computed_for}"
        )


def download_au_schools(output_path: Path) -> int:
    """Query Overture S3 for AU school-category places and save locally."""
    import duckdb

    output_path.parent.mkdir(parents=True, exist_ok=True)
    categories_sql = ", ".join(f"'{c}'" for c in _OVERTURE_SCHOOL_CATEGORIES)
    west, south, east, north = _AU_BBOX

    logger.info("Connecting to Overture S3 (release %s) ...", _OVERTURE_RELEASE)

    con = duckdb.connect()
    try:
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute("INSTALL spatial; LOAD spatial;")
        con.execute("SET s3_region='us-west-2';")
        con.execute("SET enable_progress_bar=true;")

        query = f"""
        COPY (
            SELECT
                names.primary                                AS name,
                categories.primary                           AS category,
                ST_X(geometry)                               AS lon,
                ST_Y(geometry)                               AS lat
            FROM read_parquet('{_S3_PATH}', hive_partitioning=1)
            WHERE bbox.xmin >= {west}  AND bbox.xmax <= {east}
              AND bbox.ymin >= {south} AND bbox.ymax <= {north}
              AND categories.primary IN ({categories_sql})
        ) TO '{output_path}' (FORMAT PARQUET, COMPRESSION ZSTD)
        """
        con.execute(query)
        count = con.execute(f"SELECT COUNT(*) FROM read_parquet('{output_path}')").fetchone()[0]
    finally:
        con.close()

    logger.info("Saved %d AU school places to %s", count, output_path)
    return count


def load_school_locations(db: Session, places_path: Path) -> SchoolLoadReport:
    """Match downloaded school places to their containing SA2 and upsert."""
    report = SchoolLoadReport()

    logger.info("Reading school places from %s ...", places_path)
    places_df = pd.read_parquet(places_path)
    places_df["level"] = places_df["category"].map(_OVERTURE_SCHOOL_CATEGORIES)
    places_df = places_df.dropna(subset=["level", "name", "lat", "lon"])
    report.schools_loaded = len(places_df)

    logger.info("Loading SA2 geometries ...")
    sa2_gdf = _load_sa2_geodataframe(db)

    logger.info("Spatial join: assigning schools to SA2s ...")
    schools_gdf = gpd.GeoDataFrame(
        places_df,
        geometry=gpd.points_from_xy(places_df["lon"], places_df["lat"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(schools_gdf, sa2_gdf[["sa2_code", "geometry"]], how="left", predicate="within")
    matched = joined.dropna(subset=["sa2_code"])
    report.schools_matched = len(matched)
    logger.info("Matched %d / %d schools to an SA2", report.schools_matched, report.schools_loaded)

    for row in matched.itertuples():
        school_id = hashlib.sha1(f"{row.name}|{row.lat}|{row.lon}".encode()).hexdigest()[:24]
        db.merge(
            LocalSchool(
                id=school_id,
                name=row.name,
                category=row.category,
                level=row.level,
                lat=row.lat,
                lon=row.lon,
                sa2_code=row.sa2_code,
            )
        )
    db.commit()

    report.adjacency_computed_for = _compute_adjacency(db, sa2_gdf)
    db.commit()

    return report


def _load_sa2_geodataframe(db: Session) -> gpd.GeoDataFrame:
    import json

    from shapely.geometry import shape as shp_shape

    sa2_codes: list[str] = []
    geometries: list = []
    for sa2_code, geojson_str in db.query(SA2Region.sa2_code, SA2Region.geometry_geojson).all():
        if not geojson_str:
            continue
        try:
            geometries.append(shp_shape(json.loads(geojson_str)))
            sa2_codes.append(sa2_code)
        except Exception:
            pass
    return gpd.GeoDataFrame({"sa2_code": sa2_codes}, geometry=geometries, crs="EPSG:4326")


def _compute_adjacency(db: Session, sa2_gdf: gpd.GeoDataFrame) -> int:
    """Populate `adjacent_sa2_codes` (SA2s sharing a border) for every SA2
    that doesn't already have it — a one-time computation, reused by every
    later request instead of recomputing shapely ops per page load."""
    already_done = {
        row[0] for row in db.query(SA2Region.sa2_code).filter(SA2Region.adjacent_sa2_codes.isnot(None)).all()
    }
    todo = sa2_gdf[~sa2_gdf["sa2_code"].isin(already_done)]
    if todo.empty:
        return 0

    logger.info("Computing SA2 adjacency for %d SA2s ...", len(todo))
    # Spatial self-join on a small buffer (bridges simplified-geometry slivers)
    buffered = sa2_gdf.copy()
    buffered["geometry"] = buffered.geometry.buffer(0.001)
    joined = gpd.sjoin(
        todo[["sa2_code", "geometry"]],
        buffered[["sa2_code", "geometry"]],
        how="left",
        predicate="intersects",
        lsuffix="left",
        rsuffix="right",
    )
    joined = joined[joined["sa2_code_left"] != joined["sa2_code_right"]]

    count = 0
    for sa2_code, group in joined.groupby("sa2_code_left"):
        region = db.get(SA2Region, sa2_code)
        if region is None:
            continue
        region.adjacent_sa2_codes = sorted(set(group["sa2_code_right"].dropna().tolist()))
        count += 1
    return count
