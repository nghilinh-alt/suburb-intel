"""iPAMS (Infrastructure Planning and Asset Management System) loader.

Fetches all Commonwealth-funded road and rail projects from the Department of
Infrastructure's ArcGIS feature service, converts coordinates, parses costs,
upserts into infrastructure_projects, and links active projects to nearby SA2s.

Data source
───────────
URL: https://spatial.infrastructure.gov.au/server/rest/services/iPAMS-DB/
       AuslinkGIS_Point_web/FeatureServer/0
Coordinate system: EPSG:3857 (Web Mercator) → converted to WGS84 on ingest
Record count: ~1 100 projects (228 active as of May 2026)

Columns written to infrastructure_projects
──────────────────────────────────────────
project_id     — "ipams-<Project_ID>" (e.g. "ipams-053428-14vic-np")
name           — ProjectName
type           — "road" | "rail" | "infrastructure"  (from TransportMode)
value_aud      — EstimatedProjectCost parsed to integer AUD
agc_aud        — AGC (Australian Government Commitment) parsed to integer AUD
status         — normalised ProjectStatus code
lat / lon      — EPSG:3857 converted to WGS84
state          — State field (e.g. "VIC")
timing         — "<ExpectedStartDate> to <ExpectedEndDate>" or start-only
source         — "iPAMS"
sub_program    — SubProgram (e.g. "Black Spot Projects")
expected_start — ExpectedStartDate string
expected_end   — ExpectedEndDate string
project_url    — URL to project detail page

SA2 links (sa2_project_link)
─────────────────────────────
Written for non-completed projects (status not in completed / not_proceeding).
impact_score = 1.0 − (dist_km / 25.0) for SA2 centroids within 25 km.

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.ipams
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from math import atan, pi, sinh
from pathlib import Path

import urllib3
import requests
from sqlalchemy.orm import Session

from app.db.models import InfrastructureProject, SA2ProjectLink, SA2Region
from app.ingestion.infrastructure_loader import (
    _haversine,
    _load_sa2_centroids,
    _find_nearby_sa2s,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

_FEATURE_SERVICE = (
    "https://spatial.infrastructure.gov.au/server/rest/services"
    "/iPAMS-DB/AuslinkGIS_Point_web/FeatureServer/0/query"
)
_PAGE_SIZE     = 2000   # server max
_REQUEST_DELAY = 0.5    # seconds between pages
_SOURCE        = "iPAMS"
_IMPACT_RADIUS_KM = 25.0

_OUT_FIELDS = ",".join([
    "OBJECTID", "Project_ID", "ProjectName", "SubProgram",
    "ProjectStatus", "TransportMode",
    "EstimatedProjectCost", "AGC",
    "State", "URL", "ExpectedStartDate", "ExpectedEndDate",
    "ProjectDetails",
])

_STATUS_MAP: dict[str, str] = {
    "completed":              "completed",
    "under construction":     "under_construction",
    "underway":               "under_construction",
    "in planning":            "in_planning",
    "not currently proceeding": "not_proceeding",
}

_TRANSPORT_TYPE: dict[str, str] = {
    "road": "road",
    "rail": "rail",
}

# Only create SA2 links for these statuses
_ACTIVE_STATUSES = {"in_planning", "under_construction"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class IPAMSReport:
    records_fetched:  int = 0
    projects_upserted: int = 0
    sa2_links:        int = 0

    def __str__(self) -> str:
        return (
            f"Fetched: {self.records_fetched} | "
            f"Upserted: {self.projects_upserted} | "
            f"SA2 links: {self.sa2_links}"
        )


def load_ipams_projects(db: Session) -> IPAMSReport:
    """Fetch all iPAMS projects, upsert into DB, link active ones to SA2s."""
    report = IPAMSReport()

    logger.info("Fetching iPAMS projects from ArcGIS feature service ...")
    features = _fetch_all_features(report)
    logger.info("Fetched %d features", report.records_fetched)

    logger.info("Loading SA2 centroids ...")
    sa2_centroids = _load_sa2_centroids(db)
    logger.info("Loaded %d SA2 centroids", len(sa2_centroids))

    for feat in features:
        attrs    = feat.get("attributes", {})
        geom     = feat.get("geometry")

        project_id = _make_project_id(attrs)
        name       = (attrs.get("ProjectName") or "").strip()
        if not name:
            continue

        status = _STATUS_MAP.get(
            (attrs.get("ProjectStatus") or "").lower(), "unknown"
        )
        ptype = _TRANSPORT_TYPE.get(
            (attrs.get("TransportMode") or "").lower(), "infrastructure"
        )
        value_aud      = _parse_cost(attrs.get("EstimatedProjectCost"))
        agc_aud        = _parse_cost(attrs.get("AGC"))
        state          = (attrs.get("State") or "").strip()
        sub_program    = (attrs.get("SubProgram") or "").strip()
        expected_start = (attrs.get("ExpectedStartDate") or "").strip() or None
        expected_end   = (attrs.get("ExpectedEndDate") or "").strip() or None
        project_url    = (attrs.get("URL") or "").strip() or None

        timing = _build_timing(expected_start, expected_end)

        lat, lon = (None, None)
        if geom:
            lat, lon = _web_mercator_to_wgs84(geom["x"], geom["y"])

        existing = db.get(InfrastructureProject, project_id)
        if existing:
            existing.name           = name
            existing.type           = ptype
            existing.value_aud      = value_aud
            existing.agc_aud        = agc_aud
            existing.status         = status
            existing.lat            = lat
            existing.lon            = lon
            existing.state          = state
            existing.timing         = timing
            existing.source         = _SOURCE
            existing.sub_program    = sub_program
            existing.expected_start = expected_start
            existing.expected_end   = expected_end
            existing.project_url    = project_url
        else:
            db.add(InfrastructureProject(
                project_id     = project_id,
                name           = name,
                type           = ptype,
                value_aud      = value_aud,
                agc_aud        = agc_aud,
                status         = status,
                lat            = lat,
                lon            = lon,
                state          = state,
                timing         = timing,
                source         = _SOURCE,
                sub_program    = sub_program,
                expected_start = expected_start,
                expected_end   = expected_end,
                project_url    = project_url,
            ))
        report.projects_upserted += 1

        # SA2 proximity links — active projects only
        if lat is not None and status in _ACTIVE_STATUSES:
            db.query(SA2ProjectLink).filter(
                SA2ProjectLink.project_id == project_id
            ).delete(synchronize_session=False)
            for sa2_code, impact_score in _find_nearby_sa2s(lat, lon, sa2_centroids):
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

def _fetch_all_features(report: IPAMSReport) -> list[dict]:
    """Paginate through the ArcGIS feature service."""
    session = requests.Session()
    session.verify = False
    session.headers["User-Agent"] = "SuburbIntel/1.0"

    features: list[dict] = []
    offset = 0

    while True:
        params = {
            "where":             "1=1",
            "outFields":         _OUT_FIELDS,
            "resultOffset":      offset,
            "resultRecordCount": _PAGE_SIZE,
            "returnGeometry":    "true",
            "f":                 "json",
        }
        try:
            resp = session.get(_FEATURE_SERVICE, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Request failed at offset %d: %s", offset, exc)
            break

        page = data.get("features", [])
        features.extend(page)
        report.records_fetched += len(page)

        if offset == 0:
            logger.info("  Page 1: %d features", len(page))
        elif offset % (_PAGE_SIZE * 2) == 0:
            logger.info("  Fetched %d so far ...", report.records_fetched)

        if not data.get("exceededTransferLimit", False):
            break

        offset += _PAGE_SIZE
        time.sleep(_REQUEST_DELAY)

    return features


def _make_project_id(attrs: dict) -> str:
    raw = (attrs.get("Project_ID") or "").strip()
    if raw:
        slug = re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-")
        return f"ipams-{slug}"
    return f"ipams-obj-{attrs.get('OBJECTID', 'unknown')}"


def _parse_cost(s: str | None) -> int | None:
    if not s:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(s))
    if not cleaned:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


def _web_mercator_to_wgs84(x: float, y: float) -> tuple[float, float]:
    """Convert EPSG:3857 (Web Mercator) metres to WGS84 decimal degrees."""
    lon = x / 20037508.342 * 180.0
    lat = atan(sinh(y / 6378137.0)) * 180.0 / pi
    return lat, lon


def _build_timing(start: str | None, end: str | None) -> str | None:
    if start and end:
        return f"{start} to {end}"
    return start or end or None
