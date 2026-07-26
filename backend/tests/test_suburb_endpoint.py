"""Integration tests for /suburb/{sa2_code}.

The endpoint returns section-grouped raw data rather than 0-100 composite
scores — see app/api/suburb.py's module docstring for why.
"""

from __future__ import annotations


def test_suburb_report_for_seeded_sa2(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    body = response.json()

    assert body["sa2_code"] == "47002"
    assert body["census_year"] == 2021
    assert body["demographics"]["population"] == 28900


def test_suburb_report_show_census_sections_defaults_true(client) -> None:
    # Default must match pre-flag behaviour (everything visible) so adding
    # this config doesn't silently change what's shown until deliberately flipped.
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    assert response.json()["show_census_sections"] is True


def test_suburb_report_scores_contains_only_resilience_and_housing_pressure(client) -> None:
    """The `scores` key must expose only resilience_score and housing_pressure_score.
    The full composite investment/demographic/economic scores are intentionally
    kept out of the suburb report (they drive insight/tags/risk_flags text but
    the underlying metrics are more useful to show directly)."""
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    body = response.json()
    assert "scores" in body
    scores = body["scores"]
    assert set(scores.keys()) == {"resilience_score", "housing_pressure_score"}
    # Values are either null (no SuburbScore row for the seed SA2) or 0-100 floats
    for v in scores.values():
        assert v is None or (isinstance(v, (int, float)) and 0 <= v <= 100)


def test_suburb_report_has_all_sections(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    body = response.json()
    for section in (
        "location",
        "momentum",
        "property_market",
        "investment_outlook",
        "demographics",
        "economy",
        "housing",
        "community",
        "government_investment",
        "schools",
        "amenities",
        "transport",
    ):
        assert section in body, f"missing section: {section}"


def test_suburb_report_property_market_shape(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    pm = response.json()["property_market"]
    assert "recent_sales" in pm
    assert isinstance(pm["recent_sales"], list)
    assert pm["recent_sales_available"] is False  # no PropRadar data ingested yet
    assert pm["price_history"] == []  # no property_sales rows yet
    assert pm["land_size_breakdown"] == []  # no property_sales rows yet


def test_suburb_report_momentum_sale_velocity_shape(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    velocity = response.json()["momentum"]["sale_velocity"]
    assert velocity["monthly_counts"] == []  # no property_sales rows yet
    assert velocity["trend_pct"] is None


def test_suburb_report_momentum_supply_scarcity_shape(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    assert response.json()["momentum"]["supply_scarcity"] == []  # no suburb_market_stats rows yet


def test_suburb_report_momentum_composite_shape(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    assert response.json()["momentum"]["composite"] == []  # no suburb_market_stats rows yet


def test_suburb_report_investment_snapshot_none_without_market_stats(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    assert response.json()["investment_snapshot"] is None  # no suburb_market_stats rows yet


def test_suburb_report_momentum_neighborhood_shape(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    neighborhood = response.json()["momentum"]["neighborhood"]
    assert neighborhood["total_neighbors"] == 0  # seeded SA2 has no adjacent_sa2_codes
    assert neighborhood["signal"] is None


def test_suburb_report_momentum_growth_yield_quadrant_shape(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    assert response.json()["momentum"]["growth_yield_quadrant"] == []  # no suburb_market_stats rows yet


def test_suburb_report_momentum_property_cycle_shape(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    assert response.json()["momentum"]["property_cycle"] == []  # no suburb_market_stats rows yet


def test_suburb_report_housing_by_house_type_shape(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    assert response.json()["housing"]["by_house_type"] == []  # no property_sales rows yet


def test_suburb_report_schools_local_and_nearby_shape(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    schools = response.json()["schools"]
    assert "local" in schools
    assert "nearby" in schools
    assert isinstance(schools["local"], list)
    assert isinstance(schools["nearby"], list)


def test_suburb_report_school_percentile_none_without_icsea_data(client) -> None:
    """No ICSEA data is loaded (ACARA terms not accepted — see
    school_icsea_loader.py), so this should be None, not a fabricated rank."""
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    assert response.json()["schools"]["state_percentile"] is None


def test_suburb_report_regional_comparison_none_without_sa4(client) -> None:
    """Seeded test suburbs don't have sa4_name set, so there's no local
    city/region to compare against — the endpoint should omit it cleanly
    rather than error."""
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    assert response.json()["regional_comparison"] is None


def test_suburb_report_returns_404_when_missing(client) -> None:
    response = client.get("/suburb/99999")
    assert response.status_code == 404


def test_suburb_report_handles_low_renter_suburb(client) -> None:
    """Regression: gov_score.analyze_risk_flags used to crash with AttributeError
    because it called `.get()` on an ORM model. With Chermside's seeded data
    (low renter %, diversified industries) we expect no rental/dependency flags
    and a clean 200."""
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    flags = response.json()["risk_flags"]
    # 31.5% renters → below the 40% threshold, so no rental flag
    assert not any("rental pressure" in f.lower() for f in flags)


def test_suburb_report_populates_name_and_state(client) -> None:
    """Regression: /suburb/{id} used to return sa2_name=None and state=None
    because it pulled only ABSCEntensMetrics (which doesn't have those fields).
    The endpoint now joins SA2Region so the response carries the human-readable
    name + state code."""
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    body = response.json()
    assert body["sa2_name"] == "Chermside QLD"
    assert body["state"] == "QLD"
