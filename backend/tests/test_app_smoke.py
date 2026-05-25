"""Smoke tests: app boots, root + health respond, all expected routes register."""

from __future__ import annotations

import pytest


def test_root_endpoint(client) -> None:
    response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["service"] == "Suburb Intelligence API"


def test_health_endpoint(client) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


@pytest.mark.parametrize(
    "path",
    [
        "/search",
        "/search/{suburb_name}/population-by-age",
        "/search/{suburb_name}/income",
        "/search/{suburb_name}/housing-tenure",
        "/search/{suburb_name}/osm-amenity-density",
        "/search/{suburb_name}/osm-cafe-density",
        "/search/{suburb_name}/osm-amenity-overview",
        "/search/{suburb_name}/osm-healthcare",
        "/search/{suburb_name}/osm-lifestyle",
        "/suburb/{sa2_code}",
        "/rankings",
    ],
)
def test_expected_routes_registered(client, path: str) -> None:
    """Regression: the ABS + OSM endpoints used to be nested inside
    `search_suburbs()` so they never registered. They must appear on the app."""
    paths = {route.path for route in client.app.routes}
    # FastAPI normalises trailing slashes; check either form is present.
    assert path in paths or f"{path}/" in paths, f"missing route {path}"
