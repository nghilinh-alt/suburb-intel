"""Integration tests for /suburb/{sa2_code}."""

from __future__ import annotations


def test_suburb_report_for_seeded_sa2(client) -> None:
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    body = response.json()

    # Basic shape
    assert body["sa2_code"] == "47002"
    assert body["census_year"] == 2021
    assert body["population"] == 28900

    # Scores block has all the documented keys
    scores = body["scores"]
    for key in (
        "investment_score",
        "demographic_score",
        "economic_score",
        "housing_pressure_score",
        "resilience_score",
        "gov_investment_score",
    ):
        assert key in scores
        assert isinstance(scores[key], (int, float))

    # Tags + risk flags are lists (may be empty for a low-risk suburb).
    assert isinstance(body["tags"], list)
    assert isinstance(body["risk_flags"], list)


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


def test_suburb_report_economic_score_within_contract(client) -> None:
    """Regression: Chermside's median income ($102k) used to push the economic
    sub-score to 112, breaking the 0-100 contract. The income_index is now
    clamped at 100 and the sub-score itself is defensively capped."""
    response = client.get("/suburb/47002")
    assert response.status_code == 200
    scores = response.json()["scores"]
    for key in (
        "investment_score",
        "demographic_score",
        "economic_score",
        "housing_pressure_score",
        "resilience_score",
        "gov_investment_score",
    ):
        assert 0 <= scores[key] <= 100, f"{key}={scores[key]} out of 0-100 range"
