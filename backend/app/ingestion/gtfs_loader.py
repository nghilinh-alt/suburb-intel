"""GTFS public-transport stop density loader.

Counts unique stops (train / tram / bus / ferry) inside each SA2 boundary
using a spatial point-in-polygon join between GTFS stop co-ordinates and the
geometry_geojson already stored in sa2_regions.

Supported feed formats
──────────────────────
• PTV (Victoria) — outer zip contains numbered sub-folders, each holding a
                   ``google_transit.zip`` for one mode.
                   Folder → GTFS route_type mapping:
                     1 Metro Train   → 2 (rail)
                     2 Tram          → 0 (tram)
                     3 Regional Rail → 2 (rail)
                     4 Regional Bus  → 3 (bus)
                     5 Metro Bus     → 3 (bus)
                     6 Regional Coach→ 3 (bus)
                     7 School Bus    → 3 (bus)
                    11 Telebus       → 3 (bus)

• Standard GTFS — a single zip with stops.txt / routes.txt / trips.txt /
                  stop_times.txt.  stop_times is joined to resolve the
                  route_type served at each stop.

Columns written to abs_census_metrics:
    pt_stop_train, pt_stop_tram, pt_stop_bus, pt_stop_ferry

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.gtfs --zip "../data/gtfs/gtfs.zip" --state VIC
"""

from __future__ import annotations

import io
import json
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point, shape
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics, SA2Region

logger = logging.getLogger(__name__)

# PTV folder-number → GTFS route_type
# PTV folder → normalised GTFS route_type.
# Verified from routes.txt in each inner zip (route_short_name and route_type fields).
#   Folder 1: Regional Train  (route_type 2  — Seymour, Ballarat, etc.)
#   Folder 2: Metro Train     (route_type 400 — Alamein, Belgrave, Frankston, etc.)
#   Folder 3: Tram            (route_type 0   — route numbers 1, 109, 11, etc.)
#   Folder 4: Regional Bus    (route_types 3, 701)
#   Folder 5: Regional Coach  (route_type 204)
#   Folder 6: Metro Bus       (route_type 701)
#  Folder 10: The Overland    (route_type 102 — long-distance rail service)
#  Folder 11: Telebus/demand  (route_type 3)
_PTV_FOLDER_ROUTE_TYPE: dict[str, int] = {
    "1":  2,   # Regional Train  → rail
    "2":  2,   # Metro Train     → rail  (GTFS extended type 400)
    "3":  0,   # Tram            → tram/light-rail
    "4":  3,   # Regional Bus    → bus
    "5":  3,   # Regional Coach  → bus
    "6":  3,   # Metro Bus       → bus
    "10": 2,   # The Overland    → rail
    "11": 3,   # Telebus / on-demand → bus
}

# route_type → column name on ABSCEntensMetrics
# Standard GTFS types (0–4) plus extended GTFS types used by Australian agencies:
#   TfNSW uses 700–799 (bus), 712 (suburban bus), 106/100–199 (rail),
#              204/205/200–299 (coach → bus), 400–499 (urban rail), 900–999 (light rail)
#   TransLink QLD uses similar extensions.
_ROUTE_TYPE_COLUMN: dict[int, str] = {
    # Standard types
    0: "pt_stop_tram",
    1: "pt_stop_train",
    2: "pt_stop_train",
    3: "pt_stop_bus",
    4: "pt_stop_ferry",
}

def _normalise_route_type(rt: int) -> int:
    """Map GTFS extended route type to one of the 5 standard types (0–4).

    Extended types are defined in the GTFS spec and used by TfNSW, TransLink, etc.
    Reference: https://developers.google.com/transit/gtfs/reference/extended-route-types
    """
    if rt in _ROUTE_TYPE_COLUMN:
        return rt                   # already standard
    if 100 <= rt <= 199:            # Railway Service (incl. long-distance, regional)
        return 2
    if 200 <= rt <= 299:            # Coach Service — treated as bus
        return 3
    if 400 <= rt <= 499:            # Urban Railway (metro, subway)
        return 2
    if 700 <= rt <= 799:            # Bus Service (suburban, express, etc.)
        return 3
    if 800 <= rt <= 899:            # Trolley bus — treated as bus
        return 3
    if 900 <= rt <= 999:            # Light Rail / Tram
        return 0
    if 1000 <= rt <= 1099:          # Water transport / ferry
        return 4
    if 1100 <= rt <= 1199:          # Air service — ignore (no column)
        return -1
    return -1                       # unknown → dropped

_ROUTE_TYPE_LABEL: dict[int, str] = {
    0: "tram", 1: "metro/rail", 2: "rail", 3: "bus", 4: "ferry",
}


@dataclass
class GTFSLoadReport:
    stops_loaded: int = 0
    stops_matched: int = 0
    sa2s_updated: int = 0
    sa2s_skipped_no_row: int = 0

    def __str__(self) -> str:
        return (
            f"Stops loaded: {self.stops_loaded} | "
            f"Matched to SA2: {self.stops_matched} | "
            f"SA2 rows updated: {self.sa2s_updated} | "
            f"Skipped (no metrics row): {self.sa2s_skipped_no_row}"
        )


def load_gtfs(
    gtfs_zip: Path,
    db: Session,
    *,
    year: int = 2021,
    state_filter: str | None = None,
    reset_existing: bool = True,
) -> GTFSLoadReport:
    """Count PT stops per SA2 and upsert onto abs_census_metrics.

    Args:
        gtfs_zip:       Path to the GTFS zip (PTV multi-feed or standard single-feed).
        db:             Synchronous SQLAlchemy session.
        year:           Census year whose metrics rows are updated (default 2021).
        state_filter:   If set (e.g. "VIC"), only load geometries for that state's SA2s,
                        which also limits which rows get updated.  Recommended when running
                        state-specific feeds so VIC data doesn't overwrite NSW data.
        reset_existing: If True (default), NULL out all PT columns for the target state
                        before loading.  Set to False when appending a supplementary
                        regional feed on top of an already-loaded primary feed.
    """
    report = GTFSLoadReport()

    # Reset PT stop columns for all SA2s that will be (re)populated so that
    # a re-run doesn't leave stale counts from a previous incorrect run.
    if reset_existing:
        _reset_pt_columns(db, state_filter=state_filter, year=year)

    logger.info("Extracting stops from %s ...", gtfs_zip.name)
    stops_df = _extract_stops_with_modes(gtfs_zip)
    report.stops_loaded = len(stops_df)
    logger.info("Extracted %d stops total", report.stops_loaded)

    logger.info("Loading SA2 geometries from DB ...")
    sa2_gdf = _load_sa2_geometries(db, state_filter=state_filter)
    logger.info("Loaded %d SA2 polygons", len(sa2_gdf))

    logger.info("Spatial join: assigning stops to SA2s ...")
    joined = _spatial_join(stops_df, sa2_gdf)
    report.stops_matched = int(joined["sa2_code"].notna().sum())
    logger.info(
        "Matched %d / %d stops to an SA2",
        report.stops_matched,
        report.stops_loaded,
    )

    counts = _aggregate_counts(joined)
    report.sa2s_updated, report.sa2s_skipped_no_row = _upsert_counts(counts, db, year)
    db.commit()
    return report


# ---------------------------------------------------------------------------
# Stop extraction
# ---------------------------------------------------------------------------

def _extract_stops_with_modes(gtfs_zip: Path) -> pd.DataFrame:
    """Return DataFrame with columns: stop_id, stop_lat, stop_lon, route_type."""
    with zipfile.ZipFile(gtfs_zip) as outer:
        inner_zips = [n for n in outer.namelist() if n.endswith(".zip")]
        if inner_zips:
            logger.info("Detected PTV multi-feed structure (%d inner zips)", len(inner_zips))
            return _stops_from_ptv(outer)
        else:
            logger.info("Detected standard single-feed GTFS structure")
            return _stops_from_standard(outer)


def _stops_from_ptv(outer: zipfile.ZipFile) -> pd.DataFrame:
    """PTV multi-feed: numbered sub-folder → mode mapping.

    Filters each feed to stops that are served by *regular* scheduled services:
    - Stops without a scheduled time (pathway / access nodes like entrances,
      bike racks, lifts) are excluded.
    - Temporary Rail Replacement Bus routes in the Metro Train feed (folder 2)
      are excluded so that transient bus stops aren't counted as train stops.
    """
    frames: list[pd.DataFrame] = []
    for name in sorted(outer.namelist()):
        if not name.endswith(".zip"):
            continue
        folder = name.split("/")[0]
        route_type = _PTV_FOLDER_ROUTE_TYPE.get(folder)
        if route_type is None:
            logger.debug("Unknown PTV folder %s — skipping", folder)
            continue

        with outer.open(name) as fh:
            inner_bytes = fh.read()

        with zipfile.ZipFile(io.BytesIO(inner_bytes)) as inner:
            # Folder 2 (Metro Train) embeds Rail Replacement Bus routes that
            # reference stops at/near stations.  Exclude them so that only
            # permanent train platform stops are counted.
            exclude_replacement = (folder == "2")
            served_ids = _served_stop_ids(inner, exclude_replacement=exclude_replacement)
            stops = _read_stops_txt(inner)
            stops["stop_id"] = stops["stop_id"].astype(str)
            stops = stops[stops["stop_id"].isin(served_ids)]

        stops = stops.copy()
        stops["route_type"] = route_type
        label = _ROUTE_TYPE_LABEL.get(route_type, str(route_type))
        logger.info("  PTV folder %s (%s): %d served stops", folder, label, len(stops))
        frames.append(stops)

    if not frames:
        raise ValueError("No recognised PTV inner zips found in the outer zip")
    return pd.concat(frames, ignore_index=True)


def _served_stop_ids(
    zf: zipfile.ZipFile,
    *,
    exclude_replacement: bool = False,
) -> set[str]:
    """Return stop_ids that appear in stop_times for scheduled services.

    If exclude_replacement=True, routes whose short name contains "Replacement"
    (i.e. PTV Rail Replacement Bus routes) are filtered out first.
    """
    if not exclude_replacement:
        st = _read_csv(zf, "stop_times.txt", usecols=["stop_id"])
        return set(st["stop_id"].astype(str).unique())

    # Filter to non-replacement routes → trips → stop_ids
    routes = _read_csv(zf, "routes.txt", usecols=["route_id", "route_short_name"])
    real_route_ids = set(
        routes.loc[
            ~routes["route_short_name"].str.contains("Replacement", case=False, na=False),
            "route_id",
        ]
    )
    trips = _read_csv(zf, "trips.txt", usecols=["route_id", "trip_id"])
    real_trip_ids = set(trips.loc[trips["route_id"].isin(real_route_ids), "trip_id"])
    st = _read_csv(zf, "stop_times.txt", usecols=["trip_id", "stop_id"])
    real_st = st[st["trip_id"].isin(real_trip_ids)]
    return set(real_st["stop_id"].astype(str).unique())


def _stops_from_standard(outer: zipfile.ZipFile) -> pd.DataFrame:
    """Standard single-feed GTFS: join stops → stop_times → trips → routes."""
    routes = _read_csv(outer, "routes.txt", usecols=["route_id", "route_type"])
    routes["route_type"] = pd.to_numeric(routes["route_type"], errors="coerce").astype("Int64")

    trips = _read_csv(outer, "trips.txt", usecols=["route_id", "trip_id"])
    trip_rt = trips.merge(routes, on="route_id", how="left")[["trip_id", "route_type"]]
    trip_rt_map: dict = dict(zip(trip_rt["trip_id"], trip_rt["route_type"]))

    logger.info("  Reading stop_times.txt (may be large) ...")
    st = _read_csv(outer, "stop_times.txt", usecols=["trip_id", "stop_id"])
    st["route_type"] = st["trip_id"].map(trip_rt_map)
    st = st.dropna(subset=["route_type"])
    stop_modes = st[["stop_id", "route_type"]].drop_duplicates()

    stops = _read_stops_txt(outer)
    stops["stop_id"] = stops["stop_id"].astype(str)
    stop_modes["stop_id"] = stop_modes["stop_id"].astype(str)

    # Left join — stops with no route_type get -1 (unknown), counted separately
    merged = stops.merge(stop_modes, on="stop_id", how="left")
    merged["route_type"] = pd.to_numeric(merged["route_type"], errors="coerce").fillna(-1).astype(int)
    # Normalise extended GTFS route types (e.g. TfNSW uses 700, 712, 106, etc.)
    merged["route_type"] = merged["route_type"].apply(_normalise_route_type)
    return merged


def _read_stops_txt(zf: zipfile.ZipFile) -> pd.DataFrame:
    df = _read_csv(zf, "stops.txt", usecols=["stop_id", "stop_lat", "stop_lon"])
    df["stop_lat"] = pd.to_numeric(df["stop_lat"], errors="coerce")
    df["stop_lon"] = pd.to_numeric(df["stop_lon"], errors="coerce")
    return df.dropna(subset=["stop_lat", "stop_lon"]).copy()


def _read_csv(
    zf: zipfile.ZipFile,
    name: str,
    usecols: list[str] | None = None,
) -> pd.DataFrame:
    with zf.open(name) as fh:
        return pd.read_csv(fh, usecols=usecols, dtype=str, low_memory=False,
                           skipinitialspace=True)


# ---------------------------------------------------------------------------
# SA2 geometry loading
# ---------------------------------------------------------------------------

def _load_sa2_geometries(
    db: Session,
    state_filter: str | None,
) -> gpd.GeoDataFrame:
    q = db.query(
        SA2Region.sa2_code,
        SA2Region.state,
        SA2Region.geometry_geojson,
    ).filter(SA2Region.geometry_geojson.isnot(None))

    if state_filter:
        q = q.filter(SA2Region.state == state_filter)

    records = []
    for sa2_code, state, geojson_str in q.all():
        try:
            geom = shape(json.loads(geojson_str))
            records.append({"sa2_code": sa2_code, "state": state, "geometry": geom})
        except Exception as exc:
            logger.warning("Bad geometry SA2 %s: %s", sa2_code, exc)

    return gpd.GeoDataFrame(records, crs="EPSG:4326")


# ---------------------------------------------------------------------------
# Spatial join
# ---------------------------------------------------------------------------

def _spatial_join(stops_df: pd.DataFrame, sa2_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    stops_gdf = gpd.GeoDataFrame(
        stops_df,
        geometry=gpd.points_from_xy(stops_df["stop_lon"], stops_df["stop_lat"]),
        crs="EPSG:4326",
    )
    joined = gpd.sjoin(
        stops_gdf,
        sa2_gdf[["sa2_code", "geometry"]],
        how="left",
        predicate="within",
    )
    return joined


# ---------------------------------------------------------------------------
# Aggregation and DB upsert
# ---------------------------------------------------------------------------

def _aggregate_counts(joined: gpd.GeoDataFrame) -> dict[str, dict[str, int]]:
    """Build {sa2_code: {column: count}} from the spatial join result."""
    matched = joined.dropna(subset=["sa2_code"]).copy()
    matched["col"] = matched["route_type"].apply(
        lambda rt: _ROUTE_TYPE_COLUMN.get(int(rt), None)
    )
    matched = matched.dropna(subset=["col"])

    counts: dict[str, dict[str, int]] = {}
    for (sa2, col), n in matched.groupby(["sa2_code", "col"]).size().items():
        counts.setdefault(sa2, {})[col] = int(n)
    return counts


def _reset_pt_columns(
    db: Session,
    state_filter: str | None,
    year: int,
) -> None:
    """Set all four PT stop columns to NULL for SA2s about to be (re)loaded."""
    q = db.query(ABSCEntensMetrics).filter(ABSCEntensMetrics.year == year)
    if state_filter:
        # Join to sa2_regions to filter by state
        q = q.join(SA2Region, ABSCEntensMetrics.sa2_code == SA2Region.sa2_code).filter(
            SA2Region.state == state_filter
        )
    for m in q.all():
        m.pt_stop_train = None
        m.pt_stop_tram  = None
        m.pt_stop_bus   = None
        m.pt_stop_ferry = None


def _upsert_counts(
    counts: dict[str, dict[str, int]],
    db: Session,
    year: int,
) -> tuple[int, int]:
    updated = 0
    skipped = 0
    for sa2_code, cols in counts.items():
        metrics = db.get(ABSCEntensMetrics, (sa2_code, year))
        if metrics is None:
            skipped += 1
            continue
        for col, count in cols.items():
            setattr(metrics, col, count)
        updated += 1
    return updated, skipped
