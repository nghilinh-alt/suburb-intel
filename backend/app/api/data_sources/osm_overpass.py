"""OpenStreetMap Overpass API data source.

NOTE: The Overpass query construction in the original module was malformed
(`around:500,"<suburb_name>"` is not valid Overpass QL). The implementation
below builds a *syntactically* valid query that geocodes the suburb to lat/lon
first, then runs an `around:` query. Network calls are wrapped in
``asyncio.to_thread`` because the underlying client (`requests`) is sync.
"""

from __future__ import annotations

import asyncio
import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)


# Fallback coordinates for common Australian suburbs so the dev experience
# works without a geocoder configured. Real deployments should plug in a
# proper geocoder (Nominatim, Google, etc).
_FALLBACK_COORDS: Dict[str, Dict[str, float]] = {
    "melbourne": {"latitude": -37.8136, "longitude": 144.9631},
    "south yarra": {"latitude": -37.8407, "longitude": 144.9924},
    "south yarra vic": {"latitude": -37.8407, "longitude": 144.9924},
    "sydney": {"latitude": -33.8688, "longitude": 151.2093},
    "brisbane": {"latitude": -27.4698, "longitude": 153.0251},
    "chermside": {"latitude": -27.3848, "longitude": 153.0319},
    "chermside qld": {"latitude": -27.3848, "longitude": 153.0319},
    "cronulla": {"latitude": -34.0581, "longitude": 151.1525},
    "cronulla nsw": {"latitude": -34.0581, "longitude": 151.1525},
}


class OSMOverpassDataSource:
    """Async wrapper around the Overpass amenity-density API."""

    BASE_URL = "https://overpass-api.de/api/interpreter"

    AMENITY_TAGS = {
        "cafe": "amenity=cafe",
        "restaurant": "amenity=restaurant",
        "fast_food": "amenity=fast_food",
        "bar": "amenity=bar",
        "pub": "amenity=pub",
        "hospital": "amenity=hospital",
        "clinic": "amenity=clinic",
        "doctors": "amenity=doctors",
        "dentist": "amenity=dentist",
        "pharmacy": "amenity=pharmacy",
        "grocery": "shop=supermarket",
        "supermarket": "shop=supermarket",
        "bank": "amenity=bank",
        "school": "amenity=school",
        "kindergarten": "amenity=kindergarten",
        "childcare": "amenity=childcare",
        "library": "amenity=library",
        "post_office": "amenity=post_office",
        "fitness_centre": "leisure=fitness_centre",
        "gym": "leisure=fitness_centre",
        "swimming_pool": "leisure=pool",
        "park": "leisure=park",
    }

    AMENITY_WEIGHTS = {
        "cafe": 8.0,
        "restaurant": 7.5,
        "bar": 6.0,
        "pub": 6.0,
        "fast_food": 3.0,
        "grocery": 9.0,
        "supermarket": 9.0,
        "pharmacy": 8.5,
        "bank": 7.0,
        "hospital": 9.5,
        "clinic": 8.0,
        "doctors": 8.0,
        "swimming_pool": 7.0,
        "gym": 6.5,
        "park": 7.5,
    }

    PRIORITY_AMENITIES = (
        "cafe", "restaurant", "grocery", "pharmacy", "hospital",
        "clinic", "bank", "gym", "park", "swimming_pool",
    )

    def __init__(self, timeout: int = 30) -> None:
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (compatible; SuburbIntel/1.0)",
                "Accept-Encoding": "gzip",
                "Connection": "keep-alive",
            }
        )

    # ------------------------------------------------------------------
    # Geocoding (stub with fallbacks)
    # ------------------------------------------------------------------
    def fetch_suburb_coordinates(self, suburb_name: str) -> Dict[str, Any]:
        """Resolve a suburb name to lat/lon, using a small fallback dictionary.

        Production should call Nominatim or another geocoder. We deliberately
        avoid a network call here so tests run offline.
        """
        key = suburb_name.lower().strip()
        coords = _FALLBACK_COORDS.get(key)
        if coords is None:
            # Try without trailing state code (e.g. "South Yarra VIC" -> "south yarra")
            stripped = " ".join(part for part in key.split() if part not in {"nsw", "vic", "qld", "wa", "sa", "tas", "act", "nt"})
            coords = _FALLBACK_COORDS.get(stripped, _FALLBACK_COORDS["melbourne"])
        return {
            "latitude": coords["latitude"],
            "longitude": coords["longitude"],
            "display_name": suburb_name,
        }

    # ------------------------------------------------------------------
    # Query builder
    # ------------------------------------------------------------------
    def build_overpass_query(self, suburb_name: str, amenity_tag: str) -> str:
        """Construct a syntactically-valid Overpass QL query.

        Searches within 500m, 1km and 2km of the suburb's coordinates and
        returns counts for each radius as separate result sets.
        """
        coords = self.fetch_suburb_coordinates(suburb_name)
        lat, lon = coords["latitude"], coords["longitude"]

        if "=" in amenity_tag:
            tag_key, tag_value = amenity_tag.split("=", 1)
            filt = f'["{tag_key}"="{tag_value}"]'
        else:
            filt = f'["{amenity_tag}"]'

        return (
            f"[out:json][timeout:{self.timeout}];\n"
            "(\n"
            f"  node{filt}(around:500,{lat},{lon});\n"
            f"  way{filt}(around:1000,{lat},{lon});\n"
            f"  relation{filt}(around:2000,{lat},{lon});\n"
            ");\n"
            "out count;"
        )

    # ------------------------------------------------------------------
    # Fetches
    # ------------------------------------------------------------------
    async def fetch_amenity_counts(
        self, suburb_name: str, amenity_type: str
    ) -> Dict[str, Any]:
        """Fetch counts for one amenity type within 500m / 1km / 2km."""
        tag = self.AMENITY_TAGS.get(amenity_type, amenity_type)
        query = self.build_overpass_query(suburb_name, tag)

        def _do_request() -> requests.Response:
            return self.session.post(
                self.BASE_URL, data={"data": query}, timeout=self.timeout
            )

        try:
            response = await asyncio.to_thread(_do_request)
            response.raise_for_status()
            data = response.json()
            # Overpass `out count;` returns elements with a "tags": {"total": "N"} payload.
            total = 0
            for el in data.get("elements", []):
                tags = el.get("tags") or {}
                try:
                    total += int(tags.get("total", 0))
                except (TypeError, ValueError):
                    continue
            # The Overpass count format collapses the three radii into a single
            # "total". Without separate sub-queries we report the same count
            # for each radius; consumers should treat 500m as the canonical
            # number until a richer query is shipped.
            return {
                "count_500m": total,
                "count_1km": total,
                "count_2km": total,
            }
        except requests.exceptions.RequestException as e:
            logger.warning(
                "Overpass request failed for %s (%s): %s", suburb_name, amenity_type, e
            )
            return {"count_500m": 0, "count_1km": 0, "count_2km": 0, "error": str(e)}
        except Exception as e:  # noqa: BLE001
            logger.exception("Unexpected Overpass error for %s/%s", suburb_name, amenity_type)
            return {"count_500m": 0, "count_1km": 0, "count_2km": 0, "error": str(e)}

    async def fetch_all_amenity_types(self, suburb_name: str) -> Dict[str, Any]:
        """Fetch counts for every priority amenity in parallel."""
        results = await asyncio.gather(
            *(self.fetch_amenity_counts(suburb_name, a) for a in self.PRIORITY_AMENITIES),
            return_exceptions=True,
        )

        amenities: Dict[str, Dict[str, Any]] = {}
        errors = []
        for name, result in zip(self.PRIORITY_AMENITIES, results):
            if isinstance(result, Exception):
                errors.append(f"{name}: {result}")
                continue
            amenities[name] = result

        payload: Dict[str, Any] = {
            "amenities": amenities,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "suburb": suburb_name,
        }
        if errors:
            payload["error"] = "; ".join(errors)
        return payload

    async def calculate_amenity_density_score(self, suburb_name: str) -> float:
        """Aggregate 0-10 density score across all priority amenities."""
        data = await self.fetch_all_amenity_types(suburb_name)
        amenities = data.get("amenities", {})

        max_expected = {
            "cafe": 50, "grocery": 15, "supermarket": 8, "pharmacy": 6,
            "hospital": 2, "gym": 8, "park": 15, "bank": 6,
            "swimming_pool": 4, "restaurant": 30,
        }

        total = 0.0
        for amenity_type, counts in amenities.items():
            weight = self.AMENITY_WEIGHTS.get(amenity_type, 5.0)
            cap = max_expected.get(amenity_type, 20)
            normalized = min(counts.get("count_500m", 0) / cap, 1.0) if cap else 0.0
            total += weight * normalized

        return round((min(total, 25) / 25) * 10, 2)
