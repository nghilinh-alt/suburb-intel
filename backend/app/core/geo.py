"""Geographic helpers: SA2 centroid extraction and distance-to-CBD calculation.

CBD coordinates are hardcoded per capital city — sufficient for the
distance-to-CBD metric without pulling in a geocoding API/dependency.
"""

from __future__ import annotations

import json
import math

from shapely.geometry import shape

# State code -> (lat, lon) of that state/territory's capital-city CBD.
CBD_COORDS: dict[str, tuple[float, float]] = {
    "NSW": (-33.8688, 151.2093),   # Sydney
    "VIC": (-37.8136, 144.9631),   # Melbourne
    "QLD": (-27.4698, 153.0251),   # Brisbane
    "WA":  (-31.9505, 115.8605),   # Perth
    "SA":  (-34.9285, 138.6007),   # Adelaide
    "TAS": (-42.8821, 147.3272),   # Hobart
    "ACT": (-35.2809, 149.1300),   # Canberra
    "NT":  (-12.4634, 130.8456),   # Darwin
}

_EARTH_RADIUS_KM = 6371.0


def centroid_from_geojson(geojson_text: str) -> tuple[float, float] | None:
    """Return the (lat, lon) centroid of a GeoJSON polygon/multipolygon string.

    Returns None if the input is empty or unparseable.
    """
    if not geojson_text:
        return None
    try:
        geom = shape(json.loads(geojson_text))
    except (ValueError, TypeError):
        return None
    centroid = geom.centroid
    return centroid.y, centroid.x


def distance_to_cbd_km(sa2_centroid: tuple[float, float], state: str) -> float | None:
    """Haversine distance in km from an SA2 centroid to its state's capital CBD.

    Returns None if the state has no known CBD coordinate (e.g. external territories).
    """
    cbd = CBD_COORDS.get(state)
    if cbd is None:
        return None
    return _haversine_km(sa2_centroid, cbd)


def _haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1 = a
    lat2, lon2 = b
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    h = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_KM * math.asin(math.sqrt(h))
