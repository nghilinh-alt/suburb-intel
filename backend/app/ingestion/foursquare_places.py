"""Foursquare Places API (new 2025 endpoint) — on-demand place count fetcher.

New API discovered via Foursquare's MCP server source (github.com/foursquare/foursquare-places-mcp):
  Base URL: https://places-api.foursquare.com
  Endpoint: /places/search
  Auth:     Authorization: Bearer {api_key}
  Header:   X-Places-Api-Version: 2025-02-05
  Params:   query (text), ll (lat,lon), radius (metres), limit

Architecture: on-demand with 30-day cache (suburb_place_cache table).
Only suburbs that users view are ever queried — keeps API usage near-zero.

Setup:
    Add to backend/.env: FOURSQUARE_API_KEY=fsq3XXXXXXXXXXXX
    Register at https://developer.foursquare.com/ → Create project → API Keys
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

_FSQ_BASE    = "https://places-api.foursquare.com"
_FSQ_SEARCH  = f"{_FSQ_BASE}/places/search"
_FSQ_VERSION = "2025-02-05"
_CACHE_DAYS  = 30
_REQUEST_DELAY = 0.3   # seconds between queries

# Category name → search query string for the new FSQ text-based search
CATEGORIES: dict[str, str] = {
    "cafes":        "cafe coffee",
    "restaurants":  "restaurant",
    "fast_food":    "fast food",
    "supermarkets": "supermarket grocery",
    "parks":        "park",
    "gyms":         "gym fitness",
    "pharmacies":   "pharmacy",
    "hospitals":    "hospital",
    "gp_clinics":   "doctor medical centre clinic",
    "hardware":     "hardware store",
    "petrol":       "petrol station fuel",
    "post_office":  "post office",
    "banks":        "bank",
}


def _fsq_count(api_key: str, lat: float, lon: float, radius_m: int, query: str) -> int:
    """Return count of Foursquare places matching query near lat/lon."""
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "X-Places-Api-Version": _FSQ_VERSION,
    })

    total = 0
    offset = 0
    page_size = 50

    while True:
        params: dict[str, Any] = {
            "query":  query,
            "ll":     f"{lat},{lon}",
            "radius": radius_m,
            "limit":  page_size,
            "fields": "fsq_id",
        }
        if offset > 0:
            params["offset"] = offset

        try:
            resp = session.get(_FSQ_SEARCH, params=params, timeout=15)
            if resp.status_code == 401:
                raise ValueError("Invalid Foursquare API key — check FOURSQUARE_API_KEY in .env")
            if resp.status_code == 429:
                logger.warning("Foursquare rate limit hit, sleeping 60s ...")
                time.sleep(60)
                continue
            if resp.status_code >= 400:
                logger.warning("Foursquare error %d for query '%s': %s",
                               resp.status_code, query, resp.text[:200])
                return total
            data = resp.json()
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("Foursquare request failed for '%s': %s", query, exc)
            return total

        results = data.get("results", [])
        total += len(results)

        if len(results) < page_size:
            break
        offset += page_size
        time.sleep(_REQUEST_DELAY)

    return total


def fetch_suburb_places(
    suburb_id: str,
    lat: float,
    lon: float,
    radius_m: int,
    api_key: str,
) -> dict[str, int]:
    """Fetch place counts for all categories for one suburb centroid."""
    counts: dict[str, int] = {}
    for cat_name, query in CATEGORIES.items():
        count = _fsq_count(api_key, lat, lon, radius_m, query)
        counts[cat_name] = count
        logger.debug("  %s/%s ('%s'): %d", suburb_id, cat_name, query, count)
        time.sleep(_REQUEST_DELAY)
    return counts


def get_or_fetch(
    suburb_id: str,
    lat: float,
    lon: float,
    radius_m: int,
    api_key: str,
    db,
) -> dict[str, int] | None:
    """Return cached place counts, refreshing from Foursquare if stale (>30 days)."""
    from app.db.models import SuburbPlaceCache, Base
    from app.db.session import sync_engine
    Base.metadata.create_all(bind=sync_engine)

    if not api_key:
        return None

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=_CACHE_DAYS)
    existing = db.get(SuburbPlaceCache, suburb_id)
    if existing and existing.fetched_at and existing.fetched_at >= cutoff:
        return existing.data_json or {}

    logger.info("Fetching Foursquare places for %s (lat=%.4f, lon=%.4f, r=%dm) ...",
                suburb_id, lat, lon, radius_m)
    try:
        counts = fetch_suburb_places(suburb_id, lat, lon, radius_m, api_key)
    except ValueError as exc:
        logger.error("%s", exc)
        return None
    except Exception as exc:
        logger.warning("Foursquare fetch failed for %s: %s", suburb_id, exc)
        return None

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if existing:
        existing.data_json  = counts
        existing.lat        = lat
        existing.lon        = lon
        existing.radius_m   = radius_m
        existing.fetched_at = now
    else:
        db.add(SuburbPlaceCache(
            suburb_id  = suburb_id,
            source     = "foursquare_v3",
            data_json  = counts,
            lat        = lat,
            lon        = lon,
            radius_m   = radius_m,
            fetched_at = now,
        ))
    db.commit()
    return counts
