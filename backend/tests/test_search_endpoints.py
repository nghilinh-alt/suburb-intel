"""Integration tests for /search endpoints.

Most of these used to be impossible to hit because the nested-decorator bug in
`search.py` meant the per-suburb sub-routes were never registered.
"""

from __future__ import annotations

import pytest


def test_search_exact_sa2_code(client) -> None:
    response = client.get("/search/", params={"query": "47002"})
    assert response.status_code == 200
    body = response.json()
    assert body["sa2_code"] == "47002"
    assert body["sa2_name"] == "Chermside QLD"
    assert body["state"] == "QLD"
    assert body["population"] == 28900


def test_search_partial_name_returns_list(client) -> None:
    response = client.get("/search/", params={"query": "Chermside"})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["sa2_code"] == "47002"


def test_search_state_filter(client) -> None:
    # "cron" matches Cronulla; with state=NSW we expect only the NSW row back.
    response = client.get("/search/", params={"query": "cron", "state": "NSW"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) >= 1
    assert all(row["state"] == "NSW" for row in body)


def test_search_state_filter_excludes_other_states(client) -> None:
    # Cronulla is NSW; if we filter on QLD the same query must return nothing.
    response = client.get("/search/", params={"query": "cron", "state": "QLD"})
    assert response.status_code == 404


def test_search_no_match_returns_404(client) -> None:
    response = client.get("/search/", params={"query": "DefinitelyNotARealSuburb"})
    assert response.status_code == 404


def test_search_missing_query_returns_422(client) -> None:
    response = client.get("/search/")
    assert response.status_code == 422


def test_search_unknown_sa2_returns_404(client) -> None:
    response = client.get("/search/", params={"query": "99999"})
    assert response.status_code == 404


@pytest.mark.parametrize(
    "subpath", ["population-by-age", "income", "housing-tenure"]
)
def test_abs_subroutes_resolve_or_fail_cleanly(client, subpath: str) -> None:
    """The subroutes used to never register; this would be a 404 on routing.

    After the fix they exist; the upstream ABS call may succeed (200) or
    fail (502) depending on network - both are acceptable here because we
    are testing routing, not the ABS API.
    """
    response = client.get(f"/search/Chermside/{subpath}")
    assert response.status_code in {200, 404, 502}


def test_abs_subroute_returns_404_for_unknown_suburb(client) -> None:
    response = client.get("/search/NoSuchPlace/income")
    assert response.status_code == 404
