"""PropRadar current-listings loader.

Fetches currently-for-sale property listings from PropRadar and upserts them
onto `current_listings`, tied to `sa2_code`. Same SA2-to-real-suburb split as
propradar_sold_loader.py (an SA2 like "Rochedale - Burbank" needs a query per
real suburb) — reuses `_split_suburb_parts`/`_STATE_MAP`/`_parse_address`/
`_next_offset` from that module rather than duplicating them.

Endpoint used
─────────────
GET /v1/suburbs/{state}/{suburb}/listings?limit=&offset=
Authentication: X-API-Key header. Ungated at our "hobby" plan tier.

Response shape — VERIFIED against a real 200 response (2026-07-10, QLD/cleveland)
──────────────────────────────────────────────────────────────────────────────
{
  "state": "QLD", "suburb": "cleveland",
  "query": {"limit": 20, "offset": 0, "cursor": null, "property_type": null,
            "min_beds": null, "max_beds": null, "min_price": null, "max_price": null,
            "min_days_on_market": null, "max_days_on_market": null},
  "listings": [
    {"property_id": "170f9844", "address": "4 Capricorn Drive, Cleveland, QLD, 4163",
     "bedrooms": 4, "bathrooms": 2, "parking": 2, "property_type": "House",
     "asking_price_low": null, "asking_price_high": null,
     "sale_type": "Private Sale", "added_at": "2026-07-02T16:53:28.000Z"},
    ...
  ],
  "pagination": {"offset": 0, "limit": 20, "next_offset": 20, "next_cursor": "..."}
}

Unlike /sold, there's no `months` query param at all (a "currently for sale"
view has no time window to bound) and no land-size field. `asking_price_low`/
`asking_price_high` are both null for a large share of listings (price
withheld / "contact agent") — equal to each other for a fixed-price listing.
No raw `days_on_market` number in the body (only `min_days_on_market`/
`max_days_on_market` as query *filters*, meaning PropRadar computes it
server-side but doesn't expose it at this plan tier) — `added_at` is stored
as `listed_date` instead so a reader can derive it.

Pagination is the same offset/limit shape as /sold (`pagination.next_offset`)
— reuses `_next_offset` directly. Unlike /sold, this endpoint silently caps
at 20 results per page regardless of the requested `limit` (confirmed live —
passing limit=50 still returns 20 and echoes back `"limit": 20` in the
response's own `pagination` object), so there's no cheaper-call-count trick
available here; `_PAGE_SIZE` is still passed for forward-compatibility if
that cap is ever lifted.

Quota
─────
Each page of each real suburb costs one call, same accounting as
propradar_sold_loader.py — always scope with --state and prefer
--suburb/--sa2-codes for a targeted pilot; --max-pages defaults to a small
safety cap.

A SA2 already fetched during the current calendar month is skipped
automatically (mirrors propradar_sold_loader.py's freshness check) — pass
--force to re-fetch anyway. Unlike sold listings (immutable historical
facts), a still-listed property's price/details CAN change between fetches;
re-fetching upserts (via `id` = hash of PropRadar's `property_id`) rather
than accumulating duplicates.

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.current_listings --state QLD --suburb Cleveland
    (API key is read from PROPRADAR_API_KEY env var)
"""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import CurrentListing, SA2Region
from app.ingestion.propradar_sold_loader import (
    _STATE_MAP,
    _next_offset,
    _parse_address,
    _split_suburb_parts,
)

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.propradar.com.au"
_REQUEST_DELAY = 0.5  # seconds between calls
_DEFAULT_MAX_PAGES = 3  # safety cap per suburb so one run can't blow a limited quota
_PAGE_SIZE = 50  # listings per call — larger than the API's own default (20) to cut call count


@dataclass
class CurrentListingsLoadReport:
    suburbs_processed: int = 0
    suburbs_matched: int = 0
    suburbs_not_found: int = 0
    suburbs_skipped_fresh: int = 0
    listings_upserted: int = 0
    api_calls: int = 0
    api_errors: int = 0

    def __str__(self) -> str:
        return (
            f"Suburbs processed: {self.suburbs_processed} | "
            f"Matched: {self.suburbs_matched} | "
            f"Not found: {self.suburbs_not_found} | "
            f"Skipped (already fresh this month): {self.suburbs_skipped_fresh} | "
            f"Listings upserted: {self.listings_upserted} | "
            f"API calls used: {self.api_calls} | "
            f"API errors: {self.api_errors}"
        )


def _fetched_this_month(db: Session, sa2_code: str) -> bool:
    """True if this SA2 already has current_listings fetched during the
    current calendar month — same freshness rule as propradar_sold_loader.py."""
    latest = db.query(func.max(CurrentListing.fetched_at)).filter(CurrentListing.sa2_code == sa2_code).scalar()
    if latest is None:
        return False
    now = datetime.now(timezone.utc)
    return latest.year == now.year and latest.month == now.month


def load_current_listings(
    db: Session,
    api_key: str,
    *,
    state: str | None = None,
    suburb: str | None = None,
    sa2_codes: list[str] | None = None,
    max_pages: int = _DEFAULT_MAX_PAGES,
    force: bool = False,
) -> CurrentListingsLoadReport:
    """Fetch current for-sale listings for SA2s matching the given scope.

    Args:
        db:        Synchronous SQLAlchemy session.
        api_key:   PropRadar API key.
        state:     If set, only process SA2s in this state (e.g. "QLD").
        suburb:    If set, only process SA2s whose name matches this suburb
                   (case-insensitive substring) — use for a single-suburb pilot.
        sa2_codes: If set, process exactly these SA2 codes (can span states).
        max_pages: Safety cap on pages fetched per suburb (quota protection).
        force:     Skip the monthly-freshness check and re-fetch regardless.

    At least one of `state`, `suburb`, `sa2_codes` must be given — an
    entirely unscoped run would hit every SA2 in the country.
    """
    if not state and not suburb and not sa2_codes:
        raise ValueError("Must scope by at least one of state, suburb, or sa2_codes.")

    report = CurrentListingsLoadReport()

    q = db.query(SA2Region.sa2_code, SA2Region.sa2_name, SA2Region.state)
    if state:
        q = q.filter(SA2Region.state == state)
    if sa2_codes:
        q = q.filter(SA2Region.sa2_code.in_(sa2_codes))
    elif suburb:
        q = q.filter(SA2Region.sa2_name.ilike(f"%{suburb}%"))
    sa2_rows = q.all()
    logger.info("Processing %d SA2s ...", len(sa2_rows))

    with httpx.Client(timeout=15.0) as client:
        for sa2_code, sa2_name, sa2_state in sa2_rows:
            report.suburbs_processed += 1

            pr_state = _STATE_MAP.get(sa2_state)
            if pr_state is None:
                logger.warning("Unknown state %s for SA2 %s — skipping", sa2_state, sa2_code)
                report.suburbs_not_found += 1
                continue

            if not force and _fetched_this_month(db, sa2_code):
                logger.info("Skipping %s (%s) — already fetched this month", sa2_name, sa2_code)
                report.suburbs_skipped_fresh += 1
                continue

            listings = _fetch_for_sa2(client, api_key, pr_state, sa2_name, max_pages, report)

            if not listings:
                report.suburbs_not_found += 1
                continue

            report.suburbs_matched += 1
            for listing in listings:
                current = _parse_listing(listing, sa2_code, sa2_state)
                if current is None:
                    continue
                db.merge(current)
                report.listings_upserted += 1

            db.commit()

    return report


# ---------------------------------------------------------------------------
# PropRadar API calls
# ---------------------------------------------------------------------------

def _fetch_for_sa2(
    client: httpx.Client,
    api_key: str,
    state: str,
    sa2_name: str,
    max_pages: int,
    report: CurrentListingsLoadReport,
) -> list[dict]:
    """Fetch current listings across every real suburb within this SA2 —
    accumulates results from all parts rather than stopping at the first
    one that resolves."""
    all_listings: list[dict] = []
    for suburb_name in _split_suburb_parts(sa2_name):
        all_listings.extend(_fetch_all_pages_for_name(client, api_key, state, suburb_name, max_pages, report))
    return all_listings


def _fetch_all_pages_for_name(
    client: httpx.Client,
    api_key: str,
    state: str,
    suburb_name: str,
    max_pages: int,
    report: CurrentListingsLoadReport,
) -> list[dict]:
    """Page through current listings for one exact suburb name via
    offset/limit (bounded by max_pages). Returns [] if the suburb doesn't
    resolve (404)."""
    headers = {"X-API-Key": api_key}
    slug = suburb_name.lower().replace(" ", "-")
    all_listings: list[dict] = []
    offset = 0

    for page in range(1, max_pages + 1):
        url = f"{_BASE_URL}/v1/suburbs/{state}/{slug}/listings"
        params = {"limit": _PAGE_SIZE, "offset": offset}
        try:
            resp = client.get(url, headers=headers, params=params)
            report.api_calls += 1
        except httpx.RequestError as exc:
            logger.warning("Request error for %s: %s", suburb_name, exc)
            report.api_errors += 1
            break

        time.sleep(_REQUEST_DELAY)

        if resp.status_code == 404:
            break  # not a real suburb (or no PropRadar coverage) — not an error
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
            logger.warning("Unexpected %d for %s (page %d): %s", resp.status_code, suburb_name, page, resp.text[:200])
            report.api_errors += 1
            break

        data = resp.json()
        if page == 1:
            logger.debug("Raw PropRadar response for %s: %s", suburb_name, str(data)[:1000])

        page_listings = data.get("listings") or []
        if not page_listings:
            break
        all_listings.extend(page_listings)

        next_offset = _next_offset(data)
        if next_offset is None:
            break
        offset = next_offset

    return all_listings


# ---------------------------------------------------------------------------
# Listing parsing
# ---------------------------------------------------------------------------

def _first(d: dict, *keys: str):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _parse_listing(listing: dict, sa2_code: str, state: str) -> CurrentListing | None:
    """Convert one raw API listing into a CurrentListing row, or None if it's
    missing the address we need to display it meaningfully. Price is
    frequently absent (price-on-application) so it isn't a requirement, unlike
    /sold's sold_price/sold_date."""
    address = _first(listing, "address", "fullAddress", "full_address", "streetAddress")
    if address is None:
        return None

    property_id = _first(listing, "property_id", "propertyId", "id")
    bedrooms = _first(listing, "bedrooms", "beds")
    bathrooms = _first(listing, "bathrooms", "baths")
    parking = _first(listing, "parking", "parkingSpaces", "carSpaces")
    property_type = _first(listing, "property_type", "propertyType", "type")
    asking_price_low = _first(listing, "asking_price_low", "askingPriceLow", "price_low")
    asking_price_high = _first(listing, "asking_price_high", "askingPriceHigh", "price_high")
    sale_type = _first(listing, "sale_type", "saleType")
    added_at = _first(listing, "added_at", "addedAt", "listed_date", "listedDate")

    listed_date = str(added_at)[:10] if added_at else None  # normalize to YYYY-MM-DD

    id_source = property_id or f"{address}|{listed_date}"
    listing_id = hashlib.sha1(str(id_source).encode()).hexdigest()[:24]

    suburb_name, postcode = _parse_address(str(address))

    return CurrentListing(
        id=listing_id,
        sa2_code=sa2_code,
        address=str(address),
        suburb_name=suburb_name,
        state=state,
        postcode=postcode,
        bedrooms=int(bedrooms) if bedrooms is not None else None,
        bathrooms=int(bathrooms) if bathrooms is not None else None,
        parking=int(parking) if parking is not None else None,
        property_type=str(property_type).lower() if property_type else None,
        asking_price_low=int(asking_price_low) if asking_price_low is not None else None,
        asking_price_high=int(asking_price_high) if asking_price_high is not None else None,
        sale_type=str(sale_type) if sale_type else None,
        listed_date=listed_date,
        source="propradar",
        fetched_at=datetime.now(timezone.utc),
    )
