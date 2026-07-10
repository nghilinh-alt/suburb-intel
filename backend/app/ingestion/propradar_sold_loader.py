"""PropRadar sold-listing loader.

Fetches recent sold-property records from PropRadar and upserts them onto
`property_sales`, tied to `sa2_code`.

SA2s are ABS statistical areas, not real suburbs — many combine two or more
actual gazetted suburbs (e.g. "Rochedale - Burbank", "Kedron - Gordon Park").
PropRadar's endpoint is suburb-scoped, so a combined SA2 needs a separate
query per real suburb it contains — querying just the first part (as an
earlier version of this loader did, treating the rest as a same-suburb
fallback name) silently misses every listing in the other part(s). See
`_split_suburb_parts`. Each returned listing's own `address` field is also
parsed for its real suburb_name/postcode — ground truth from the data
itself, independent of which query found it.

Endpoint used
─────────────
GET /v1/suburbs/{state}/{suburb}/sold?months=&limit=&offset=
Authentication: X-API-Key header.

Response shape — VERIFIED against a real 200 response (2026-07-08, QLD/rochedale)
──────────────────────────────────────────────────────────────────────────────
{
  "state": "QLD", "suburb": "rochedale",
  "query": {"months": 12, "limit": 20, "offset": 0, "cursor": null,
            "property_type": null, "min_beds": null, "max_beds": null,
            "min_price": null, "max_price": null},
  "sold": [
    {"property_id": "7dafef6d", "address": "32 Parolin Parade, Rochedale, QLD, 4123",
     "bedrooms": 6, "bathrooms": 5, "parking": 2, "property_type": "House",
     "sold_price": 2280000, "sold_date": "2026-06-29"},
    ...
  ],
  "pagination": {"offset": 0, "limit": 20, "next_offset": 20, "next_cursor": "..."}
}

No land size field anywhere in this response — `land_size_sqm` on
PropertySale will stay null via this loader (kept in the model/parsing in
case a future PropRadar API version adds it; see property_market_service.py's
land-size breakdown, which will just show empty until then).

Pagination is offset/limit-based (`pagination.next_offset`), NOT the `page`
param this loader originally guessed — that guess meant earlier runs never
actually paged past the first batch. `months` controls how far back "sold"
results go (API defaults to 12 if omitted); we request more by default so
the price-history chart ("up to 5 years") has real depth to show.

Quota
─────
Each page of each real suburb costs one call — a SA2 combining N real
suburbs (see `_split_suburb_parts`) costs up to N × max_pages, not just
max_pages, since each part is queried independently now. Always scope with
--state and prefer --suburb/--sa2-codes for a targeted pilot; `--max-pages`
defaults to a small safety cap so one run can't silently exhaust a
limited-tier quota. Page size is 50 (not the API's own default of 20) to
cover the same history in fewer calls.

A SA2 already fetched during the current calendar month is skipped
automatically (sold listings don't change retroactively, so a fetch from
earlier this month is still current) — pass --force to re-fetch anyway.
This means re-running the same command repeatedly costs nothing extra once
a SA2 is up to date for the month.

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.propradar_sold --state QLD --suburb Rochedale
    (API key is read from PROPRADAR_API_KEY env var)
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import PropertySale, SA2Region

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.propradar.com.au"
_REQUEST_DELAY = 0.5  # seconds between calls
_DEFAULT_MAX_PAGES = 3  # safety cap per suburb so one run can't blow a limited quota
_PAGE_SIZE = 50  # listings per call — larger than the API's own default (20) to cut call count
_DEFAULT_MONTHS = 60  # 5 years, to give the price-history chart real depth

# Strips an ABS state-name suffix off an SA2 name, e.g. "St Kilda (Vic.)" -> "St Kilda".
_STATE_SUFFIX_RE = re.compile(
    r"\s*\((Vic\.|NSW|ACT|SA|WA|QLD|NT|Tas\.)\)\s*$", re.IGNORECASE
)

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
    """True if this SA2 already has property_sales fetched during the
    current calendar month — the "only call PropRadar if this month's data
    isn't in our db" rule. Sold listings don't change retroactively, so a
    fetch from earlier this month is still current; a fetch from last month
    (or no fetch at all) isn't."""
    latest = db.query(func.max(PropertySale.fetched_at)).filter(PropertySale.sa2_code == sa2_code).scalar()
    if latest is None:
        return False
    now = datetime.now(timezone.utc)
    return latest.year == now.year and latest.month == now.month


def load_propradar_sold(
    db: Session,
    api_key: str,
    *,
    state: str | None = None,
    suburb: str | None = None,
    sa2_codes: list[str] | None = None,
    max_pages: int = _DEFAULT_MAX_PAGES,
    months: int = _DEFAULT_MONTHS,
    force: bool = False,
) -> PropRadarLoadReport:
    """Fetch recent sold listings for SA2s matching the given scope. Each
    SA2's own state (not a single passed-in state) is used per-request, so
    `sa2_codes` can span multiple states at once — e.g. a pilot sample
    across every capital city.

    Args:
        db:        Synchronous SQLAlchemy session.
        api_key:   PropRadar API key (starts with pr_live_ or pr_test_).
        state:     If set, only process SA2s in this state (e.g. "QLD").
        suburb:    If set, only process SA2s whose name matches this suburb
                   (case-insensitive substring) — use for a single-suburb pilot.
        sa2_codes: If set, process exactly these SA2 codes (ignores `suburb`'s
                   name-matching; can span multiple states) — use for a
                   specific pilot batch, e.g. a random sample across capitals.
        max_pages: Safety cap on pages fetched per suburb (quota protection).
        months:    How far back to request sold listings (API default is 12
                   if omitted; we default higher for price-history depth).
        force:     Skip the monthly-freshness check and re-fetch regardless.

    At least one of `state`, `suburb`, `sa2_codes` must be given — an
    entirely unscoped run would hit every SA2 in the country.
    """
    if not state and not suburb and not sa2_codes:
        raise ValueError("Must scope by at least one of state, suburb, or sa2_codes.")

    report = PropRadarLoadReport()

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

            listings = _fetch_for_sa2(client, api_key, pr_state, sa2_name, max_pages, months, report)

            if not listings:
                report.suburbs_not_found += 1
                continue

            report.suburbs_matched += 1
            for listing in listings:
                sale = _parse_listing(listing, sa2_code, sa2_state)
                if sale is None:
                    continue
                db.merge(sale)
                report.listings_upserted += 1

            db.commit()

    return report


# ---------------------------------------------------------------------------
# PropRadar API calls
# ---------------------------------------------------------------------------

def _split_suburb_parts(sa2_name: str) -> list[str]:
    """Split a combined SA2 name into each real suburb it represents, e.g.
    "Rochedale - Burbank" -> ["Rochedale", "Burbank"]. PropRadar is purely
    suburb-scoped, so each part is queried independently — each part is a
    genuinely different suburb we'd otherwise silently never query.

    Note this over-queries for compass-qualifier SA2 names that aren't
    really two suburbs (e.g. "Melbourne CBD - West") — "West" alone will
    just 404 harmlessly, costing one wasted call rather than returning wrong
    data, so it's not worth the complexity of trying to distinguish the two
    patterns from the name alone.
    """
    name = _STATE_SUFFIX_RE.sub("", sa2_name).strip()
    parts = [p.strip() for p in name.split(" - ") if p.strip()]
    return parts or [name]


def _fetch_for_sa2(
    client: httpx.Client,
    api_key: str,
    state: str,
    sa2_name: str,
    max_pages: int,
    months: int,
    report: PropRadarLoadReport,
) -> list[dict]:
    """Fetch sold listings across every real suburb within this SA2 —
    accumulates results from all parts rather than stopping at the first
    one that resolves."""
    all_listings: list[dict] = []
    for suburb_name in _split_suburb_parts(sa2_name):
        all_listings.extend(_fetch_all_pages_for_name(client, api_key, state, suburb_name, max_pages, months, report))
    return all_listings


def _fetch_all_pages_for_name(
    client: httpx.Client,
    api_key: str,
    state: str,
    suburb_name: str,
    max_pages: int,
    months: int,
    report: PropRadarLoadReport,
) -> list[dict]:
    """Page through sold listings for one exact suburb name via offset/limit
    (bounded by max_pages). Returns [] if the suburb doesn't resolve (404)."""
    headers = {"X-API-Key": api_key}
    slug = suburb_name.lower().replace(" ", "-")
    all_listings: list[dict] = []
    offset = 0

    for page in range(1, max_pages + 1):
        url = f"{_BASE_URL}/v1/suburbs/{state}/{slug}/sold"
        params = {"months": months, "limit": _PAGE_SIZE, "offset": offset}
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

        page_listings = data.get("sold") or []
        if not page_listings:
            break
        all_listings.extend(page_listings)

        next_offset = _next_offset(data)
        if next_offset is None:
            break
        offset = next_offset

    return all_listings


def _next_offset(data: dict) -> int | None:
    """Read the next page's offset from `pagination.next_offset`, or None if
    there isn't a further page."""
    pagination = data.get("pagination")
    if not isinstance(pagination, dict):
        return None
    return pagination.get("next_offset")


# ---------------------------------------------------------------------------
# Listing parsing
# ---------------------------------------------------------------------------

def _first(d: dict, *keys: str):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


_POSTCODE_RE = re.compile(r"^\d{4}$")


def _parse_address(address: str) -> tuple[str | None, str | None]:
    """Extract (suburb_name, postcode) from a PropRadar address string, e.g.
    "32 Parolin Parade, Rochedale, QLD, 4123" -> ("Rochedale", "4123").
    Ground truth from the listing itself — independent of which suburb-name
    query found it, so it's correct even if PropRadar's own suburb matching
    is fuzzier than an exact name (e.g. returns a listing in a neighbouring
    suburb for a query at its edge)."""
    parts = [p.strip() for p in address.split(",")]
    if len(parts) < 4:
        return None, None
    suburb, postcode = parts[-3], parts[-1]
    if not _POSTCODE_RE.match(postcode):
        return None, None
    # PropRadar's own address casing is inconsistent (seen "Cleveland" and
    # "CLEVELAND" for the same real suburb) — normalize ALL-CAPS only, so a
    # correctly-cased name (incl. ones title-casing would mangle, e.g.
    # "McMahons Point") isn't touched.
    if suburb.isupper():
        suburb = suburb.title()
    return suburb, postcode


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
    parking = _first(listing, "parking", "parkingSpaces", "carSpaces")
    property_type = _first(listing, "property_type", "propertyType", "type")
    property_id = _first(listing, "property_id", "propertyId", "id")
    # Verified: this endpoint doesn't return land size at all (see module
    # docstring) — always None via this loader. Kept in case a future
    # PropRadar API version adds it.
    land_size = _first(listing, "land_size_sqm", "landSize", "land_size", "lotSize", "lot_size")

    sold_date_str = str(sold_date)[:10]  # normalize to YYYY-MM-DD if a datetime string
    id_source = property_id or f"{address}|{sold_date_str}|{sold_price}"
    sale_id = hashlib.sha1(str(id_source).encode()).hexdigest()[:24]

    suburb_name, postcode = _parse_address(str(address)) if address else (None, None)

    return PropertySale(
        id=sale_id,
        sa2_code=sa2_code,
        address=str(address) if address else None,
        suburb_name=suburb_name,
        state=state,
        postcode=postcode,
        bedrooms=int(bedrooms) if bedrooms is not None else None,
        bathrooms=int(bathrooms) if bathrooms is not None else None,
        parking=int(parking) if parking is not None else None,
        property_type=str(property_type).lower() if property_type else None,
        land_size_sqm=int(land_size) if land_size is not None else None,
        sold_price=int(sold_price),
        sold_date=sold_date_str,
        source="propradar",
        fetched_at=datetime.now(timezone.utc),
    )
