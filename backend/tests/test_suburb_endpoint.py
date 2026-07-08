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


def test_suburb_report_has_no_numeric_composite_scores(client) -> None:
    """Regression: the report used to expose a `scores` dict of 0-100
    composite numbers; the product now shows underlying data instead."""
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    body = response.json()
    assert "scores" not in body


def test_suburb_report_has_all_sections(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    body = response.json()
    for section in (
        "location",
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
