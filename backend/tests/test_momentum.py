"""Tests for app.core.momentum's pure functions, using synthetic sold-date
lists (no DB) — see test_momentum_service.py for the DB-backed wrapper."""

from __future__ import annotations

from datetime import date

import math

from app.core.momentum import (
    classify_growth_yield_quadrant,
    classify_property_cycle_position,
    compute_derived_growth,
    compute_momentum,
    compute_sale_velocity,
    compute_supply_scarcity,
    generate_investment_snapshot,
    summarize_neighborhood_momentum,
)


def test_sale_velocity_monthly_counts_group_by_month():
    sold_dates = ["2026-05-01", "2026-05-15", "2026-06-01"]
    result = compute_sale_velocity(sold_dates, as_of=date(2026, 7, 10))

    assert result["monthly_counts"] == [
        {"period": "2026-05", "count": 2},
        {"period": "2026-06", "count": 1},
    ]


def test_sale_velocity_accelerating_trend():
    # Prior 3mo (Apr-Jun): 1 sale. Recent 3mo (Jul-Sep... well as_of=Sep):
    # simpler to reason about with as_of fixed and explicit windows below.
    as_of = date(2026, 9, 15)
    # prior window: Jun, Jul, Aug -> wait _last_n_month_keys(as_of, 6) gives
    # Apr..Sep; prior=[Apr,May,Jun], recent=[Jul,Aug,Sep].
    sold_dates = (
        ["2026-04-01"] * 2  # prior
        + ["2026-07-01"] * 4  # recent
        + ["2026-08-01"] * 2  # recent
    )
    result = compute_sale_velocity(sold_dates, as_of=as_of)

    assert result["prior_3mo_count"] == 2
    assert result["recent_3mo_count"] == 6
    assert result["trend_pct"] == 200.0  # (6-2)/2 * 100


def test_sale_velocity_cooling_trend():
    as_of = date(2026, 9, 15)
    sold_dates = ["2026-04-01"] * 6 + ["2026-07-01"] * 1  # prior=6, recent=1
    result = compute_sale_velocity(sold_dates, as_of=as_of)

    assert result["prior_3mo_count"] == 6
    assert result["recent_3mo_count"] == 1
    assert result["trend_pct"] == -83.3


def test_sale_velocity_trend_none_when_no_prior_activity():
    as_of = date(2026, 9, 15)
    sold_dates = ["2026-07-01", "2026-08-01"]  # only recent, nothing prior
    result = compute_sale_velocity(sold_dates, as_of=as_of)

    assert result["prior_3mo_count"] == 0
    assert result["recent_3mo_count"] == 2
    assert result["trend_pct"] is None  # undefined, not fabricated as "infinite"


def test_sale_velocity_empty_input():
    result = compute_sale_velocity([], as_of=date(2026, 7, 10))
    assert result == {
        "monthly_counts": [],
        "recent_3mo_count": 0,
        "prior_3mo_count": 0,
        "trend_pct": None,
    }


def test_sale_velocity_skips_unparseable_dates():
    result = compute_sale_velocity([None, "", "bad"], as_of=date(2026, 7, 10))
    assert result["monthly_counts"] == []


def test_sale_velocity_caps_history_at_24_months():
    sold_dates = [f"{2020 + y}-{m:02d}-01" for y in range(6) for m in range(1, 13)]  # 72 months
    result = compute_sale_velocity(sold_dates, as_of=date(2026, 7, 10))
    assert len(result["monthly_counts"]) == 24


def _sale(sold_date, sold_price, property_type="house"):
    return {"sold_date": sold_date, "sold_price": sold_price, "property_type": property_type}


def test_derived_growth_computes_house_1y_from_year_over_year_medians():
    as_of = date(2026, 7, 10)
    sales = [
        # recent window (Aug 2025 - Jul 2026): median 610,000
        _sale("2026-06-01", 600_000), _sale("2026-06-10", 620_000), _sale("2026-06-20", 610_000),
        # comparison window one year back (Aug 2024 - Jul 2025): median 505,000
        _sale("2025-06-01", 500_000), _sale("2025-06-10", 510_000), _sale("2025-06-20", 505_000),
    ]
    result = compute_derived_growth(sales, as_of=as_of)
    assert result["growth_house_1y_pct"] == 20.8
    # No sales at all 3y/5y back -> undefined, not fabricated
    assert result["growth_house_3y_pct"] is None
    assert result["growth_house_5y_pct"] is None


def test_derived_growth_none_below_minimum_sample_size():
    as_of = date(2026, 7, 10)
    sales = [_sale("2026-06-01", 600_000), _sale("2026-06-10", 620_000)]  # only 2, need 3
    result = compute_derived_growth(sales, as_of=as_of)
    assert result["growth_house_1y_pct"] is None


def test_derived_growth_splits_house_and_unit_buckets():
    as_of = date(2026, 7, 10)
    sales = [
        _sale("2026-06-01", 600_000, "house"), _sale("2026-06-05", 610_000, "house"), _sale("2026-06-10", 620_000, "house"),
        _sale("2025-06-01", 500_000, "house"), _sale("2025-06-05", 505_000, "house"), _sale("2025-06-10", 510_000, "house"),
        _sale("2026-06-01", 400_000, "apartment"), _sale("2026-06-05", 410_000, "unit"), _sale("2026-06-10", 420_000, "flat"),
        _sale("2025-06-01", 350_000, "apartment"), _sale("2025-06-05", 355_000, "unit"), _sale("2025-06-10", 360_000, "flat"),
    ]
    result = compute_derived_growth(sales, as_of=as_of)
    assert result["growth_house_1y_pct"] is not None
    assert result["growth_unit_1y_pct"] is not None
    assert result["growth_house_1y_pct"] != result["growth_unit_1y_pct"]


def test_derived_growth_ignores_unmapped_property_types():
    # Townhouse/villa/duplex don't map to either PropRadar bucket — excluded
    # entirely rather than guessed into house or unit.
    as_of = date(2026, 7, 10)
    sales = [_sale("2026-06-01", 900_000, "townhouse") for _ in range(5)]
    result = compute_derived_growth(sales, as_of=as_of)
    assert result["growth_house_1y_pct"] is None
    assert result["growth_unit_1y_pct"] is None


def test_derived_growth_empty_input():
    result = compute_derived_growth([], as_of=date(2026, 7, 10))
    assert all(v is None for v in result.values())
    assert set(result.keys()) == {
        "growth_house_1y_pct", "growth_house_3y_pct", "growth_house_5y_pct",
        "growth_unit_1y_pct", "growth_unit_3y_pct", "growth_unit_5y_pct",
    }


def test_supply_scarcity_all_inputs_present():
    result = compute_supply_scarcity(
        stock_on_market_pct_house=0.66,
        stock_on_market_pct_unit=0.31,
        inventory_months_house=4.62,
        inventory_months_unit=1.64,
        building_approvals_1yr=150,
        population=15850,
    )
    assert result["components"]["stock_on_market_score"] == 30.7
    assert result["components"]["inventory_months_score"] == 34.1
    # 150/15850*1000 = 9.46 per 1000, above the 6.8 ceiling -> clamped to 0
    assert result["components"]["building_approvals_score"] == 0.0
    assert result["scarcity_score"] == 22.7


def test_supply_scarcity_zero_supply_maxes_out_at_100():
    result = compute_supply_scarcity(
        stock_on_market_pct_house=0.0,
        inventory_months_house=0.0,
        building_approvals_1yr=0,
        population=10_000,
    )
    assert result["scarcity_score"] == 100.0


def test_supply_scarcity_abundant_supply_floors_at_0():
    result = compute_supply_scarcity(
        stock_on_market_pct_house=10.0,  # well above ceiling
        inventory_months_house=24.0,     # well above ceiling
        building_approvals_1yr=5000,
        population=10_000,               # 500 per 1000, way above ceiling
    )
    assert result["scarcity_score"] == 0.0


def test_supply_scarcity_reweights_over_available_components_only():
    # Only stock-on-market available — score should equal that component's
    # value alone, not be dragged down by treating missing inputs as 0.
    result = compute_supply_scarcity(stock_on_market_pct_house=0.0)
    assert result["components"]["inventory_months_score"] is None
    assert result["components"]["building_approvals_score"] is None
    assert result["scarcity_score"] == 100.0


def test_supply_scarcity_none_when_nothing_available():
    result = compute_supply_scarcity()
    assert result["scarcity_score"] is None
    assert all(v is None for v in result["components"].values())


def test_supply_scarcity_averages_house_and_unit_variants():
    with_both = compute_supply_scarcity(stock_on_market_pct_house=0.0, stock_on_market_pct_unit=3.0)
    house_only_at_midpoint = compute_supply_scarcity(stock_on_market_pct_house=1.5)
    assert with_both["scarcity_score"] == house_only_at_midpoint["scarcity_score"]


def test_momentum_accelerating_fixture():
    result = compute_momentum(
        sale_velocity_trend_pct=40.0,
        growth_house_1y_pct=15.0,
        scarcity_score=85.0,
        heat_score_house=80.0,
    )
    assert result["phase"] == "accelerating"
    assert result["momentum_score"] == 72.2
    assert result["components"]["sale_velocity"]["signal"] == 0.8
    assert result["components"]["supply_scarcity"]["signal"] == 0.7


def test_momentum_cooling_fixture():
    result = compute_momentum(
        sale_velocity_trend_pct=-40.0,
        growth_house_1y_pct=-10.0,
        scarcity_score=15.0,
        heat_score_house=20.0,
    )
    assert result["phase"] == "cooling"
    assert result["momentum_score"] == -66.0


def test_momentum_steady_fixture():
    result = compute_momentum(
        sale_velocity_trend_pct=0.0,
        growth_house_1y_pct=0.0,
        scarcity_score=50.0,  # neutral midpoint, not "no scarcity"
        heat_score_house=50.0,
    )
    assert result["phase"] == "steady"
    assert result["momentum_score"] == 0.0


def test_momentum_reweights_over_available_components():
    result = compute_momentum(sale_velocity_trend_pct=25.0)
    assert result["momentum_score"] == 50.0  # signal 0.5 alone, not diluted by 3 missing "neutral" inputs
    assert result["phase"] == "accelerating"
    assert result["components"]["growth"]["signal"] is None


def test_momentum_none_when_nothing_available():
    result = compute_momentum()
    assert result["phase"] is None
    assert result["momentum_score"] is None
    assert all(c["signal"] is None for c in result["components"].values())


def test_momentum_averages_house_and_unit_growth_and_heat():
    result = compute_momentum(
        sale_velocity_trend_pct=0.0,
        growth_house_1y_pct=10.0, growth_unit_1y_pct=-10.0,  # averages to 0
        heat_score_house=80.0, heat_score_unit=20.0,  # averages to 50 (neutral)
    )
    assert result["components"]["growth"]["growth_pct"] == 0.0
    assert result["components"]["heat_score"]["value"] == 50.0


def test_investment_snapshot_all_positive_signals():
    result = generate_investment_snapshot(
        momentum_phase="accelerating",
        growth_house_1y_pct=10.8,
        gross_yield_house_pct=4.5,
        scarcity_score=75.0,
        days_on_market_house=15,
    )
    assert result["verdict"] == (
        "Momentum accelerating; Prices up 10.8% over the past year; "
        "Strong 4.5% rental yield; Supply is tight; Selling fast (15 days on market)"
    )
    by_label = {h["label"]: h for h in result["highlights"]}
    assert by_label["Momentum"]["tone"] == "positive"
    assert by_label["Momentum"]["value"] == "Accelerating"
    assert by_label["1yr Price Growth"]["tone"] == "positive"
    assert by_label["Gross Rental Yield"]["tone"] == "positive"
    assert by_label["Supply Scarcity"]["tone"] == "positive"
    assert by_label["Days on Market"]["tone"] == "positive"


def test_investment_snapshot_all_negative_signals():
    result = generate_investment_snapshot(
        momentum_phase="cooling",
        growth_house_1y_pct=-5.0,
        gross_yield_house_pct=2.0,
        scarcity_score=20.0,
        days_on_market_house=60,
    )
    assert "Momentum cooling" in result["verdict"]
    assert "Prices down 5.0%" in result["verdict"]
    by_label = {h["label"]: h for h in result["highlights"]}
    assert by_label["Momentum"]["tone"] == "negative"
    assert by_label["1yr Price Growth"]["tone"] == "negative"
    assert by_label["Gross Rental Yield"]["tone"] == "negative"
    assert by_label["Supply Scarcity"]["tone"] == "negative"
    assert by_label["Days on Market"]["tone"] == "negative"


def test_investment_snapshot_none_when_everything_missing():
    result = generate_investment_snapshot()
    assert result["verdict"] is None
    assert all(h["value"] is None for h in result["highlights"])
    assert all(h["tone"] == "neutral" for h in result["highlights"])


def test_investment_snapshot_partial_data_only_uses_whats_available():
    result = generate_investment_snapshot(growth_house_1y_pct=8.0)
    assert result["verdict"] == "Prices up 8.0% over the past year"
    by_label = {h["label"]: h for h in result["highlights"]}
    assert by_label["1yr Price Growth"]["value"] == 8.0
    assert by_label["Gross Rental Yield"]["value"] is None


def test_neighborhood_momentum_surrounded_by_acceleration():
    result = summarize_neighborhood_momentum(["accelerating", "accelerating", "steady"])
    assert result["total_neighbors"] == 3
    assert result["counts"] == {"accelerating": 2, "steady": 1, "cooling": 0}
    assert result["accelerating_pct"] == 66.7
    assert result["signal"] == "surrounded_by_acceleration"


def test_neighborhood_momentum_surrounded_by_cooling():
    result = summarize_neighborhood_momentum(["cooling", "cooling", "steady"])
    assert result["signal"] == "surrounded_by_cooling"
    assert result["cooling_pct"] == 66.7


def test_neighborhood_momentum_no_signal_when_mixed():
    result = summarize_neighborhood_momentum(["accelerating", "cooling", "steady", "steady"])
    assert result["signal"] is None
    assert result["accelerating_pct"] == 25.0
    assert result["cooling_pct"] == 25.0


def test_neighborhood_momentum_no_signal_on_exact_tie():
    # Regression: an exact 50/50 split used to arbitrarily favor
    # "accelerating" because it was checked first with a >= comparison.
    # A tie is not a majority for either side.
    result = summarize_neighborhood_momentum(["accelerating", "cooling"])
    assert result["accelerating_pct"] == 50.0
    assert result["cooling_pct"] == 50.0
    assert result["signal"] is None


def test_neighborhood_momentum_ignores_unknown_neighbors():
    # Two neighbors have no momentum data (no PropRadar coverage) — only the
    # known ones count toward total_neighbors and the percentages.
    result = summarize_neighborhood_momentum(["accelerating", "accelerating", None, None])
    assert result["total_neighbors"] == 2
    assert result["accelerating_pct"] == 100.0
    assert result["signal"] == "surrounded_by_acceleration"


def test_neighborhood_momentum_no_signal_below_minimum_known_neighbors():
    # Only 1 known neighbor — too small a sample to call a signal, even
    # though it's 100% accelerating.
    result = summarize_neighborhood_momentum(["accelerating", None, None])
    assert result["total_neighbors"] == 1
    assert result["signal"] is None


def test_neighborhood_momentum_empty_input():
    result = summarize_neighborhood_momentum([])
    assert result == {
        "total_neighbors": 0,
        "counts": {"accelerating": 0, "steady": 0, "cooling": 0},
        "accelerating_pct": None,
        "cooling_pct": None,
        "signal": None,
    }


def test_quadrant_hot_when_both_above_median():
    result = classify_growth_yield_quadrant(growth_house_1y_pct=15.0, gross_yield_house_pct=5.0)
    assert result["quadrant"] == "hot"
    assert "growth and yield" in result["label"]


def test_quadrant_growth_play_when_only_growth_above_median():
    result = classify_growth_yield_quadrant(growth_house_1y_pct=15.0, gross_yield_house_pct=2.0)
    assert result["quadrant"] == "growth_play"


def test_quadrant_cash_flow_play_when_only_yield_above_median():
    result = classify_growth_yield_quadrant(growth_house_1y_pct=5.0, gross_yield_house_pct=5.0)
    assert result["quadrant"] == "cash_flow_play"


def test_quadrant_avoid_when_both_below_median():
    result = classify_growth_yield_quadrant(growth_house_1y_pct=2.0, gross_yield_house_pct=2.0)
    assert result["quadrant"] == "avoid"


def test_quadrant_at_exact_median_counts_as_above():
    result = classify_growth_yield_quadrant(growth_house_1y_pct=9.6, gross_yield_house_pct=3.62)
    assert result["quadrant"] == "hot"


def test_quadrant_none_when_growth_missing():
    result = classify_growth_yield_quadrant(growth_house_1y_pct=None, gross_yield_house_pct=5.0)
    assert result == {"quadrant": None, "label": None}


def test_quadrant_none_when_yield_missing():
    result = classify_growth_yield_quadrant(growth_house_1y_pct=15.0, gross_yield_house_pct=None)
    assert result == {"quadrant": None, "label": None}


def _cycle_point(theta_deg):
    theta = math.radians(theta_deg)
    return math.sin(theta), math.cos(theta)


def test_cycle_position_start_of_recovery_at_zero_degrees():
    g, v = _cycle_point(0)
    result = classify_property_cycle_position(g, v)
    assert result["position"] == "start_of_recovery"
    assert result["angle_degrees"] == 0.0


def test_cycle_position_rising_market_at_45_degrees():
    g, v = _cycle_point(45)
    result = classify_property_cycle_position(g, v)
    assert result["position"] == "rising_market"


def test_cycle_position_approaching_peak_at_90_degrees():
    g, v = _cycle_point(90)
    result = classify_property_cycle_position(g, v)
    assert result["position"] == "approaching_peak"


def test_cycle_position_peak_at_135_degrees():
    g, v = _cycle_point(135)
    result = classify_property_cycle_position(g, v)
    assert result["position"] == "peak_of_market"
    assert result["label"] == "Peak of Market"


def test_cycle_position_starting_to_decline_at_180_degrees():
    g, v = _cycle_point(180)
    result = classify_property_cycle_position(g, v)
    assert result["position"] == "starting_to_decline"


def test_cycle_position_declining_at_225_degrees():
    g, v = _cycle_point(225)
    result = classify_property_cycle_position(g, v)
    assert result["position"] == "declining_market"


def test_cycle_position_approaching_bottom_at_270_degrees():
    g, v = _cycle_point(270)
    result = classify_property_cycle_position(g, v)
    assert result["position"] == "approaching_bottom"


def test_cycle_position_bottom_at_315_degrees():
    g, v = _cycle_point(315)
    result = classify_property_cycle_position(g, v)
    assert result["position"] == "bottom_of_market"


def test_cycle_position_confidence_scales_with_signal_strength():
    weak = classify_property_cycle_position(0.05, 0.05)
    strong = classify_property_cycle_position(1.0, 1.0)
    assert weak["confidence"] < strong["confidence"]
    assert strong["confidence"] == 1.0


def test_cycle_position_none_when_growth_missing():
    result = classify_property_cycle_position(None, 0.5)
    assert result == {"position": None, "label": None, "angle_degrees": None, "confidence": None}


def test_cycle_position_none_when_velocity_missing():
    result = classify_property_cycle_position(0.5, None)
    assert result == {"position": None, "label": None, "angle_degrees": None, "confidence": None}


def test_cycle_position_none_when_both_zero():
    result = classify_property_cycle_position(0.0, 0.0)
    assert result["position"] is None
