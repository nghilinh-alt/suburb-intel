"""Tests for suburb_market_stats_loader's pure parsing, using the real
verified response shape (see that module's docstring — captured from a live
200 response against QLD/cleveland on 2026-07-09)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.db.models import SuburbMarketStats
from app.db.session import get_sync_session
from app.ingestion.suburb_market_stats_loader import _already_fetched, _parse_stats

_REAL_RESPONSE = {
    "suburb": "CLEVELAND", "state": "QLD", "postcode": 4163,
    "medians": {"house_price": 1280000, "unit_price": 865000, "house_weekly_rent": 795, "unit_weekly_rent": 630},
    "growth": {
        "house": {"qtr_pct": None, "1y_pct": 10.8, "3y_pct": 40, "5y_pct": 84.7, "10y_pct": None},
        "unit": {"qtr_pct": None, "1y_pct": None, "3y_pct": None, "5y_pct": None, "10y_pct": None},
    },
    "yields": {"house_gross_pct": 3.23, "unit_gross_pct": 3.79},
    "market_dynamics": {
        "house_days_on_market": 15, "unit_days_on_market": 41, "vacancy_rate_pct": 1.12,
        "house_inventory_months": 4.62, "unit_inventory_months": 1.64,
        "house_stock_on_market_pct": 0.66, "unit_stock_on_market_pct": 0.31,
        "sold_vs_asking_pct": 3.4, "house_heat_score": 78, "unit_heat_score": None,
        "house_sales_12mo": 262, "unit_sales_12mo": 148,
    },
    "demographics": {
        "population": 15850, "median_age": 51, "median_household_income": 1430,
        "owner_occupied_pct": 66.8, "renter_pct": 29.4, "unemployment_rate_pct": 3.2,
        "socioeconomic_score": 49,
    },
    "location": {"distance_to_cbd_km": 24.6},
    "as_of": "2026-07-01T22:45:07.072Z",
    "locked_fields": {"livability": {"upgrade_to": "starter"}},
}


def test_parse_stats_reads_real_field_names():
    stats = _parse_stats(_REAL_RESPONSE, "QLD-cleveland-2026-07", "301021007", "QLD", "Cleveland", "2026-07")

    assert stats.id == "QLD-cleveland-2026-07"
    assert stats.sa2_code == "301021007"
    assert stats.suburb_name == "Cleveland"
    assert stats.postcode == "4163"
    assert stats.period == "2026-07"
    assert stats.median_house_price == 1280000
    assert stats.median_unit_price == 865000
    assert stats.median_house_rent_weekly == 795
    assert stats.growth_house_1y_pct == 10.8
    assert stats.growth_house_qtr_pct is None
    assert stats.gross_yield_house_pct == 3.23
    assert stats.days_on_market_house == 15
    assert stats.sold_vs_asking_pct == 3.4
    assert stats.pr_population == 15850
    assert stats.pr_distance_to_cbd_km == 24.6
    assert stats.as_of == datetime(2026, 7, 1, 22, 45, 7, 72000, tzinfo=timezone.utc)


def test_parse_stats_handles_missing_optional_sections():
    minimal = {"suburb": "test", "state": "QLD"}
    stats = _parse_stats(minimal, "QLD-test-2026-07", "999999999", "QLD", "Test", "2026-07")
    assert stats.median_house_price is None
    assert stats.pr_population is None
    assert stats.as_of is None


def _seed_stats(db, stats_id, period):
    db.merge(SuburbMarketStats(
        id=stats_id, sa2_code="90000099", suburb_name="Test", state="QLD", period=period,
    ))
    db.commit()


def test_already_fetched_true_when_row_exists_for_this_periods_id():
    db = get_sync_session()
    _seed_stats(db, "fresh-check-1-2026-07", "2026-07")
    assert _already_fetched(db, "fresh-check-1-2026-07") is True
    db.close()


def test_already_fetched_false_for_a_different_periods_id():
    db = get_sync_session()
    _seed_stats(db, "fresh-check-2-2026-06", "2026-06")
    assert _already_fetched(db, "fresh-check-2-2026-07") is False
    db.close()


def test_already_fetched_false_when_no_data():
    db = get_sync_session()
    assert _already_fetched(db, "fresh-check-3-never-seeded-2026-07") is False
    db.close()
