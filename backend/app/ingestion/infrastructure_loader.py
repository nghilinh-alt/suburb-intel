"""Infrastructure Australia Priority List loader.

Parses the IA 2026 Priority List PDF, geocodes each project via Nominatim,
upserts into infrastructure_projects, then links projects to nearby SA2s.

Data source
───────────
Infrastructure Australia 2026 Infrastructure Priority List
PDF: data/infrastructure/2026-ipl.pdf
Consolidated list is on pages 109–121 of the 139-page document.

Columns written to infrastructure_projects
──────────────────────────────────────────
project_id  — URL-safe slug from project name
name        — project name as printed in the PDF
type        — inferred from name keywords (rail/road/port_freight/…)
value_aud   — NULL (PDF does not include cost estimates)
status      — normalised timing code (pipeline_2_4yr / pipeline_5_10yr / …)
lat / lon   — Nominatim geocode result (WGS84)
state       — state code(s) from PDF, e.g. "NSW" or "VIC, NSW"
timing      — raw timing string from PDF
source      — "Infrastructure Australia Priority List 2026"

Rows written to sa2_project_link
─────────────────────────────────
(sa2_code, project_id, impact_score)
impact_score = 1.0 − (distance_km / 25.0), for SA2 centroids within 25 km.

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.infrastructure
    python -m app.ingestion.infrastructure --pdf ../data/infrastructure/2026-ipl.pdf
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path

import urllib3
import requests
from sqlalchemy.orm import Session

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from app.db.models import InfrastructureProject, SA2ProjectLink, SA2Region

logger = logging.getLogger(__name__)

_SOURCE        = "Infrastructure Australia Priority List 2026"
_GEOCODE_DELAY = 1.1   # seconds — Nominatim ToS: max 1 req/s

# Regex: one line → name | state codes | timing
_LINE_PAT = re.compile(
    r"^(.+?)\s+([A-Z]{2,3}(?:,\s*[A-Z]{2,3})*)\s+"
    r"(2-4 year pipeline|5-10 year pipeline|Investment-ready for (?:Delivery|Planning))$"
)

_TIMING_STATUS: dict[str, str] = {
    "2-4 year pipeline":              "pipeline_2_4yr",
    "5-10 year pipeline":             "pipeline_5_10yr",
    "Investment-ready for Delivery":  "investment_ready_delivery",
    "Investment-ready for Planning":  "investment_ready_planning",
}

_TYPE_KEYWORDS: dict[str, list[str]] = {
    "rail":         ["rail", "train", "metro", "signalling", "tram", "light rail", "etcs"],
    "road":         ["highway", "road", "freeway", "motorway", "bridge", "corridor"],
    "port_freight": ["port", "intermodal", "freight", "wharf", "maritime", "precinct"],
    "airport":      ["airport"],
    "water":        ["water", "wastewater", "sewerage", "irrigation", "dam", "desalination", "aquifer"],
    "energy":       ["energy", "electricity", "power", "grid", "renewable", "solar", "wind",
                     "battery", "interconnect", "rez", "zero emission", "zero-emission"],
    "bus":          ["bus"],
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class InfrastructureReport:
    projects_parsed:   int = 0
    projects_upserted: int = 0
    geocoded:          int = 0
    geocode_failed:    int = 0
    sa2_links:         int = 0

    def __str__(self) -> str:
        return (
            f"Projects: {self.projects_parsed} parsed, {self.projects_upserted} upserted | "
            f"Geocoded: {self.geocoded} ok / {self.geocode_failed} failed | "
            f"SA2 links: {self.sa2_links}"
        )


def load_infrastructure_projects(
    pdf_path: Path,
    db: Session,
) -> InfrastructureReport:
    """Parse PDF, geocode projects, upsert into DB, link to SA2s.

    Projects already in the DB with a valid lat/lon are NOT re-geocoded
    (saves Nominatim rate-limit budget on re-runs).
    """
    report = InfrastructureReport()

    # 1. Parse PDF
    raw_projects = _parse_pdf(pdf_path)
    report.projects_parsed = len(raw_projects)
    logger.info("Parsed %d projects from PDF", report.projects_parsed)

    # 2. SA2 geometries (loaded once for containment + adjacency linking)
    logger.info("Loading SA2 geometries ...")
    sa2_gdf = _load_sa2_geodataframe(db)
    logger.info("Loaded %d SA2 polygons", len(sa2_gdf))

    # 3. Geocode + upsert
    http = requests.Session()
    http.verify = False
    http.headers["User-Agent"] = "SuburbIntel/1.0 (research project)"

    for proj in raw_projects:
        project_id = proj["project_id"]
        existing   = db.get(InfrastructureProject, project_id)

        # Skip geocoding if already stored
        if existing and existing.lat is not None:
            lat, lon = existing.lat, existing.lon
        else:
            lat, lon = _geocode(proj["name"], proj["state"].split(",")[0].strip(), http)
            if lat is not None:
                report.geocoded += 1
            else:
                report.geocode_failed += 1
            time.sleep(_GEOCODE_DELAY)

        # Upsert project row
        if existing:
            existing.name   = proj["name"]
            existing.type   = proj["type"]
            existing.status = proj["status"]
            existing.state  = proj["state"]
            existing.timing = proj["timing"]
            existing.source = _SOURCE
            if lat is not None:
                existing.lat = lat
                existing.lon = lon
        else:
            db.add(InfrastructureProject(
                project_id = project_id,
                name       = proj["name"],
                type       = proj["type"],
                value_aud  = None,
                status     = proj["status"],
                lat        = lat,
                lon        = lon,
                state      = proj["state"],
                timing     = proj["timing"],
                source     = _SOURCE,
            ))
        report.projects_upserted += 1

        # Refresh SA2 links — containing SA2 + adjacent SA2s only
        if lat is not None:
            db.query(SA2ProjectLink).filter(
                SA2ProjectLink.project_id == project_id
            ).delete(synchronize_session=False)
            for sa2_code, impact_score in _find_sa2s_for_project(lat, lon, sa2_gdf):
                db.add(SA2ProjectLink(
                    sa2_code     = sa2_code,
                    project_id   = project_id,
                    impact_score = impact_score,
                ))
                report.sa2_links += 1

    db.commit()
    return report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_pdf(pdf_path: Path) -> list[dict]:
    """Extract project rows from pages 109-121 of the IA 2026 PDF."""
    try:
        import pdfplumber
    except ImportError:
        raise ImportError("pdfplumber required: pip install pdfplumber")

    projects: list[dict] = []
    seen: set[str] = set()

    with pdfplumber.open(pdf_path) as pdf:
        for i in range(108, min(121, len(pdf.pages))):
            text = pdf.pages[i].extract_text() or ""
            for line in text.split("\n"):
                m = _LINE_PAT.match(line.strip())
                if not m:
                    continue

                name   = m.group(1).strip()
                state  = m.group(2).strip()
                timing = m.group(3).strip()

                # Normalise dashes (PDF uses em/en dashes)
                name = name.replace("–", "-").replace("—", "-").replace("�", "-")

                pid = _slug(name)
                if pid in seen:
                    continue
                seen.add(pid)

                projects.append({
                    "project_id": pid,
                    "name":       name,
                    "state":      state,
                    "timing":     timing,
                    "status":     _TIMING_STATUS.get(timing, "planned"),
                    "type":       _classify_type(name),
                })

    return projects


def _slug(name: str) -> str:
    """URL-safe slug, max 60 chars."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


def _classify_type(name: str) -> str:
    lower = name.lower()
    for type_name, keywords in _TYPE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return type_name
    return "infrastructure"


_CITY_BY_STATE: dict[str, str] = {
    "NSW": "Sydney", "VIC": "Melbourne", "QLD": "Brisbane",
    "SA": "Adelaide", "WA": "Perth", "TAS": "Hobart",
    "NT": "Darwin", "ACT": "Canberra",
}

# Known place names to scan for in project names
_PLACE_NAMES = [
    # Cities / regions
    "Melbourne", "Sydney", "Brisbane", "Adelaide", "Perth", "Hobart",
    "Darwin", "Canberra", "Gold Coast", "Sunshine Coast", "Ipswich",
    "Newcastle", "Wollongong", "Geelong", "Townsville", "Cairns",
    "Launceston", "Fremantle", "Gladstone", "Whyalla", "Burnie",
    "Kwinana", "Broome", "Kununurra", "Esperance", "Albany",
    # Ports
    "Port of Brisbane", "Port of Burnie", "Port of Melbourne",
    "Port of Adelaide", "Port of Gladstone",
    # Roads (strip generic suffixes when geocoding)
    "Bruce Highway", "Hume Highway", "Great Northern Highway",
    "South Coast Highway", "Pacific Highway", "Princes Highway",
    "Anketell Road",
    # Precincts / landmarks
    "Middle Arm Precinct", "Osborne Precinct", "Henderson Precinct",
    "Lefevre Peninsula",
    # Other geographic references
    "East Wanneroo", "Tallawong", "St Marys", "Leppington", "Macarthur",
    "Bradfield", "Beaudesert", "Salisbury", "Springvale",
    "Adelaide River", "Ord-East Kimberley", "Werribee",
    "Bolivar", "Launceston",
]
# Longest first so greedy match picks the most specific name
_PLACE_NAMES.sort(key=len, reverse=True)


_NON_PLACE_WORDS = re.compile(
    r"\b(future|stage|south east|metropolitan|network|program|development|"
    r"improvement[s]?|upgrade[s]?|planning|capacity|system|storage|transit|signalling|"
    r"rail|etcs|metronet|digital|hub|corridor|pipeline|precinct|link|"
    r"connection|connectivity|interconnect|water|energy|power|freight|"
    r"industrial|infrastructure)\b",
    re.IGNORECASE,
)


def _build_geocode_query(name: str, state: str) -> str:
    """Extract the best geographic term from a project name for Nominatim."""
    # 1. Parenthetical content — only use if it looks like a real place name
    paren = re.search(r'\(([^)]+)\)', name)
    if paren:
        content = paren.group(1).strip()
        # Skip: all-uppercase acronyms (METRONET, ETCS) or abstract text
        is_acronym = content.isupper() and len(content) <= 10
        has_non_place = _NON_PLACE_WORDS.search(content)
        if not is_acronym and not has_non_place:
            return f"{content}, {state}, Australia"

    # 2. Well-known place names embedded in the project name
    lower = name.lower()
    for place in _PLACE_NAMES:
        if place.lower() in lower:
            return f"{place}, {state}, Australia"

    # 3. "between X and Y" → use X
    between = re.search(r'\bbetween\s+([A-Z][a-zA-Z\s]+?)\s+and\s+', name)
    if between:
        return f"{between.group(1).strip()}, {state}, Australia"

    # 4. Fall back to the state capital
    city = _CITY_BY_STATE.get(state, state)
    return f"{city}, Australia"


def _geocode(
    name: str,
    state: str,
    session: requests.Session,
) -> tuple[float | None, float | None]:
    """Geocode via Nominatim. Returns (lat, lon) or (None, None).

    First tries the best-extracted query; if that returns no result, falls
    back to the state capital (ensuring all projects get approximate coords).
    """
    primary_query = _build_geocode_query(name, state)
    capital_query = f"{_CITY_BY_STATE.get(state, state)}, Australia"

    for query in dict.fromkeys([primary_query, capital_query]):  # deduplicated, ordered
        try:
            resp = session.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "countrycodes": "au", "limit": "1"},
                timeout=15,
            )
            resp.raise_for_status()
            results = resp.json()
            if results:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                label = "geocoded" if query == primary_query else "geocoded (capital fallback)"
                logger.info("  %s [%s] via '%s' -> (%.4f, %.4f)", label, name[:40], query[:40], lat, lon)
                return lat, lon
            logger.debug("  no result for query: %s", query)
            if query != capital_query:
                time.sleep(_GEOCODE_DELAY)  # rate-limit between attempts
        except Exception as exc:
            logger.warning("  geocode error: %s — %s", name[:40], exc)
            if query != capital_query:
                time.sleep(_GEOCODE_DELAY)

    logger.warning("  geocode failed entirely: %s", name[:60])
    return None, None


def _load_sa2_geodataframe(db: Session):
    """Load all SA2 polygons as a GeoDataFrame (EPSG:4326).

    Used by both the IA Priority List and iPAMS loaders.
    """
    import geopandas as gpd
    from shapely.geometry import shape as shp_shape

    sa2_codes: list[str] = []
    geometries: list = []

    for sa2_code, geojson_str in db.query(SA2Region.sa2_code, SA2Region.geometry_geojson).all():
        if not geojson_str:
            continue
        try:
            geom = shp_shape(json.loads(geojson_str))
            sa2_codes.append(sa2_code)
            geometries.append(geom)
        except Exception:
            pass

    return gpd.GeoDataFrame({"sa2_code": sa2_codes}, geometry=geometries, crs="EPSG:4326")


def _find_sa2s_for_project(
    lat: float,
    lon: float,
    sa2_gdf,
) -> list[tuple[str, float]]:
    """Return [(sa2_code, impact_score)] for the containing SA2 and its neighbours.

    - Containing SA2 (project point falls inside): score = 1.0
    - SA2s sharing a border with the containing SA2: score = 0.5

    If the point doesn't fall inside any SA2 (simplified geometry gaps, coastal
    projects), uses the nearest SA2 polygon within ~2 km as the primary.
    """
    from shapely.geometry import Point

    point = Point(lon, lat)  # shapely convention: (x=lon, y=lat)

    # --- 1. Find containing SA2 ---
    containing = sa2_gdf[sa2_gdf.geometry.contains(point)]

    if containing.empty:
        # Nearest polygon fallback (handles geometry simplification gaps / coastal projects)
        import warnings
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", "Geometry is in a geographic CRS")
            distances = sa2_gdf.geometry.distance(point)
        nearest_idx = distances.idxmin()
        if distances[nearest_idx] > 0.02:   # > ~2.2 km — project outside Australia
            return []
        containing = sa2_gdf.loc[[nearest_idx]]

    primary_code = containing.iloc[0]["sa2_code"]
    primary_geom = containing.iloc[0].geometry
    results = [(primary_code, 1.0)]

    # --- 2. Adjacent SA2s (share a boundary) ---
    # Buffer by ~110 m to bridge simplified-geometry slivers
    buffered = primary_geom.buffer(0.001)
    neighbours = sa2_gdf[
        (sa2_gdf["sa2_code"] != primary_code) &
        sa2_gdf.geometry.intersects(buffered)
    ]
    for _, row in neighbours.iterrows():
        results.append((row["sa2_code"], 0.5))

    return results
