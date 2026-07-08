"""PropRadar sold-listing loader.

Fetches recent sold-property records from PropRadar and upserts them onto
`property_sales`, tied to `sa2_code` via the same SA2-name candidate matching
already used by domain_prices_loader.py's `_suburb_candidates` (no postcode
needed — this endpoint takes a suburb name directly, unlike Domain's).

Endpoint used
─────────────
GET /v1/suburbs/{state}/{suburb}/sold — paginated recent sold properties.
Authentication: X-API-Key header.

Response shape — NOT YET VERIFIED against a real 200 response
────────────────────────────────────────────────────────────
As of writing, the configured PROPRADAR_API_KEY returns 402
"subscription_expired" (reactivate at https://api.propradar.com.au/developers/dashboard).
Field parsing below is a best-effort guess from PropRadar's documented field
list (beds/baths/type/price/date), with defensive fallbacks across likely
naming variants (see `_parse_listing`, `_extract_listings`, `_next_page_cursor`).
Once the subscription is active, run a single-suburb pilot first and check
the logged raw JSON (`logger.debug` on the first page) before trusting a
full-state run — adjust the key-fallback lists if the real shape differs.

Quota
─────
Free tier = 50 calls/month. Each page of each suburb costs one call. Always
scope with --state and prefer --suburb for a single targeted pilot; `--max-pages`
defaults to a small safety cap so one run can't silently exhaust the quota.

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.propradar_sold --state QLD --suburb Chermside
    (API key is read from PROPRADAR_API_KEY env var)
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.db.models import PropertySale, SA2Region
from app.ingestion.domain_prices_loader import _suburb_candidates

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.propradar.com.au"
_REQUEST_DELAY = 0.5  # seconds between calls — free tier has almost no headroom anyway
_DEFAULT_MAX_PAGES = 3  # safety cap per suburb so one run can't blow the monthly quota

# Map DB state codes -> PropRadar's expected path segment (lowercase, per the
# one endpoint we've confirmed reachable: /v1/suburbs/QLD/chermside/sold used
# the state code as-is, uppercase).
_STATE_MAP = {
    "NSW": "NSW", "VIC": "VIC", "QLD": "QLD", "SA": "SA",
    "WA": "WA", "ACT": "ACT", "TAS": "TAS", "NT": "NT",
}


@dataclass
class PropRadarLoadReport:
    suburbs_processed: int = 0
    suburbs_matched: int = 0
    suburbs_not_found: int = 0
    listings_upserted: int = 0
    api_calls: int = 0
    api_errors: int = 0

    def __str__(self) -> str:
        return (
            f"Suburbs processed: {self.suburbs_processed} | "
            f"Matched: {self.suburbs_matched} | "
            f"Not found: {self.suburbs_not_found} | "
            f"Listings upserted: {self.listings_upserted} | "
            f"API calls used: {self.api_calls} | "
            f"API errors: {self.api_errors}"
        )


def load_propradar_sold(
    db: Session,
    api_key: str,
    *,
    state: str,
    suburb: str | None = None,
    max_pages: int = _DEFAULT_MAX_PAGES,
) -> PropRadarLoadReport:
    """Fetch recent sold listings for SA2s in `state` (optionally one `suburb`).

    Args:
        db:        Synchronous SQLAlchemy session.
        api_key:   PropRadar API key (starts with pr_live_ or pr_test_).
        state:     State code to scope the run (e.g. "QLD"). Required — a full
                   national run would exceed the free-tier monthly quota.
        suburb:    If set, only process SA2s whose name matches this suburb
                   (case-insensitive substring) — use for a single-suburb pilot.
        max_pages: Safety cap on pages fetched per suburb (quota protection).
    """
    report = PropRadarLoadReport()

    domain_state = _STATE_MAP.get(state)
    if domain_state is None:
        raise ValueError(f"Unknown state code: {state}")

    q = db.query(SA2Region.sa2_code, SA2Region.sa2_name).filter(SA2Region.state == state)
    if suburb:
        q = q.filter(SA2Region.sa2_name.ilike(f"%{suburb}%"))
    sa2_rows = q.all()
    logger.info("Processing %d SA2s in %s ...", len(sa2_rows), state)

    with httpx.Client(timeout=15.0) as client:
        for sa2_code, sa2_name in sa2_rows:
            report.suburbs_processed += 1
            listings = _fetch_all_pages(client, api_key, domain_state, sa2_name, max_pages, report)

            if listings is None:
                report.suburbs_not_found += 1
                continue

            report.suburbs_matched += 1
            for listing in listings:
                sale = _parse_listing(listing, sa2_code, state)
                if sale is None:
                    continue
                db.merge(sale)
                report.listings_upserted += 1

            db.commit()

    return report


# ---------------------------------------------------------------------------
# PropRadar API calls
# ---------------------------------------------------------------------------

def _fetch_all_pages(
    client: httpx.Client,
    api_key: str,
    state: str,
    sa2_name: str,
    max_pages: int,
    report: PropRadarLoadReport,
) -> list[dict] | None:
    """Try each suburb-name candidate until one returns 200, then page through
    results (bounded by max_pages). Returns None if no candidate matched."""
    headers = {"X-API-Key": api_key}

    for candidate in _suburb_candidates(sa2_name):
        slug = candidate.lower().replace(" ", "-")
        all_listings: list[dict] = []

        for page in range(1, max_pages + 1):
            url = f"{_BASE_URL}/v1/suburbs/{state}/{slug}/sold"
            params = {"page": page} if page > 1 else {}
            try:
                resp = client.get(url, headers=headers, params=params)
                report.api_calls += 1
            except httpx.RequestError as exc:
                logger.warning("Request error for %s: %s", candidate, exc)
                report.api_errors += 1
                break

            time.sleep(_REQUEST_DELAY)

            if resp.status_code == 404:
                break  # try next candidate
            if resp.status_code == 402:
                raise RuntimeError(
                    "PropRadar returned 402 Payment Required — subscription expired. "
                    "Reactivate at https://api.propradar.com.au/developers/dashboard."
                )
            if resp.status_code == 401:
                raise RuntimeError("PropRadar returned 401 Unauthorized — check PROPRADAR_API_KEY.")
            if resp.status_code == 429:
                logger.warning("Rate limited — sleeping 5s ...")
                time.sleep(5)
                report.api_errors += 1
                break
            if resp.status_code != 200:
                logger.warning("Unexpected %d for %s (page %d): %s", resp.status_code, candidate, page, resp.text[:200])
                report.api_errors += 1
                break

            data = resp.json()
            if page == 1:
                logger.debug("Raw PropRadar response for %s: %s", candidate, str(data)[:1000])

            page_listings = _extract_listings(data)
            if not page_listings:
                break
            all_listings.extend(page_listings)

            if not _has_next_page(data):
                break

        if all_listings:
            return all_listings

    return None


def _extract_listings(data: dict) -> list[dict]:
    """Pull the listings array out of whatever top-level key the API uses."""
    for key in ("results", "data", "properties", "listings", "sold"):
        if isinstance(data.get(key), list):
            return data[key]
    return []


def _has_next_page(data: dict) -> bool:
    """Best-effort pagination-continuation check across likely API shapes."""
    for key in ("has_more", "hasMore", "has_next", "hasNext"):
        if key in data:
            return bool(data[key])
    next_page = data.get("next_page") or data.get("nextPage")
    if next_page is not None:
        return bool(next_page)
    pagination = data.get("pagination") or data.get("meta")
    if isinstance(pagination, dict):
        page = pagination.get("page") or pagination.get("current_page")
        total_pages = pagination.get("total_pages") or pagination.get("totalPages")
        if page is not None and total_pages is not None:
            return page < total_pages
    return False


# ---------------------------------------------------------------------------
# Listing parsing
# ---------------------------------------------------------------------------

def _first(d: dict, *keys: str):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _parse_listing(listing: dict, sa2_code: str, state: str) -> PropertySale | None:
    """Convert one raw API listing into a PropertySale row, or None if it's
    missing the fields we need to display it meaningfully."""
    sold_price = _first(listing, "sold_price", "soldPrice", "price", "salePrice")
    sold_date = _first(listing, "sold_date", "soldDate", "date", "saleDate")
    if sold_price is None or sold_date is None:
        return None

    address = _first(listing, "address", "fullAddress", "full_address", "streetAddress")
    bedrooms = _first(listing, "bedrooms", "beds")
    bathrooms = _first(listing, "bathrooms", "baths")
    property_type = _first(listing, "property_type", "propertyType", "type")
    property_id = _first(listing, "property_id", "propertyId", "id")
    # Field name unverified — PropRadar's real shape hasn't been observed yet
    # (see module docstring). Common variants guessed defensively.
    land_size = _first(listing, "land_size_sqm", "landSize", "land_size", "lotSize", "lot_size")

    sold_date_str = str(sold_date)[:10]  # normalize to YYYY-MM-DD if a datetime string
    id_source = property_id or f"{address}|{sold_date_str}|{sold_price}"
    sale_id = hashlib.sha1(str(id_source).encode()).hexdigest()[:24]

    return PropertySale(
        id=sale_id,
        sa2_code=sa2_code,
        address=str(address) if address else None,
        state=state,
        bedrooms=int(bedrooms) if bedrooms is not None else None,
        bathrooms=int(bathrooms) if bathrooms is not None else None,
        property_type=str(property_type).lower() if property_type else None,
        land_size_sqm=int(land_size) if land_size is not None else None,
        sold_price=int(sold_price),
        sold_date=sold_date_str,
        source="propradar",
        fetched_at=datetime.now(timezone.utc),
    )
