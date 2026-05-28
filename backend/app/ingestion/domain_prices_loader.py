"""Domain API property price loader.

Fetches suburb performance statistics from the Domain Group API and stores
median sold prices, days on market, and auction clearance rates onto
existing abs_census_metrics rows.

Endpoint used
─────────────
GET /v2/suburbPerformanceStatistics/{state}/{suburb}/{postcode}
  ?propertyCategory=house|unit
  &chronologicalSpan=12       (12-month period)
  &tPlusFrom=1                (1 period back from current)
  &tPlusTo=1                  (same — most recent complete year)

Authentication: X-API-Key header.
Required scope: api_suburbperformance_read
  (add "Properties & Locations" package to your project at developer.domain.com.au)

SA2 → suburb + postcode resolution
────────────────────────────────────
SA2 names are ABS statistical areas, not always identical to Domain suburb names.
Resolution is two-step:

  1. Postcode — the ABS Mesh Block allocation files (MB_2021 and POA_2021) already
     downloaded for the ICSEA loader are used to find each SA2's dominant postcode
     (the postcode whose mesh blocks make up the largest share of the SA2 area).

  2. Suburb name — the SA2 name is cleaned into one or more candidates:
       • Remove state suffixes: "(Vic.)", "(NSW)", "(ACT)", "(SA)", "(WA)", "(QLD)", "(NT)", "(Tas.)"
       • If the name contains " - ", try the full name first, then just the
         part before " - " (e.g. "Caulfield - North" → try "Caulfield - North",
         then "Caulfield").
     Each candidate is tried in order; the first 200 response wins.

Columns written to abs_census_metrics:
    domain_median_house_price, domain_median_unit_price,
    domain_days_on_market, domain_clearance_rate

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.domain_prices \\
        --mb  "../data/datapacks/MB_2021_AUST.xlsx" \\
        --poa "../data/datapacks/POA_2021_AUST.xlsx" \\
        [--state VIC] [--year 2021]
    (API key is read from DOMAIN_API_KEY env var, or pass --api-key)
"""

from __future__ import annotations

import logging
import os
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics, SA2Region

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.domain.com.au"
_CLEARANCE_MIN_AUCTIONS = 10   # don't report clearance rate below this volume

# How long to wait between requests (seconds). Free tier = 1 000 RPM → ~1 req/60 ms.
# We use 120 ms to leave headroom.
_REQUEST_DELAY = 0.12

# Map DB state codes → Domain API lowercase codes
_STATE_MAP = {
    "VIC": "vic", "NSW": "nsw", "QLD": "qld",
    "SA": "sa",   "WA": "wa",   "ACT": "act",
    "TAS": "tas", "NT": "nt",
}


@dataclass
class DomainLoadReport:
    sa2s_processed: int = 0
    sa2s_updated: int = 0
    sa2s_no_postcode: int = 0
    sa2s_not_found: int = 0
    sa2s_no_metrics_row: int = 0
    api_errors: int = 0

    def __str__(self) -> str:
        return (
            f"Processed: {self.sa2s_processed} | "
            f"Updated: {self.sa2s_updated} | "
            f"No postcode: {self.sa2s_no_postcode} | "
            f"Not found in Domain: {self.sa2s_not_found} | "
            f"No metrics row: {self.sa2s_no_metrics_row} | "
            f"API errors: {self.api_errors}"
        )


def load_domain_prices(
    mb_file: Path,
    poa_file: Path,
    db: Session,
    api_key: str,
    *,
    year: int = 2021,
    state_filter: str | None = None,
) -> DomainLoadReport:
    """Fetch Domain suburb stats and upsert onto abs_census_metrics.

    Args:
        mb_file:      Path to MB_2021_AUST.xlsx (ABS Mesh Block → SA2 allocation).
        poa_file:     Path to POA_2021_AUST.xlsx (ABS Mesh Block → POA/postcode).
        db:           Synchronous SQLAlchemy session.
        api_key:      Domain API key (starts with key_).
        year:         Census year to update (default 2021).
        state_filter: If set (e.g. "VIC"), only process SA2s in that state.
    """
    report = DomainLoadReport()

    logger.info("Building SA2 → postcode lookup ...")
    sa2_postcode = _build_sa2_postcode_lookup(mb_file, poa_file)
    logger.info("Built postcode lookup for %d SA2s", len(sa2_postcode))

    q = db.query(SA2Region.sa2_code, SA2Region.sa2_name, SA2Region.state)
    if state_filter:
        q = q.filter(SA2Region.state == state_filter)
    sa2_rows = q.all()
    logger.info("Processing %d SA2s ...", len(sa2_rows))

    with httpx.Client(timeout=15.0) as client:
        for sa2_code, sa2_name, state in sa2_rows:
            report.sa2s_processed += 1

            postcode = sa2_postcode.get(sa2_code)
            if postcode is None:
                report.sa2s_no_postcode += 1
                logger.debug("No postcode for SA2 %s (%s)", sa2_code, sa2_name)
                continue

            domain_state = _STATE_MAP.get(state)
            if domain_state is None:
                logger.debug("Unknown state %s for SA2 %s — skipping", state, sa2_code)
                continue

            # Fetch house stats
            house_data = _fetch_suburb_stats(
                client, api_key, domain_state, sa2_name, postcode, "house", report
            )
            # Small pause between property categories
            time.sleep(_REQUEST_DELAY)
            # Fetch unit stats
            unit_data = _fetch_suburb_stats(
                client, api_key, domain_state, sa2_name, postcode, "unit", report
            )
            time.sleep(_REQUEST_DELAY)

            if house_data is None and unit_data is None:
                report.sa2s_not_found += 1
                continue

            metrics = db.get(ABSCEntensMetrics, (sa2_code, year))
            if metrics is None:
                report.sa2s_no_metrics_row += 1
                continue

            if house_data:
                metrics.domain_median_house_price = house_data.get("median_price")
                metrics.domain_days_on_market     = house_data.get("days_on_market")
                metrics.domain_clearance_rate     = house_data.get("clearance_rate")
            if unit_data:
                metrics.domain_median_unit_price = unit_data.get("median_price")

            report.sa2s_updated += 1

            if report.sa2s_processed % 50 == 0:
                logger.info(
                    "  Progress: %d / %d SA2s", report.sa2s_processed, len(sa2_rows)
                )
                db.flush()   # periodically flush to avoid huge uncommitted transactions

    db.commit()
    return report


# ---------------------------------------------------------------------------
# SA2 → postcode lookup
# ---------------------------------------------------------------------------

def _build_sa2_postcode_lookup(mb_file: Path, poa_file: Path) -> dict[str, str]:
    """Return {sa2_code: dominant_postcode} via ABS Mesh Block allocation files.

    The dominant postcode is the one whose mesh blocks make up the largest
    share of the SA2's total mesh block count.
    """
    logger.info("  Reading MB allocation file ...")
    mb = pd.read_excel(
        mb_file,
        usecols=["MB_CODE_2021", "SA2_CODE_2021"],
        dtype=str,
    )
    logger.info("  Reading POA allocation file ...")
    poa = pd.read_excel(
        poa_file,
        usecols=["MB_CODE_2021", "POA_CODE_2021"],
        dtype=str,
    )
    merged = mb.merge(poa, on="MB_CODE_2021", how="inner")
    # Count mesh blocks per (SA2, postcode) — more MBs = more of the SA2 is in that postcode
    counts = (
        merged.groupby(["SA2_CODE_2021", "POA_CODE_2021"])
        .size()
        .reset_index(name="mb_count")
    )
    # Keep only the postcode with the highest count for each SA2
    dominant = (
        counts.sort_values("mb_count", ascending=False)
        .drop_duplicates("SA2_CODE_2021")
    )
    # Postcodes in Australia are 4-digit strings; POA codes have leading zeros preserved
    result: dict[str, str] = {}
    for _, row in dominant.iterrows():
        sa2 = str(row["SA2_CODE_2021"]).zfill(9)
        poa_code = str(row["POA_CODE_2021"]).strip()
        # POA codes like "2600" are valid; skip non-numeric (e.g. "XXX" for no fixed address)
        if re.match(r"^\d{4}$", poa_code):
            result[sa2] = poa_code
    return result


# ---------------------------------------------------------------------------
# SA2 name → suburb name candidates
# ---------------------------------------------------------------------------

_STATE_SUFFIX_RE = re.compile(
    r"\s*\((Vic\.|NSW|ACT|SA|WA|QLD|NT|Tas\.)\)\s*$", re.IGNORECASE
)


def _suburb_candidates(sa2_name: str) -> list[str]:
    """Return ordered suburb name candidates from an SA2 name.

    Examples:
        "Richmond"                   → ["Richmond"]
        "St Kilda (Vic.)"            → ["St Kilda"]
        "Carlton North - Princes Hill" → ["Carlton North - Princes Hill", "Carlton North"]
        "Melbourne CBD - West"       → ["Melbourne CBD - West", "Melbourne CBD"]
        "Caulfield - North"          → ["Caulfield - North", "Caulfield"]
    """
    # Strip state suffix
    name = _STATE_SUFFIX_RE.sub("", sa2_name).strip()
    candidates = [name]
    if " - " in name:
        candidates.append(name.split(" - ")[0].strip())
    return candidates


# ---------------------------------------------------------------------------
# Domain API calls
# ---------------------------------------------------------------------------

def _fetch_suburb_stats(
    client: httpx.Client,
    api_key: str,
    state: str,
    sa2_name: str,
    postcode: str,
    property_category: str,
    report: DomainLoadReport,
) -> dict | None:
    """Try each suburb name candidate until Domain returns a result.

    Returns a dict with keys: median_price, days_on_market, clearance_rate
    or None if no candidate matched.
    """
    headers = {"X-API-Key": api_key}
    params = {
        "propertyCategory": property_category,
        "chronologicalSpan": 12,
        "tPlusFrom": 1,
        "tPlusTo": 1,
    }

    for candidate in _suburb_candidates(sa2_name):
        suburb_slug = urllib.parse.quote(candidate.lower())
        url = f"{_BASE_URL}/v2/suburbPerformanceStatistics/{state}/{suburb_slug}/{postcode}"
        try:
            resp = client.get(url, headers=headers, params=params)
        except httpx.RequestError as exc:
            logger.warning("Request error for %s/%s: %s", sa2_name, property_category, exc)
            report.api_errors += 1
            return None

        if resp.status_code == 200:
            return _parse_response(resp.json())

        if resp.status_code == 404:
            # Try next candidate
            continue

        if resp.status_code == 401:
            raise RuntimeError(
                "Domain API returned 401 Unauthorized. "
                "Check your API key and ensure 'Properties & Locations' access is approved."
            )

        if resp.status_code == 403:
            raise RuntimeError(
                "Domain API returned 403 Forbidden. "
                "Access to Properties & Locations may still be pending approval."
            )

        if resp.status_code == 429:
            logger.warning("Rate limited — sleeping 5 s ...")
            time.sleep(5)
            report.api_errors += 1
            return None

        logger.warning(
            "Unexpected %d for %s/%s/%s (%s): %s",
            resp.status_code, state, candidate, postcode, property_category,
            resp.text[:200],
        )
        report.api_errors += 1
        return None

    return None   # all candidates exhausted


def _parse_response(data: dict) -> dict | None:
    """Extract the key metrics from a Domain API response."""
    try:
        series_info = data["series"]["seriesInfo"]
    except (KeyError, TypeError):
        return None

    if not series_info:
        return None

    # tPlusFrom=tPlusTo=1 → single entry for the most recent complete period
    values = series_info[0].get("values", {})
    if not values:
        return None

    median_price = _to_float(values.get("medianSoldPrice"))
    days_on_market = _to_float(values.get("daysOnMarket"))

    # Clearance rate: only report if statistically meaningful
    auctioned   = _to_int(values.get("auctionNumberAuctioned")) or 0
    sold        = _to_int(values.get("auctionNumberSold")) or 0
    withdrawn   = _to_int(values.get("auctionNumberWithdrawn")) or 0
    denominator = auctioned + withdrawn
    clearance_rate: float | None = None
    if denominator >= _CLEARANCE_MIN_AUCTIONS:
        clearance_rate = sold / denominator

    return {
        "median_price":    median_price,
        "days_on_market":  days_on_market,
        "clearance_rate":  clearance_rate,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_float(val) -> float | None:
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _to_int(val) -> int | None:
    f = _to_float(val)
    return int(f) if f is not None else None
