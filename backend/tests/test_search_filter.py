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
