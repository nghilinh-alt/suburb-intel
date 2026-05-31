"""Foursquare Places API v3 helper — on-demand place count fetcher.

Architecture: on-demand with 30-day cache (suburb_place_cache table).
On first request for a suburb, centroids are geocoded and Foursquare is
queried for each category. Results are cached for 30 days, after which
a fresh fetch is made on the next request.

This keeps API usage near-zero on the free tier (~100k req/month) — only
suburbs that users actually view are ever queried.

Setup:
    1. Go to https://developer.foursquare.com/
    2. Create a project and copy the API key
    3. Add to backend/.env: FOURSQUARE_API_KEY=fsq3XXXXXXXXXXXX

Categories queried (Foursquare v3 category IDs):
    cafes        → 13032 (Coffee Shop), 13033 (Café)
    restaurants  → 13065 (Restaurant) — sit-down only
    fast_food    → 13145 (Fast Food Restaurant)
    supermarkets → 17145 (Supermarket), 17069 (Grocery Store)
    parks        → 16032 (Park), 16047 (Playground)
    gyms         → 18011 (Gym/Fitness Center)
    pharmacies   → 17114 (Pharmacy)
    hospitals    → 15014 (Hospital)
    gp_clinics   → 15039 (Doctor's Office), 15058 (Medical Center)
    hardware     → 11091 (Hardware Store)
    petrol       → 19046 (Gas Station/Petrol Station)
    post_office  → 12114 (Post Office)
    banks        → 11100 (Bank)
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

_FSQ_NEARBY = "https://api.foursquare.com/v3/places/nearby"
_CACHE_DAYS = 30
_REQUEST_DELAY = 0.2   # seconds between category queries (rate limiting)

# Category name → Foursquare v3 category ID(s)
CATEGORIES: dict[str, list[str]] = {
    "cafes":        ["13032", "13033"],
    "restaurants":  ["13065"],
    "fast_food":    ["13145"],
    "supermarkets": ["17145", "17069"],
    "parks":        ["16032", "16047"],
    "gyms":         ["18011"],
    "pharmacies":   ["17114"],
    "hospitals":    ["15014"],
    "gp_clinics":   ["15039", "15058"],
    "hardware":     ["11091"],
    "petrol":       ["19046"],
    "post_office":  ["12114"],
    "banks":        ["11100"],
}


def _fsq_count(api_key: str, lat: float, lon: float, radius_m: int, cat_ids: list[str]) -> int:
    """Return count of Foursquare places matching category IDs near lat/lon."""
    session = requests.Session()
    session.verify = False
    session.headers.update({
        "Authorization": api_key,
        "Accept": "application/json",
    })

    total = 0
    offset = 0
    page_size = 50   # FSQ max per request

    while True:
        params: dict[str, Any] = {
            "ll":         f"{lat},{lon}",
            "radius":     radius_m,
            "categories": ",".join(cat_ids),
            "limit":      page_size,
            "fields":     "fsq_id",   # minimal fields — we only need the count
        }
        if offset > 0:
            params["offset"] = offset

        try:
            resp = session.get(_FSQ_NEARBY, params=params, timeout=15)
            if resp.status_code == 401:
                raise ValueError("Invalid Foursquare API key — check FOURSQUARE_API_KEY in .env")
            if resp.status_code == 429:
                logger.warning("Foursquare rate limit hit, sleeping 60s ...")
                time.sleep(60)
                continue
            resp.raise_for_status()
            data = resp.json()
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("Foursquare request failed: %s", exc)
            return total

        results = data.get("results", [])
        total += len(results)

        # FSQ returns up to `limit` results; if we got a full page, there may be more
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
    """Fetch place counts for all categories for one suburb centroid.

    Returns: {category_name: count}
    """
    counts: dict[str, int] = {}
    for cat_name, cat_ids in CATEGORIES.items():
        count = _fsq_count(api_key, lat, lon, radius_m, cat_ids)
        counts[cat_name] = count
        logger.debug("  %s/%s: %d", suburb_id, cat_name, count)
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
    """Return cached place counts, refreshing from Foursquare if stale (>30 days).

    Returns None if no API key is configured.
    """
    from app.db.models import SuburbPlaceCache, Base
    from app.db.session import sync_engine
    Base.metadata.create_all(bind=sync_engine)

    if not api_key:
        return None

    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=_CACHE_DAYS)

    existing = db.get(SuburbPlaceCache, suburb_id)
    if existing and existing.fetched_at and existing.fetched_at >= cutoff:
        return existing.data_json or {}

    # Fetch fresh
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
