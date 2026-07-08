"""Tests for the rule-based plain-English suburb search parser."""

from __future__ import annotations

from app.core.nl_query_parser import parse_with_rules


def test_city_with_distance_filter():
    f = parse_with_rules("Brisbane suburbs within 10km of CBD")
    assert f.city == "Brisbane"
    assert f.state == "QLD"
    assert f.max_distance_to_cbd_km == 10.0
    assert f.sort_by == "distance_to_cbd"
    assert f.sort_dir == "asc"


def test_closest_to_cbd_without_explicit_distance():
    f = parse_with_rules("Melbourne suburbs closest to the CBD")
    assert f.state == "VIC"
    assert f.max_distance_to_cbd_km is None
    assert f.sort_by == "distance_to_cbd"
    assert f.sort_dir == "asc"


def test_top_n_and_highest_income():
    f = parse_with_rules("top 5 highest income suburbs in Sydney")
    assert f.state == "NSW"
    assert f.limit == 5
    assert f.sort_by == "median_income"
    assert f.sort_dir == "desc"


def test_no_city_defaults_to_no_state_filter():
    f = parse_with_rules("suburbs with the most population growth")
    assert f.state is None
    assert f.sort_by == "population"


def test_state_code_recognised_without_city_name():
    f = parse_with_rules("cheapest suburbs in QLD")
    assert f.state == "QLD"


def test_default_sort_and_limit_when_no_cues_present():
    f = parse_with_rules("Perth suburbs")
    assert f.state == "WA"
    assert f.sort_by == "population"
    assert f.sort_dir == "desc"
    assert f.limit == 10
