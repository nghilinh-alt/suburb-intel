"""Overture Maps amenity loader.

Drop-in replacement for the OSM Overpass loader, using the Overture Maps
Foundation's free, open dataset instead.  Overture combines Meta Places,
Microsoft Bing, and TomTom data — far better suburban AU coverage than OSM.

Workflow
────────
1. (One-time) ``download_au_places()`` uses DuckDB to pull all Australian
   POIs matching our 7 categories from Overture's public S3 bucket into a
   local GeoParquet file (~300 MB).  No API key needed.

2. ``load_overture_amenities()`` reads that file, spatial-joins against SA2
   polygons (same geopandas approach as the GTFS loader), counts per
   category, computes amenity_score, and upserts to abs_census_metrics.

   Runs in ~2–3 minutes for all 2 472 SA2s — no rate limits, no timeouts.

Columns written to abs_census_metrics
──────────────────────────────────────
Core counts:
  osm_cafes, osm_bakeries, osm_restaurants, osm_fast_food,
  osm_supermarkets, osm_parks, osm_gyms, osm_hospitals,
  osm_medical_centers, osm_pharmacies, osm_shopping_centres,
  osm_mechanics, osm_hardware_stores, osm_petrol_stations, osm_banks,
  osm_post_offices, osm_laundries, osm_car_washes, osm_vets, osm_pet_stores

Cuisine breakdown (subsets of osm_restaurants):
  osm_rest_chinese, osm_rest_indian, osm_rest_thai, osm_rest_italian,
  osm_rest_japanese, osm_rest_vietnamese, osm_rest_korean, osm_rest_greek,
  osm_rest_mexican, osm_rest_middle_eastern, osm_rest_seafood

Derived:
  amenity_score  (0–10 weighted liveability score)

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1

    # Step 1 — download AU places once (run when you want fresh data):
    python -m app.ingestion.overture_amenities --download

    # Step 2 — load all states into DB:
    python -m app.ingestion.overture_amenities

    # One state only:
    python -m app.ingestion.overture_amenities --state VIC
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import shape
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics, SA2Region

logger = logging.getLogger(__name__)

# Latest Overture release (update this string when re-downloading fresh data)
_OVERTURE_RELEASE = "2026-05-20.0"
_S3_PATH = (
    f"s3://overturemaps-us-west-2/release/{_OVERTURE_RELEASE}"
    "/theme=places/type=place/*"
)

# Generous bounding box covering all of Australia + territories
_AU_BBOX = (112.0, -44.5, 155.0, -9.0)   # west, south, east, north

# ---------------------------------------------------------------------------
# Category mapping
# ---------------------------------------------------------------------------

# Overture categories.primary → internal amenity category name.
# Cuisine categories map to both their cuisine column AND count toward
# the osm_restaurants total (see aggregation logic below).
_OVERTURE_TO_CAT: dict[str, str] = {
    # ── Cafes (coffee shops only — NOT bakeries) ─────────────────────────
    "coffee_shop":                     "cafe",
    "cafe":                            "cafe",
    "tea_house":                       "cafe",
    # ── Bakeries (separate from cafes) ──────────────────────────────────
    "bakery":                          "bakery",
    # ── Generic / unclassified restaurants ──────────────────────────────
    "restaurant":                      "restaurant",
    "casual_eatery":                   "restaurant",
    "food_court":                      "restaurant",
    "steakhouse":                      "restaurant",
    "noodle_house":                    "restaurant",
    "bbq_joint":                       "restaurant",
    "sandwich_spot":                   "restaurant",
    "wings_joint":                     "restaurant",
    "tapas_restaurant":                "restaurant",
    "vegetarian_and_vegan_restaurant": "restaurant",
    # ── Fast food (separate from sit-down) ───────────────────────────────
    "fast_food_restaurant":            "fast_food",
    "burger_joint":                    "fast_food",
    "pizza_place":                     "fast_food",
    # ── Cuisine-specific restaurants ─────────────────────────────────────
    "chinese_restaurant":              "rest_chinese",
    "indian_restaurant":               "rest_indian",
    "thai_restaurant":                 "rest_thai",
    "italian_restaurant":              "rest_italian",
    "japanese_restaurant":             "rest_japanese",
    "sushi_restaurant":                "rest_japanese",
    "vietnamese_restaurant":           "rest_vietnamese",
    "korean_restaurant":               "rest_korean",
    "greek_restaurant":                "rest_greek",
    "mexican_restaurant":              "rest_mexican",
    "middle_eastern_restaurant":       "rest_middle_eastern",
    "seafood_restaurant":              "rest_seafood",
    # ── Supermarkets / grocers ───────────────────────────────────────────
    "supermarket":                     "supermarket",
    "grocery_store":                   "supermarket",
    "convenience_store":               "supermarket",
    # ── Parks / outdoors ─────────────────────────────────────────────────
    "park":                            "park",
    "national_park":                   "park",
    "nature_preserve":                 "park",
    "recreation_area":                 "park",
    "botanical_garden":                "park",
    "playground":                      "park",
    "beach":                           "park",
    "nature_reserve":                  "park",
    "dog_park":                        "park",
    "skate_park":                      "park",
    # ── Gyms / fitness ───────────────────────────────────────────────────
    "gym":                             "gym",
    "fitness_center":                  "gym",
    "health_club":                     "gym",
    "yoga_studio":                     "gym",
    "pilates_studio":                  "gym",
    "sports_complex":                  "gym",
    "recreation_center":               "gym",
    "martial_arts_school":             "gym",
    "boxing_gym":                      "gym",
    "crossfit_gym":                    "gym",
    # ── Hospitals (actual inpatient facilities) ──────────────────────────
    "hospital":                        "hospital",
    "urgent_care_center":              "hospital",
    "emergency_room":                  "hospital",
    # ── GP clinics / medical centres (primary care) ──────────────────────
    "medical_center":                  "medical_center",
    "clinic":                          "medical_center",
    "doctors_office":                  "medical_center",
    "medical_clinic":                  "medical_center",
    "health_clinic":                   "medical_center",
    "general_practitioner":            "medical_center",
    "medical_office":                  "medical_center",
    # ── Pharmacies ───────────────────────────────────────────────────────
    "pharmacy":                        "pharmacy",
    "drugstore":                       "pharmacy",
    # ── Shopping centres ─────────────────────────────────────────────────
    "shopping_mall":                   "shopping_centre",
    "department_store":                "shopping_centre",
    # ── Service businesses ───────────────────────────────────────────────
    "auto_repair":                     "mechanic",
    "car_repair":                      "mechanic",
    "auto_service":                    "mechanic",
    "hardware_store":                  "hardware_store",
    "home_improvement_store":          "hardware_store",
    "gas_station":                     "petrol_station",
    "petrol_station":                  "petrol_station",
    "fuel_station":                    "petrol_station",
    "bank":                            "bank",
    "post_office":                     "post_office",
    "laundry":                         "laundry",
    "dry_cleaner":                     "laundry",
    "car_wash":                        "car_wash",
    "veterinarian":                    "vet",
    "pet_store":                       "pet_store",
}

# Internal category → DB column on abs_census_metrics
_CAT_COLUMN: dict[str, str] = {
    "cafe":              "osm_cafes",
    "bakery":            "osm_bakeries",
    "restaurant":        "osm_restaurants",   # generic; total computed separately
    "fast_food":         "osm_fast_food",
    "supermarket":       "osm_supermarkets",
    "park":              "osm_parks",
    "gym":               "osm_gyms",
    "hospital":          "osm_hospitals",
    "medical_center":    "osm_medical_centers",
    "pharmacy":          "osm_pharmacies",
    "shopping_centre":   "osm_shopping_centres",
    # Service businesses
    "mechanic":          "osm_mechanics",
    "hardware_store":    "osm_hardware_stores",
    "petrol_station":    "osm_petrol_stations",
    "bank":              "osm_banks",
    "post_office":       "osm_post_offices",
    "laundry":           "osm_laundries",
    "car_wash":          "osm_car_washes",
    "vet":               "osm_vets",
    "pet_store":         "osm_pet_stores",
    # Cuisine breakdown
    "rest_chinese":         "osm_rest_chinese",
    "rest_indian":          "osm_rest_indian",
    "rest_thai":            "osm_rest_thai",
    "rest_italian":         "osm_rest_italian",
    "rest_japanese":        "osm_rest_japanese",
    "rest_vietnamese":      "osm_rest_vietnamese",
    "rest_korean":          "osm_rest_korean",
    "rest_greek":           "osm_rest_greek",
    "rest_mexican":         "osm_rest_mexican",
    "rest_middle_eastern":  "osm_rest_middle_eastern",
    "rest_seafood":         "osm_rest_seafood",
}

# Categories that roll up into osm_restaurants (generic + all cuisines)
_RESTAURANT_CATS: frozenset[str] = frozenset({
    "restaurant",
    "rest_chinese", "rest_indian", "rest_thai", "rest_italian",
    "rest_japanese", "rest_vietnamese", "rest_korean", "rest_greek",
    "rest_mexican", "rest_middle_eastern", "rest_seafood",
})

# Amenity score weights and caps
# osm_restaurants = total sit-down dining, used for the core score
_SCORE_PARAMS: dict[str, tuple[float, int]] = {
    "cafe":             (8.0,  30),
    "restaurant":       (7.0,  50),   # total sit-down; higher cap for dense CBDs
    "supermarket":      (9.0,   8),
    "park":             (8.5,   5),
    "gym":              (7.0,   5),
    "hospital":         (9.5,   3),
    "medical_center":   (9.0,   5),
    "pharmacy":         (8.0,   5),
    "shopping_centre":  (6.5,   3),
}
_MAX_SCORE = sum(w for w, _ in _SCORE_PARAMS.values())   # 63.5


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class OvertureLoadReport:
    places_loaded:   int = 0
    places_matched:  int = 0
    sa2s_updated:    int = 0
    sa2s_no_row:     int = 0

    def __str__(self) -> str:
        return (
            f"Places loaded: {self.places_loaded} | "
            f"Matched to SA2: {self.places_matched} | "
            f"SA2 rows updated: {self.sa2s_updated} | "
            f"No metrics row: {self.sa2s_no_row}"
        )


# ---------------------------------------------------------------------------
# Step 1 — download
# ---------------------------------------------------------------------------

def download_au_places(output_path: Path) -> int:
    """Query Overture S3 and save all AU places for our categories locally.

    Uses DuckDB with the httpfs + spatial extensions.  Filters by:
      - Australia bounding box
      - categories.primary in our tracked set

    Returns the number of places saved.
    """
    import duckdb

    output_path.parent.mkdir(parents=True, exist_ok=True)

    categories_sql = ", ".join(f"'{c}'" for c in _OVERTURE_TO_CAT)
    west, south, east, north = _AU_BBOX

    logger.info("Connecting to Overture S3 (release %s) ...", _OVERTURE_RELEASE)
    logger.info("This downloads ~300 MB and may take 3–10 minutes ...")

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

    logger.info("Saved %d AU places to %s", count, output_path)
    return count


# ---------------------------------------------------------------------------
# Step 2 — load into DB
# ---------------------------------------------------------------------------

def load_overture_amenities(
    db: Session,
    places_path: Path,
    *,
    year: int = 2021,
    state_filter: str | None = None,
) -> OvertureLoadReport:
    """Count Overture places per SA2 and upsert onto abs_census_metrics.

    Args:
        db:           Synchronous SQLAlchemy session.
        places_path:  Path to the local parquet produced by download_au_places().
        year:         Census year whose metrics rows are updated.
        state_filter: If set (e.g. "VIC"), only process that state's SA2s.
    """
    report = OvertureLoadReport()

    # --- Load and filter places -----------------------------------------
    logger.info("Reading places from %s ...", places_path)
    places_df = pd.read_parquet(places_path)
    places_df["amenity_cat"] = places_df["category"].map(_OVERTURE_TO_CAT)
    places_df = places_df.dropna(subset=["amenity_cat", "lat", "lon"])
    report.places_loaded = len(places_df)
    logger.info("Loaded %d places across %d categories", report.places_loaded,
                places_df["amenity_cat"].nunique())

    # --- Load SA2 geometries ---------------------------------------------
    logger.info("Loading SA2 geometries ...")
    sa2_gdf = _load_sa2_geometries(db, state_filter)
    logger.info("Loaded %d SA2 polygons", len(sa2_gdf))

    # --- Spatial join ----------------------------------------------------
    logger.info("Spatial join: assigning places to SA2s ...")
    places_gdf = gpd.GeoDataFrame(
        places_df,
        geometry=gpd.points_from_xy(places_df["lon"], places_df["lat"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(
        places_gdf,
        sa2_gdf[["sa2_code", "geometry"]],
        how="left",
        predicate="within",
    )
    report.places_matched = int(joined["sa2_code"].notna().sum())
    logger.info("Matched %d / %d places to an SA2",
                report.places_matched, report.places_loaded)

    # --- Aggregate counts ------------------------------------------------
    matched = joined.dropna(subset=["sa2_code"]).copy()
    # cat_counts[sa2_code][internal_cat] = count
    cat_counts: dict[str, dict[str, int]] = {}
    for (sa2, cat), n in matched.groupby(["sa2_code", "amenity_cat"]).size().items():
        if cat in _CAT_COLUMN:
            cat_counts.setdefault(str(sa2), {})[cat] = int(n)

    # --- Upsert ----------------------------------------------------------
    logger.info("Upserting counts for %d SA2s ...", len(cat_counts))
    all_sa2s = {row[0] for row in db.query(SA2Region.sa2_code).all()} \
        if not state_filter else \
        {row[0] for row in db.query(SA2Region.sa2_code)
                               .filter(SA2Region.state == state_filter).all()}

    for sa2_code in all_sa2s:
        metrics = db.get(ABSCEntensMetrics, (sa2_code, year))
        if metrics is None:
            report.sa2s_no_row += 1
            continue

        cats = cat_counts.get(sa2_code, {})

        # Write every individual category column (zero if absent)
        for cat, col in _CAT_COLUMN.items():
            setattr(metrics, col, cats.get(cat, 0))

        # osm_restaurants = generic + all cuisine sub-categories combined
        metrics.osm_restaurants = sum(
            cats.get(c, 0) for c in _RESTAURANT_CATS
        )

        # Amenity score — uses osm_restaurants total, not individual cuisines
        score = 0.0
        for score_cat, (weight, cap) in _SCORE_PARAMS.items():
            if score_cat == "restaurant":
                count = metrics.osm_restaurants
            else:
                col = _CAT_COLUMN.get(score_cat)
                count = cats.get(score_cat, 0) if col else 0
            score += weight * min(count / cap, 1.0)
        metrics.amenity_score = round((score / _MAX_SCORE) * 10, 3)
        report.sa2s_updated += 1

    db.commit()
    return report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_sa2_geometries(
    db: Session,
    state_filter: str | None,
) -> gpd.GeoDataFrame:
    q = db.query(
        SA2Region.sa2_code,
        SA2Region.geometry_geojson,
    ).filter(SA2Region.geometry_geojson.isnot(None))
    if state_filter:
        q = q.filter(SA2Region.state == state_filter)

    records = []
    for sa2_code, geojson_str in q.all():
        try:
            geom = shape(json.loads(geojson_str))
            records.append({"sa2_code": sa2_code, "geometry": geom})
        except Exception as exc:
            logger.warning("Bad geometry SA2 %s: %s", sa2_code, exc)

    return gpd.GeoDataFrame(records, crs="EPSG:4326")
