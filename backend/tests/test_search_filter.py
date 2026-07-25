"""Tests for /search/filter and /search/filter-options — the Search page's
filter sidebar backend. Uses the shared seeded SA2s from conftest.py:
47002 Chermside QLD (pop 28900, income 102000, investment_score 82.5),
22625 Cronulla NSW (pop 18750, income 91000, investment_score 71.0),
30150 Altona Gardens VIC (no census/score row).

All tests share ONE SQLite DB across the whole test session (see
conftest.py), so other test files' dummy SA2/census rows are present too —
assertions below check for presence/absence/order of the known seeded
codes rather than exact total_count, except where a narrow filter band
(chosen to be unlikely to collide with other tests' dummy values) isolates
an exact, predictable set.
"""

from __future__ import annotations


def _codes(body) -> set[str]:
    return {r["sa2_code"] for r in body["results"]}


def test_filter_no_params_includes_seeded_suburbs_with_census_data(client) -> None:
    response = client.get("/search/filter", params={"limit": 100})
    assert response.status_code == 200
    body = response.json()
    assert {"47002", "22625"} <= _codes(body)
    # 30150 has no ABSCEntensMetrics row (inner join) so it must be excluded
    assert "30150" not in _codes(body)


def test_filter_by_narrow_income_band_isolates_chermside(client) -> None:
    response = client.get(
        "/search/filter",
        params={"min_median_income": 101999, "max_median_income": 102001},
    )
    assert response.status_code == 200
    body = response.json()
    assert _codes(body) == {"47002"}


def test_filter_by_state_excludes_other_states(client) -> None:
    response = client.get(
        "/search/filter",
        params={"states": "NSW", "min_median_income": 90999, "max_median_income": 91001},
    )
    body = response.json()
    assert _codes(body) == {"22625"}


def test_filter_min_population_excludes_smaller_suburb(client) -> None:
    response = client.get(
        "/search/filter",
        params={"states": "NSW,QLD", "min_population": 20000, "max_population": 29000},
    )
    body = response.json()
    assert _codes(body) == {"47002"}


def test_filter_min_investment_score_includes_only_high_scorer(client) -> None:
    response = client.get(
        "/search/filter",
        params={"states": "NSW,QLD", "min_investment_score": 82, "min_population": 18000, "max_population": 29000},
    )
    body = response.json()
    codes = _codes(body)
    assert "47002" in codes
    assert "22625" not in codes
    chermside = next(r for r in body["results"] if r["sa2_code"] == "47002")
    assert chermside["investment_score"] == 82.5


def test_filter_combines_multiple_filters_with_and(client) -> None:
    # Cronulla's income is 91000 — a 100000 floor combined with state=NSW
    # must exclude it even though the bare state filter would include it.
    response = client.get(
        "/search/filter", params={"states": "NSW", "min_median_income": 100000, "min_population": 18000, "max_population": 19000}
    )
    body = response.json()
    assert "22625" not in _codes(body)


def test_filter_sort_by_median_income_ascending_orders_correctly(client) -> None:
    response = client.get(
        "/search/filter",
        params={"states": "NSW,QLD", "min_population": 18000, "max_population": 29000, "sort_by": "median_income", "sort_dir": "asc"},
    )
    body = response.json()
    codes = [r["sa2_code"] for r in body["results"]]
    assert codes == ["22625", "47002"]  # Cronulla (91000) before Chermside (102000)


def test_filter_pagination_limit_and_offset(client) -> None:
    narrow = {"states": "NSW,QLD", "min_population": 18000, "max_population": 29000, "sort_by": "population"}

    page1 = client.get("/search/filter", params={**narrow, "limit": 1, "offset": 0}).json()
    assert page1["total_count"] == 2
    assert len(page1["results"]) == 1
    assert page1["results"][0]["sa2_code"] == "47002"  # higher population, default desc

    page2 = client.get("/search/filter", params={**narrow, "limit": 1, "offset": 1}).json()
    assert page2["results"][0]["sa2_code"] == "22625"


def test_filter_options_returns_distinct_states(client) -> None:
    response = client.get("/search/filter-options")
    assert response.status_code == 200
    body = response.json()
    assert set(body["states"]) >= {"QLD", "NSW", "VIC"}


def test_filter_response_includes_momentum_fields(client) -> None:
    response = client.get(
        "/search/filter",
        params={"min_median_income": 101999, "max_median_income": 102001},
    )
    assert response.status_code == 200
    chermside = next(r for r in response.json()["results"] if r["sa2_code"] == "47002")
    for field in ("momentum_score", "momentum_phase", "growth_yield_quadrant", "neighborhood_signal"):
        assert field in chermside
    # Seeded SuburbScore rows don't set momentum fields, so they're null.
    assert chermside["momentum_phase"] is None


def test_filter_by_momentum_phase_excludes_suburbs_without_that_phase(client) -> None:
    # Seeded suburbs have no momentum_phase set at all, so filtering for a
    # real phase value must exclude them (not error, not match everything).
    response = client.get(
        "/search/filter",
        params={"min_median_income": 101999, "max_median_income": 102001, "momentum_phase": "accelerating"},
    )
    assert response.status_code == 200
    assert "47002" not in _codes(response.json())


def test_filter_by_invalid_momentum_phase_returns_422(client) -> None:
    response = client.get("/search/filter", params={"momentum_phase": "bogus"})
    assert response.status_code == 422


def test_filter_by_invalid_growth_yield_quadrant_returns_422(client) -> None:
    response = client.get("/search/filter", params={"growth_yield_quadrant": "bogus"})
    assert response.status_code == 422


def test_filter_sortable_by_momentum_score(client) -> None:
    response = client.get("/search/filter", params={"sort_by": "momentum_score", "limit": 100})
    assert response.status_code == 200  # doesn't error even though it's an unfamiliar sort column
