"""ABS Population Projections loader (SA2 level).

Fetches ABS population projections for each SA2 via the Digital Atlas of
Australia ArcGIS feature service (free, no API key required).

Data source
───────────
ABS Population Projections SA2 2022–2032 (Series B — medium assumptions)
Feature service: https://services-ap1.arcgis.com/ypkPEy1AmwPKGNNv/arcgis/rest/services/ABS_PopProj_2232_SA2/FeatureServer/0

Fields fetched: sa2_code_2021, ref_date, prj_persons
Paginated at 2 000 records/request (~13 requests for all SA2s × 10 years).

Columns written to abs_census_metrics
──────────────────────────────────────
pop_proj_2026       — projected total population 30 June 2026
pop_proj_2031       — projected total population 30 June 2031
pop_growth_proj_pct — % change from 2023 to 2031

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.population_projections
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import urllib3
import requests
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics

logger = logging.getLogger(__name__)

_FEATURE_SERVICE = (
    "https://services-ap1.arcgis.com/ypkPEy1AmwPKGNNv/arcgis/rest/services"
    "/ABS_PopProj_2232_SA2/FeatureServer/0/query"
)
_PAGE_SIZE   = 1000    # ArcGIS service max record count
_REQUEST_DELAY = 0.5   # seconds between paginated requests


@dataclass
class PopProjectionsReport:
    records_fetched: int = 0
    sa2s_updated:    int = 0
    sa2s_no_row:     int = 0

    def __str__(self) -> str:
        return (
            f"Records fetched: {self.records_fetched} | "
            f"SA2 rows updated: {self.sa2s_updated} | "
            f"No metrics row: {self.sa2s_no_row}"
        )


def load_population_projections(
    db: Session,
    *,
    year: int = 2021,
) -> PopProjectionsReport:
    """Fetch ABS SA2 population projections and upsert onto abs_census_metrics.

    Args:
        db:   Synchronous SQLAlchemy session.
        year: Census year row to update (default 2021).
    """
    report = PopProjectionsReport()

    logger.info("Fetching population projections from ArcGIS feature service ...")
    all_records = _fetch_all_projections(report)
    logger.info("Fetched %d projection records", report.records_fetched)

    # Build lookup: sa2_code → {year: projected_population}
    projections: dict[str, dict[int, int]] = {}
    for rec in all_records:
        attrs = rec.get("attributes", {})
        sa2   = attrs.get("sa2_code_2021")
        pop   = attrs.get("prj_persons")
        # ref_date is a Unix timestamp in ms
        ref_ms = attrs.get("ref_date")
        if sa2 is None or pop is None or ref_ms is None:
            continue
        proj_year = _ms_to_year(ref_ms)
        if proj_year is None:
            continue
        projections.setdefault(str(sa2), {})[proj_year] = int(pop)

    logger.info("Projections parsed for %d SA2s", len(projections))

    # Upsert
    for sa2_code, year_map in projections.items():
        metrics = db.get(ABSCEntensMetrics, (sa2_code, year))
        if metrics is None:
            report.sa2s_no_row += 1
            continue

        proj_2023 = year_map.get(2023)
        proj_2026 = year_map.get(2026)
        proj_2031 = year_map.get(2031)

        metrics.pop_proj_2026 = proj_2026
        metrics.pop_proj_2031 = proj_2031

        if proj_2023 and proj_2031 and proj_2023 > 0:
            metrics.pop_growth_proj_pct = round(
                (proj_2031 - proj_2023) / proj_2023 * 100, 2
            )
        else:
            metrics.pop_growth_proj_pct = None

        report.sa2s_updated += 1

    db.commit()
    return report


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_all_projections(report: PopProjectionsReport) -> list[dict]:
    """Paginate through the ArcGIS feature service and return all records."""
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    session = requests.Session()
    session.verify = False
    session.headers["User-Agent"] = "SuburbIntel/1.0"

    records: list[dict] = []
    offset = 0

    while True:
        params = {
            "where":             "1=1",
            "outFields":         "sa2_code_2021,ref_date,prj_persons",
            "resultOffset":      offset,
            "resultRecordCount": _PAGE_SIZE,
            "f":                 "json",
        }

        try:
            resp = session.get(_FEATURE_SERVICE, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("ArcGIS request failed at offset %d: %s", offset, exc)
            break

        features = data.get("features", [])
        records.extend(features)
        report.records_fetched += len(features)

        if offset == 0:
            logger.info("  Page 1: %d records", len(features))
        elif offset % (_PAGE_SIZE * 5) == 0:
            logger.info("  Fetched %d records so far ...", report.records_fetched)

        # ArcGIS signals more pages via exceededTransferLimit=true;
        # if absent (or false) and we got a full page, assume done
        if not data.get("exceededTransferLimit", False):
            break

        offset += _PAGE_SIZE
        time.sleep(_REQUEST_DELAY)

    return records


def _ms_to_year(ms: int | float) -> int | None:
    """Convert ArcGIS Unix timestamp (ms) to a calendar year."""
    try:
        from datetime import datetime, timezone
        dt = datetime.fromtimestamp(ms / 1000, tz=timezone.utc)
        return dt.year
    except Exception:
        return None
