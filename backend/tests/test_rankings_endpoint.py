"""Tests for the /rankings/ endpoint."""

from __future__ import annotations

import pytest


class TestGetRankings:
    def test_returns_two_seeded_suburbs(self, client):
        resp = client.get("/rankings/?limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert "rankings" in data
        assert data["count"] >= 2

    def test_default_ordered_descending_by_investment(self, client):
        resp = client.get("/rankings/?limit=10")
        assert resp.status_code == 200
        ranks = resp.json()["rankings"]
        scores = [r["investment_score"] for r in ranks if r["investment_score"] is not None]
        assert scores == sorted(scores, reverse=True)

    def test_rank_field_is_sequential(self, client):
        resp = client.get("/rankings/?limit=10")
        assert resp.status_code == 200
        ranks = resp.json()["rankings"]
        for i, r in enumerate(ranks, start=1):
            assert r["rank"] == i

    def test_top_score_matches_seed(self, client):
        resp = client.get("/rankings/?limit=10")
        assert resp.status_code == 200
        ranks = resp.json()["rankings"]
        # Chermside was seeded with investment_score=82.5 (highest of the two seeds)
        assert ranks[0]["investment_score"] == pytest.approx(82.5)
        assert ranks[0]["sa2_code"] == "47002"

    def test_demographic_score_ordering(self, client):
        resp = client.get("/rankings/?score_type=demographic_score&limit=10")
        assert resp.status_code == 200
        ranks = resp.json()["rankings"]
        scores = [r["demographic_score"] for r in ranks if r["demographic_score"] is not None]
        assert scores == sorted(scores, reverse=True)

    def test_invalid_score_type_returns_400(self, client):
        resp = client.get("/rankings/?score_type=bogus")
        assert resp.status_code == 400

    def test_response_includes_sa2_name_and_state(self, client):
        resp = client.get("/rankings/?limit=10")
        assert resp.status_code == 200
        first = resp.json()["rankings"][0]
        assert "sa2_name" in first
        assert "state" in first
        assert first["state"] in ("NSW", "VIC", "QLD", "SA", "WA", "TAS", "NT", "ACT")

    def test_all_score_types_present_in_row(self, client):
        resp = client.get("/rankings/?limit=10")
        assert resp.status_code == 200
        row = resp.json()["rankings"][0]
        for field in (
            "investment_score", "demographic_score", "economic_score",
            "housing_pressure_score", "resilience_score", "gov_investment_score",
            "momentum_score",
        ):
            assert field in row

    def test_momentum_score_is_a_valid_sort_type(self, client):
        resp = client.get("/rankings/?score_type=momentum_score&limit=10")
        assert resp.status_code == 200
        assert resp.json()["count"] >= 2

    def test_momentum_descriptive_fields_present_in_row(self, client):
        resp = client.get("/rankings/?limit=10")
        assert resp.status_code == 200
        row = resp.json()["rankings"][0]
        for field in ("momentum_phase", "growth_yield_quadrant", "neighborhood_signal"):
            assert field in row

    def test_market_stats_fields_present_in_every_row(self, client):
        """median_house_price and gross_yield_house_pct must exist on every row (null is OK)."""
        resp = client.get("/rankings/?limit=10")
        assert resp.status_code == 200
        for row in resp.json()["rankings"]:
            assert "median_house_price" in row
            assert "gross_yield_house_pct" in row

    def test_state_filter_returns_only_matching_state(self, client):
        """?states=QLD must include Chermside (QLD) and exclude Cronulla (NSW)."""
        resp = client.get("/rankings/?states=QLD&limit=50")
        assert resp.status_code == 200
        data = resp.json()
        states_returned = {r["state"] for r in data["rankings"]}
        assert states_returned == {"QLD"}, (
            f"Expected only QLD suburbs, got states: {states_returned}"
        )
        sa2_codes = [r["sa2_code"] for r in data["rankings"]]
        assert "47002" in sa2_codes, "Chermside (QLD) should appear in QLD-filtered results"
        assert "22625" not in sa2_codes, "Cronulla (NSW) must not appear in QLD-filtered results"


class TestGetTopSuburbs:
    def test_top_by_investment_score(self, client):
        resp = client.get("/search/top?by=investment_score&limit=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["by"] == "investment_score"
        assert len(data["suburbs"]) >= 1

    def test_top_by_invalid_field_returns_400(self, client):
        resp = client.get("/search/top?by=bogus")
        assert resp.status_code == 400
