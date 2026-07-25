"""Integration tests for POST /search/ask."""

from __future__ import annotations


def test_ask_returns_parsed_filter_and_results(client) -> None:
    resp = client.post("/search/ask", json={"prompt": "QLD suburbs"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["parsed_filter"]["state"] == "QLD"
    assert any(r["sa2_code"] == "47002" for r in body["results"])


def test_ask_orders_by_population_desc_by_default(client) -> None:
    resp = client.post("/search/ask", json={"prompt": "suburbs"})
    assert resp.status_code == 200
    pops = [r["population"] for r in resp.json()["results"] if r["population"] is not None]
    assert pops == sorted(pops, reverse=True)


def test_ask_top_n_limits_results(client) -> None:
    resp = client.post("/search/ask", json={"prompt": "top 1 suburbs"})
    assert resp.status_code == 200
    assert len(resp.json()["results"]) == 1


def test_ask_unmatched_filter_returns_message(client) -> None:
    resp = client.post("/search/ask", json={"prompt": "Darwin suburbs within 1km of CBD"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["results"] == []
    assert body["message"] is not None


def test_ask_bare_suburb_name_returns_that_suburb_not_generic_results(client) -> None:
    # Regression: "Cronulla" (no city/state/distance/top-N cue) used to fall
    # straight through to an unfiltered "top by population" query, silently
    # ignoring the name entirely and surfacing unrelated suburbs.
    resp = client.post("/search/ask", json={"prompt": "Cronulla"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["parsed_filter"]["suburb_name"] == "Cronulla"
    assert len(body["results"]) == 1
    assert body["results"][0]["sa2_code"] == "22625"
    assert body["message"] is None


def test_ask_suburb_name_candidate_with_no_match_falls_back_to_generic_results(client) -> None:
    # No real suburb matches this, so it should behave exactly like the
    # pre-existing "unmatched generic prompt" case (test above), not error
    # or return an empty result set.
    resp = client.post("/search/ask", json={"prompt": "zzznotarealsuburbzzz"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["parsed_filter"]["suburb_name"] == "zzznotarealsuburbzzz"
    assert len(body["results"]) > 0
