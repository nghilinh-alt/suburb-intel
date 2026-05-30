"""Tertiary education facilities loader.

Fetches university and TAFE campus locations from the Geoscience Australia
Foundation Facilities ArcGIS service (Education layer) and upserts them
into the schools table + sa2_school_link using the same containment +
adjacency model as the ACARA school profile loader.

Data source
───────────
GA Foundation Facilities Points — Layer 0: Education_Facilities
URL: https://services.ga.gov.au/gis/rest/services/Foundation_Facilities_Points/MapServer/0
Licence: Creative Commons Attribution 4.0 — © State/Territory governments 2020
Coverage: QLD, NSW, VIC, TAS only (other states excluded by GA due to licensing)

Type mapping:
  Tertiary Institution → school_type = 'University'
  Technical College    → school_type = 'TAFE'
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

import requests
import urllib3

from sqlalchemy.orm import Session

from app.db.models import School, SA2SchoolLink
from app.ingestion.infrastructure_loader import (
    _load_sa2_geodataframe,
    _find_sa2s_for_project,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

_GA_URL       = "https://services.ga.gov.au/gis/rest/services/Foundation_Facilities_Points/MapServer/0/query"
_PAGE_SIZE    = 1000
_REQUEST_DELAY = 0.3
_SOURCE       = "GA Foundation Facilities"
_SOURCE_YEAR  = 2020  # GA data vintage

_TYPE_MAP = {
    "Tertiary Institution": "University",
    "Technical College":    "TAFE",
}


@dataclass
class TertiaryLoadReport:
    fetched: int = 0
    upserted: int = 0
    skipped_unnamed: int = 0
    skipped_no_coords: int = 0
    sa2_links: int = 0

    def __str__(self) -> str:
        return (
            f"Fetched: {self.fetched} | "
            f"Upserted: {self.upserted} | "
            f"Skipped unnamed: {self.skipped_unnamed} | "
            f"Skipped no coords: {self.skipped_no_coords} | "
            f"SA2 links: {self.sa2_links}"
        )


def load_tertiary_education(db: Session) -> TertiaryLoadReport:
    report = TertiaryLoadReport()

    logger.info("Loading SA2 geometries ...")
    sa2_gdf = _load_sa2_geodataframe(db)
    logger.info("Loaded %d SA2 polygons", len(sa2_gdf))

    logger.info("Fetching GA tertiary facilities ...")
    features = _fetch_all_features(report)
    logger.info("Fetched %d features", report.fetched)

    # Remove existing GA-sourced tertiary links before reload
    existing_ga_ids = [
        row[0] for row in db.query(School.acara_id).filter(School.source == _SOURCE).all()
    ]
    if existing_ga_ids:
        db.query(SA2SchoolLink).filter(
            SA2SchoolLink.acara_id.in_(existing_ga_ids)
        ).delete(synchronize_session=False)
        logger.info("Cleared %d existing GA school links", len(existing_ga_ids))

    for feat in features:
        attrs = feat.get("attributes", {})
        geom  = feat.get("geometry")
        oid   = attrs.get("objectid")
        name  = (attrs.get("name") or "").strip()
        mf    = attrs.get("main_function") or ""

        if not name or name.upper() == "UNKNOWN":
            report.skipped_unnamed += 1
            continue

        school_type = _TYPE_MAP.get(mf)
        if not school_type:
            continue

        lat = lon = None
        if geom:
            lon = geom.get("x")
            lat = geom.get("y")

        acara_id = f"ga-{oid}"

        existing = db.get(School, acara_id)
        fields = dict(
            name=name,
            suburb=attrs.get("suburb"),
            state=attrs.get("state"),
            postcode=None,
            sector=None,
            school_type=school_type,
            is_special=0,
            lat=float(lat) if lat is not None else None,
            lon=float(lon) if lon is not None else None,
            sa2_code=None,
            remoteness=None,
            year_range=None,
            icsea=None,
            icsea_percentile=None,
            total_enrolments=None,
            indigenous_pct=None,
            source_year=_SOURCE_YEAR,
            source=_SOURCE,
            acara_location_age_id=None,
        )

        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
        else:
            db.add(School(acara_id=acara_id, **fields))
        report.upserted += 1

        if lat is None or lon is None:
            report.skipped_no_coords += 1
            continue

        for sa2_code, score in _find_sa2s_for_project(lat, lon, sa2_gdf):
            db.add(SA2SchoolLink(
                sa2_code=sa2_code,
                acara_id=acara_id,
                impact_score=score,
            ))
            report.sa2_links += 1

    db.commit()
    return report


def _fetch_all_features(report: TertiaryLoadReport) -> list[dict]:
    session = requests.Session()
    session.verify = False
    session.headers["User-Agent"] = "SuburbIntel/1.0"

    type_list = ", ".join(f"'{t}'" for t in _TYPE_MAP)
    where = f"main_function IN ({type_list}) AND name NOT IN ('Unknown', '')"

    features: list[dict] = []
    offset = 0

    while True:
        params = {
            "where":             where,
            "outFields":         "objectid,name,main_function,operationalstatus,address,suburb,state",
            "returnGeometry":    "true",
            "outSR":             "4326",
            "resultOffset":      offset,
            "resultRecordCount": _PAGE_SIZE,
            "f":                 "json",
        }
        try:
            resp = session.get(_GA_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("GA fetch failed at offset %d: %s", offset, exc)
            break

        page = data.get("features", [])
        features.extend(page)
        report.fetched += len(page)

        if not data.get("exceededTransferLimit", False):
            break

        offset += _PAGE_SIZE
        time.sleep(_REQUEST_DELAY)

    return features
