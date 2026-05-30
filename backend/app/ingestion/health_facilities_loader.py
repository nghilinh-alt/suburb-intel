"""Health facilities loader.

Two complementary sources:

  AIHW MyHospitals API (v0)
  ─────────────────────────
  URL: https://myhospitalsapi.aihw.gov.au/api/v0/retired-myhospitals-api/hospitals
  Covers: public and private hospitals nationally, with lat/lon and ispublic flag.
  Used as the authoritative hospital source (691 active public, 429 active private).

  Geoscience Australia Foundation Facilities (ArcGIS MapServer, layer 1)
  ───────────────────────────────────────────────────────────────────────
  URL: https://services.ga.gov.au/gis/rest/services/Foundation_Facilities_Points/MapServer/1
  Covers: Aged Care, Nursing Homes, Indigenous Health Centres, Disability Support.
  Hospital records are skipped (AIHW is authoritative for hospitals).
  Licence: Creative Commons Attribution 4.0 — © Australian Department of Health 2020.

Tables written
──────────────
health_facilities  — one row per facility (upsert on facility_id)
sa2_health_link    — containing SA2 (score=1.0) + border-adjacent SA2s (score=0.5)

Usage (CLI):
    python -m app.ingestion.health_facilities
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import urllib3
import requests
from sqlalchemy.orm import Session

from app.db.models import HealthFacility, SA2HealthLink
from app.ingestion.infrastructure_loader import (
    _load_sa2_geodataframe,
    _find_sa2s_for_project,
)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

_AIHW_URL = "https://myhospitalsapi.aihw.gov.au/api/v0/retired-myhospitals-api/hospitals"
_GA_URL   = "https://services.ga.gov.au/gis/rest/services/Foundation_Facilities_Points/MapServer/1/query"
_GA_PAGE_SIZE    = 1000
_GA_REQUEST_DELAY = 0.3

# GA main_function values to ingest (skip Hospital — AIHW is authoritative)
_GA_TYPE_MAP = {
    "Aged Care Facility":     "aged_care",
    "Nursing Home":           "nursing_home",
    "Indigenous Health Centre": "indigenous_health",
    "Disability Support Service": "disability_support",
}

_SOURCE_AIHW = "AIHW"
_SOURCE_GA   = "GA Foundation Facilities"


@dataclass
class HealthLoadReport:
    aihw_fetched: int = 0
    ga_fetched: int = 0
    facilities_upserted: int = 0
    sa2_links: int = 0
    skipped_no_coords: int = 0

    def __str__(self) -> str:
        return (
            f"AIHW fetched: {self.aihw_fetched} | "
            f"GA fetched: {self.ga_fetched} | "
            f"Facilities upserted: {self.facilities_upserted} | "
            f"SA2 links: {self.sa2_links} | "
            f"Skipped (no coords): {self.skipped_no_coords}"
        )


def load_health_facilities(db: Session) -> HealthLoadReport:
    report = HealthLoadReport()

    logger.info("Loading SA2 geometries ...")
    sa2_gdf = _load_sa2_geodataframe(db)
    logger.info("Loaded %d SA2 polygons", len(sa2_gdf))

    # Full reload of links
    db.query(SA2HealthLink).delete(synchronize_session=False)

    logger.info("Fetching AIHW hospitals ...")
    aihw_records = _fetch_aihw(report)
    logger.info("Fetched %d AIHW hospital records", report.aihw_fetched)

    logger.info("Fetching GA Foundation Facilities (non-hospital) ...")
    ga_records = _fetch_ga(report)
    logger.info("Fetched %d GA facility records", report.ga_fetched)

    all_records = aihw_records + ga_records
    logger.info("Upserting %d total facilities ...", len(all_records))

    for rec in all_records:
        facility_id = rec["facility_id"]
        lat = rec.get("lat")
        lon = rec.get("lon")

        existing = db.get(HealthFacility, facility_id)
        if existing:
            for k, v in rec.items():
                if k != "facility_id":
                    setattr(existing, k, v)
        else:
            db.add(HealthFacility(**rec))
        report.facilities_upserted += 1

        if lat is None or lon is None:
            report.skipped_no_coords += 1
            continue

        for sa2_code, score in _find_sa2s_for_project(lat, lon, sa2_gdf):
            db.add(SA2HealthLink(
                sa2_code=sa2_code,
                facility_id=facility_id,
                impact_score=score,
            ))
            report.sa2_links += 1

    db.commit()
    return report


# ---------------------------------------------------------------------------
# AIHW fetcher
# ---------------------------------------------------------------------------

def _fetch_aihw(report: HealthLoadReport) -> list[dict]:
    session = requests.Session()
    session.verify = False
    session.headers.update({"User-Agent": "SuburbIntel/1.0", "Accept": "application/json"})

    try:
        resp = session.get(_AIHW_URL, timeout=30)
        resp.raise_for_status()
        hospitals = resp.json()
    except Exception as exc:
        logger.error("AIHW fetch failed: %s", exc)
        return []

    records = []
    for h in hospitals:
        if h.get("isclosed"):
            continue
        facility_type = "public_hospital" if h.get("ispublic") else "private_hospital"
        code = str(h.get("code") or h.get("id"))
        lat = h.get("latitude")
        lon = h.get("longitude")
        records.append({
            "facility_id":    f"aihw-{code}",
            "name":           (h.get("name") or "").strip(),
            "facility_type":  facility_type,
            "lat":            float(lat) if lat is not None else None,
            "lon":            float(lon) if lon is not None else None,
            "state":          h.get("state"),
            "address":        None,
            "suburb":         None,
            "phn_name":       h.get("phnname"),
            "is_operational": 1,
            "source":         _SOURCE_AIHW,
            "source_id":      code,
        })
        report.aihw_fetched += 1

    return records


# ---------------------------------------------------------------------------
# GA Foundation Facilities fetcher
# ---------------------------------------------------------------------------

def _fetch_ga(report: HealthLoadReport) -> list[dict]:
    session = requests.Session()
    session.verify = False
    session.headers["User-Agent"] = "SuburbIntel/1.0"

    type_filter = ", ".join(f"'{t}'" for t in _GA_TYPE_MAP)
    where = f"main_function IN ({type_filter}) AND operationalstatus = 'Operational'"

    records: list[dict] = []
    offset = 0

    while True:
        params = {
            "where":             where,
            "outFields":         "objectid,name,main_function,operationalstatus,address,suburb,state",
            "returnGeometry":    "true",
            "outSR":             "4326",
            "resultOffset":      offset,
            "resultRecordCount": _GA_PAGE_SIZE,
            "f":                 "json",
        }
        try:
            resp = session.get(_GA_URL, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("GA fetch failed at offset %d: %s", offset, exc)
            break

        features = data.get("features", [])
        for feat in features:
            attrs = feat.get("attributes", {})
            geom  = feat.get("geometry")
            oid   = attrs.get("objectid")
            mf    = attrs.get("main_function") or ""
            ftype = _GA_TYPE_MAP.get(mf)
            if not ftype:
                continue

            lat = lon = None
            if geom:
                lon = geom.get("x")
                lat = geom.get("y")

            records.append({
                "facility_id":    f"ga-{oid}",
                "name":           (attrs.get("name") or "").strip(),
                "facility_type":  ftype,
                "lat":            float(lat) if lat is not None else None,
                "lon":            float(lon) if lon is not None else None,
                "state":          attrs.get("state"),
                "address":        attrs.get("address"),
                "suburb":         attrs.get("suburb"),
                "phn_name":       None,
                "is_operational": 1,
                "source":         _SOURCE_GA,
                "source_id":      str(oid),
            })
            report.ga_fetched += 1

        if not data.get("exceededTransferLimit", False):
            break

        offset += _GA_PAGE_SIZE
        time.sleep(_GA_REQUEST_DELAY)

    return records
