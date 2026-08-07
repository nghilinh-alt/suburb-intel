"""Points-of-interest loader — hospitals, shopping centres, stadiums/arenas,
and attractions, from Overture Maps places.

Categories verified by querying Overture's real AU category taxonomy
directly via DuckDB against the S3 source (same approach as
school_locations_loader.py) rather than guessing names.

Separate download/table from overture_amenity_loader.py's counted amenity
categories (cafes, restaurants, etc.) — this is about a handful of *named*
landmark-scale places, not density counts.

Public/private hospital tagging is a best-effort NAME HEURISTIC only
("private" in the name -> private; otherwise assumed public) — Overture
doesn't carry ownership data. Australian private hospitals don't always
say "Private" in their name (e.g. some faith-based/not-for-profit private
hospitals), so this will misclassify some. Treat it as a hint, not a fact.

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.points_of_interest --download
    python -m app.ingestion.points_of_interest
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import PointOfInterest
from app.ingestion.school_locations_loader import _load_sa2_geodataframe

logger = logging.getLogger(__name__)

_OVERTURE_RELEASE = "2026-05-20.0"
_S3_PATH = (
    f"s3://overturemaps-us-west-2/release/{_OVERTURE_RELEASE}"
    "/theme=places/type=place/*"
)
_AU_BBOX = (112.0, -44.5, 155.0, -9.0)

# Overture categories.primary -> friendly group label. Verified against real
# category values present in Overture's AU places (queried live via DuckDB) —
# notably "shopping_mall" has ZERO matches in Australia (Overture tags real
# AU malls as "shopping_center" instead, US spelling — the older
# overture_amenity_loader.py has this same wrong category name, so its
# osm_shopping_centres count column has likely been silently 0 everywhere).
# "department_store" is deliberately excluded — it matches individual anchor
# stores (Myer, Target, David Jones) inside a mall, not the complex itself,
# which just produced 5-8 duplicate near-identical entries per real mall.
#
# NOTE: several of these categories are self-tag noise magnets — Overture lets
# any business pick its own primary category, so "shopping_center" collects
# individual retailers (a keyboard shop, a sunglasses reseller, a solar-parts
# maker) and "venue_and_event_space" collects logistics/marine/office
# businesses. "venue_and_event_space" is dropped entirely below (no reliable
# way to keep only genuine attractions), and Shopping Centre / the generic
# Stadium bucket get name-based precision filters in `_passes_quality_filter`
# — same precision-over-recall trade-off already used for `_is_real_hospital`.
_OVERTURE_POI_CATEGORIES: dict[str, str] = {
    # ── Hospitals (major facilities only — GPs/clinics stay in the amenity
    #    counts section, this is landmark-scale). Overture's "hospital"
    #    category is noisy in practice (~60% of matches were vets, podiatry,
    #    radiology clinics, breast-screening services, not hospitals) — see
    #    `_is_real_hospital` for the name-based quality filter this needs.
    "hospital": "Hospital",
    "childrens_hospital": "Hospital",
    "emergency_room": "Hospital",
    # ── Shopping complexes ────────────────────────────────────────────────
    "shopping_center": "Shopping Centre",
    # ── Stadiums & arenas ─────────────────────────────────────────────────
    "stadium_arena": "Stadium & Arena",
    "football_stadium": "Stadium & Arena",
    "basketball_stadium": "Stadium & Arena",
    "track_stadium": "Stadium & Arena",
    "hockey_arena": "Stadium & Arena",
    "rugby_stadium": "Stadium & Arena",
    "soccer_stadium": "Stadium & Arena",
    "tennis_stadium": "Stadium & Arena",
    "baseball_stadium": "Stadium & Arena",
    # ── Attractions ───────────────────────────────────────────────────────
    "amusement_park": "Attraction",
    "zoo": "Attraction",
    "aquarium": "Attraction",
    "casino": "Attraction",
    "museum": "Attraction",
    "history_museum": "Attraction",
    "art_museum": "Attraction",
    "science_museum": "Attraction",
    "contemporary_art_museum": "Attraction",
    "state_museum": "Attraction",
    "childrens_museum": "Attraction",
    "community_museum": "Attraction",
    "aviation_museum": "Attraction",
    "design_museum": "Attraction",
    "modern_art_museum": "Attraction",
    "military_museum": "Attraction",
}


@dataclass
class PoiLoadReport:
    places_loaded: int = 0
    places_matched: int = 0

    def __str__(self) -> str:
        return f"Places loaded: {self.places_loaded} | Matched to an SA2: {self.places_matched}"


def download_au_pois(output_path: Path) -> int:
    import duckdb

    output_path.parent.mkdir(parents=True, exist_ok=True)
    categories_sql = ", ".join(f"'{c}'" for c in _OVERTURE_POI_CATEGORIES)
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
                ST_Y(geometry)                                AS lat
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

    logger.info("Saved %d AU POI places to %s", count, output_path)
    return count


def _is_public_hospital(name: str, group_label: str) -> int | None:
    if group_label != "Hospital":
        return None
    return 0 if "private" in name.lower() else 1


def _is_real_hospital(name: str, group_label: str) -> bool:
    """Quality filter for the noisy 'hospital' Overture category — require
    the word 'hospital' in the name itself. Verified against real AU data:
    this excludes things like vet clinics, podiatry, radiology, and breast
    screening services that Overture had miscategorized as hospitals. Trades
    recall for precision — a genuine hospital with an unusual name (no
    "Hospital" in it) would be missed, but a mislabeled vet clinic won't be
    shown to users as a real hospital."""
    if group_label != "Hospital":
        return True
    return "hospital" in name.lower()


# Name tokens that mark a genuine shopping complex, as opposed to the many
# individual small retailers Overture self-tags as "shopping_center". Word-
# boundary matched so "mall" doesn't fire on "small" and "shopping" catches
# "Shoppingtown"/"Shopping Village"/"Shopping Plaza" alike.
_SHOPPING_CENTRE_TOKENS: tuple[str, ...] = (
    "shopping",
    "shoppingtown",
    "marketplace",
    "market place",
    "plaza",
    "arcade",
    "mall",
    "westfield",
    "homemaker",
    "megacentre",
    "mega centre",
    "harbour town",
    "outlet",
    "dfo",
)

# Name tokens for a genuine sporting venue. Only applied to Overture's generic
# "stadium_arena" catch-all (a social-play badminton centre self-tags into it);
# the sport-specific categories (football_stadium, rugby_stadium, ...) are
# trustworthy on their own and are NOT name-filtered, so venues with names like
# "The Gabba" survive.
_STADIUM_TOKENS: tuple[str, ...] = (
    "stadium",
    "arena",
    "oval",
    "ground",
    "showground",
    "velodrome",
    "racecourse",
    "raceway",
    "speedway",
    "aquatic",
)


def _name_has_token(name: str, tokens: tuple[str, ...]) -> bool:
    low = name.lower()
    return any(re.search(rf"\b{re.escape(tok)}\b", low) for tok in tokens)


def _passes_quality_filter(name: str, category: str, group_label: str) -> bool:
    """Precision filter for Overture's noisiest self-tag POI categories.

    Overture carries no size/type signal to separate a landmark from a small
    business that picked the same primary category, so we fall back to a name
    heuristic per group — trading recall for precision, the same call already
    made in `_is_real_hospital`.
    """
    if group_label == "Hospital":
        return _is_real_hospital(name, group_label)
    if group_label == "Shopping Centre":
        return _name_has_token(name, _SHOPPING_CENTRE_TOKENS)
    if group_label == "Stadium & Arena" and category == "stadium_arena":
        return _name_has_token(name, _STADIUM_TOKENS)
    return True


def load_points_of_interest(db: Session, places_path: Path) -> PoiLoadReport:
    report = PoiLoadReport()

    logger.info("Reading POI places from %s ...", places_path)
    places_df = pd.read_parquet(places_path)
    places_df["group_label"] = places_df["category"].map(_OVERTURE_POI_CATEGORIES)
    places_df = places_df.dropna(subset=["group_label", "name", "lat", "lon"])
    places_df = places_df[
        places_df.apply(
            lambda r: _passes_quality_filter(r["name"], r["category"], r["group_label"]),
            axis=1,
        )
    ]
    report.places_loaded = len(places_df)

    logger.info("Loading SA2 geometries ...")
    sa2_gdf = _load_sa2_geodataframe(db)

    logger.info("Spatial join: assigning POIs to SA2s ...")
    poi_gdf = gpd.GeoDataFrame(
        places_df,
        geometry=gpd.points_from_xy(places_df["lon"], places_df["lat"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(poi_gdf, sa2_gdf[["sa2_code", "geometry"]], how="left", predicate="within")
    matched = joined.dropna(subset=["sa2_code"])
    report.places_matched = len(matched)
    logger.info("Matched %d / %d POIs to an SA2", report.places_matched, report.places_loaded)

    for row in matched.itertuples():
        poi_id = hashlib.sha1(f"{row.name}|{row.lat}|{row.lon}".encode()).hexdigest()[:24]
        db.merge(
            PointOfInterest(
                id=poi_id,
                name=row.name,
                category=row.category,
                group_label=row.group_label,
                is_public_hospital=_is_public_hospital(row.name, row.group_label),
                lat=row.lat,
                lon=row.lon,
                sa2_code=row.sa2_code,
            )
        )
    db.commit()

    return report
