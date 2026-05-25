"""Tests for the OSM Overpass data source + route registration.

These tests are network-free: ``OSMOverpassDataSource.fetch_*`` calls are
monkey-patched. The original test file imported from a non-existent module
and tested attributes that no longer match the implementation.
"""

from __future__ import annotations

import asyncio

import pytest

from app.api.data_sources.osm_overpass import OSMOverpassDataSource


class TestOSMOverpassDataSource:
    def setup_method(self) -> None:
        self.osm = OSMOverpassDataSource()

    def test_default_attributes(self) -> None:
        assert self.osm.BASE_URL == "https://overpass-api.de/api/interpreter"
        assert self.osm.timeout == 30

    def test_amenity_tags_includes_cafe(self) -> None:
        assert self.osm.AMENITY_TAGS["cafe"] == "amenity=cafe"

    def test_amenity_weights_include_essential_types(self) -> None:
        for amenity in ("cafe", "grocery", "hospital", "pharmacy", "gym"):
            assert amenity in self.osm.AMENITY_WEIGHTS

    def test_build_overpass_query_uses_three_radii(self) -> None:
        """Regression: the original implementation produced malformed Overpass
        QL — the new builder must include the three radii and proper structure."""
        query = self.osm.build_overpass_query("South Yarra VIC", "amenity=cafe")
        assert "[out:json]" in query
        assert "around:500" in query
        assert "around:1000" in query
        assert "around:2000" in query
        assert "out count" in query
        assert "node" in query and "way" in query and "relation" in query

    def test_fetch_suburb_coordinates_falls_back_for_known_suburb(self) -> None:
        result = self.osm.fetch_suburb_coordinates("South Yarra VIC")
        assert isinstance(result, dict)
        assert -38 <= result["latitude"] <= -37
        assert result["display_name"] == "South Yarra VIC"

    def test_fetch_suburb_coordinates_handles_unknown_suburb(self) -> None:
        """Falls back to Melbourne so downstream code never sees None."""
        result = self.osm.fetch_suburb_coordinates("Totally Unknown 9999")
        assert "latitude" in result and "longitude" in result


class TestOSMRoutesNoNetwork:
    """Hit the OSM routes with monkey-patched fetches so no HTTP happens."""

    @pytest.fixture(autouse=True)
    def _patch_source(self, monkeypatch):
        async def fake_fetch_all(self, suburb_name):  # noqa: ARG001
            return {
                "amenities": {
                    "cafe": {"count_500m": 40, "count_1km": 80, "count_2km": 150},
                    "grocery": {"count_500m": 5, "count_1km": 10, "count_2km": 15},
                    "hospital": {"count_500m": 1, "count_1km": 2, "count_2km": 3},
                    "pharmacy": {"count_500m": 4, "count_1km": 8, "count_2km": 12},
                    "gym": {"count_500m": 3, "count_1km": 5, "count_2km": 7},
                    "park": {"count_500m": 6, "count_1km": 10, "count_2km": 14},
                    "bank": {"count_500m": 4, "count_1km": 7, "count_2km": 9},
                    "restaurant": {"count_500m": 20, "count_1km": 40, "count_2km": 70},
                    "swimming_pool": {"count_500m": 1, "count_1km": 2, "count_2km": 2},
                    "clinic": {"count_500m": 2, "count_1km": 4, "count_2km": 6},
                },
                "timestamp": "2026-05-26T00:00:00Z",
                "suburb": suburb_name,
            }

        async def fake_score(self, suburb_name):  # noqa: ARG001
            return 7.5

        async def fake_one(self, suburb_name, amenity_type):  # noqa: ARG001
            return {"count_500m": 42, "count_1km": 87, "count_2km": 156}

        monkeypatch.setattr(OSMOverpassDataSource, "fetch_all_amenity_types", fake_fetch_all)
        monkeypatch.setattr(
            OSMOverpassDataSource, "calculate_amenity_density_score", fake_score
        )
        monkeypatch.setattr(OSMOverpassDataSource, "fetch_amenity_counts", fake_one)

    def test_amenity_density_route(self, client) -> None:
        response = client.get("/search/South%20Yarra/osm-amenity-density")
        assert response.status_code == 200
        body = response.json()
        assert body["suburb"] == "South Yarra"
        assert body["density_score"] == 7.5
        assert "cafe" in body["amenities_breakdown"]

    def test_cafe_density_route_classifies_high(self, client) -> None:
        response = client.get("/search/South%20Yarra/osm-cafe-density")
        assert response.status_code == 200
        body = response.json()
        assert body["amenity"] == "cafe"
        assert body["density_indicator"] == "HIGH"  # 42 >= 30
        assert body["counts"]["within_500m"] == 42

    def test_amenity_overview_route_returns_score_and_breakdown(self, client) -> None:
        """Regression: the original route populated `amenities_breakdown = []`
        but never appended to it inside the loop. After the fix the breakdown
        list must be non-empty."""
        response = client.get("/search/South%20Yarra/osm-amenity-overview")
        assert response.status_code == 200
        body = response.json()
        assert body["overall_amenity_score"] > 0
        assert len(body["amenities"]) > 0
        assert any(item["type"] == "cafe" for item in body["amenities"])

    def test_healthcare_route_returns_rating(self, client) -> None:
        response = client.get("/search/South%20Yarra/osm-healthcare")
        assert response.status_code == 200
        body = response.json()
        assert body["rating"] in {"EXCELLENT", "GOOD", "ADEQUATE"}
        assert body["nearby_hospitals_500m"] == 1

    def test_lifestyle_route_returns_rating(self, client) -> None:
        response = client.get("/search/South%20Yarra/osm-lifestyle")
        assert response.status_code == 200
        body = response.json()
        assert body["lifestyle_rating"] in {"VIBRANT", "LIVEABLE", "STANDARD"}
        assert body["cafe_count_500m"] == 40
