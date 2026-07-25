"""In-house momentum signals derived only from data we already ingest
ourselves (PropRadar sold listings + monthly suburb-market snapshots) — our
PropRadar plan tier ("hobby") returns 403 on market_cycle/price_history/
heat_history/rankings, so every "momentum" signal has to be computed
in-house rather than read off a gated endpoint. See
docs/IMPROVEMENT_PLAN_FOR_CLAUDE_CODE.md Phase 1 for the full rationale.

Every function here takes plain values (no SQLAlchemy rows), so it's
testable without a DB and reusable from both the suburb report and
rankings. DB-fetch wrappers live in app/services/momentum_service.py.
"""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from statistics import median
from typing import Any, Optional

_VELOCITY_HISTORY_MONTHS = 24  # 2 years — enough for a sparkline; matches the sold-ingest's cost-controlled --months 24 default (see CLAUDE.md)

# Years-back windows we can actually derive from our own sold data: skip qtr
# (too noisy off a suburb-level median with a handful of sales) and 10y
# (exceeds propradar_sold_loader's default 5-year --months window).
_GROWTH_WINDOW_YEARS = (1, 3, 5)
_MIN_SALES_FOR_MEDIAN = 3  # below this, a window's median is too noisy to report as a growth input

# Coarse mapping onto PropRadar's own house-vs-unit split (the fields we're
# backfilling), matching property_market_service.py's normalized property_type
# values. Townhouse/villa/duplex/etc. don't map cleanly to either bucket, so
# they're excluded from derived growth entirely rather than guessed into one.
_HOUSE_TYPES = frozenset({"house"})
_UNIT_TYPES = frozenset({"apartment", "unit", "flat"})


def _month_key(iso_date: Optional[str]) -> Optional[str]:
    """'2026-06-29' -> '2026-06'; None for missing/unparseable input."""
    if not iso_date or len(iso_date) < 7:
        return None
    return iso_date[:7]


def _last_n_month_keys(as_of: date, n: int) -> list[str]:
    """The n calendar-month keys ending at (and including) as_of's month,
    oldest first — e.g. as_of=2026-07-15, n=3 -> ['2026-05','2026-06','2026-07']."""
    keys = []
    year, month = as_of.year, as_of.month
    for _ in range(n):
        keys.append(f"{year:04d}-{month:02d}")
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(keys))


def compute_sale_velocity(sold_dates: list[str], *, as_of: date | None = None) -> dict[str, Any]:
    """Monthly sale counts (oldest to newest, capped at 2 years) plus a
    rolling trend: sales in the most recent 3 calendar months vs the 3
    months before that, as a % change. More transactions closing is a
    classic early-heat signal — rising demand pressure showing up before
    it's obvious in asking prices.

    Args:
        sold_dates: flat list of ISO 'YYYY-MM-DD' sold_date strings (one per
            sale, property_sales.sold_date as-is). Unparseable/missing
            entries are skipped rather than raising.
        as_of: the "today" the 3mo/3mo windows are anchored to — defaults to
            the current UTC date. Anchoring to wall-clock time (rather than
            "the most recent month with any data") is deliberate: a suburb
            that has genuinely gone quiet should show a recent count of 0,
            not silently skip forward to whenever it last had a sale.

    Returns:
        {
          "monthly_counts": [{"period": "2025-07", "count": 3}, ...],
          "recent_3mo_count": int,
          "prior_3mo_count": int,
          "trend_pct": float | None,  # % change, recent vs prior; None when
                                       # prior_3mo_count is 0 (a % change off
                                       # zero is undefined, not "infinite")
        }
    """
    as_of = as_of or datetime.now(timezone.utc).date()

    counts: dict[str, int] = {}
    for sold_date in sold_dates:
        key = _month_key(sold_date)
        if key is None:
            continue
        counts[key] = counts.get(key, 0) + 1

    all_months = sorted(counts.keys())[-_VELOCITY_HISTORY_MONTHS:]
    monthly_counts = [{"period": period, "count": counts[period]} for period in all_months]

    last_6_months = _last_n_month_keys(as_of, 6)
    prior_3_months, recent_3_months = last_6_months[:3], last_6_months[3:]
    recent_count = sum(counts.get(p, 0) for p in recent_3_months)
    prior_count = sum(counts.get(p, 0) for p in prior_3_months)

    trend_pct = round((recent_count - prior_count) / prior_count * 100, 1) if prior_count else None

    return {
        "monthly_counts": monthly_counts,
        "recent_3mo_count": recent_count,
        "prior_3mo_count": prior_count,
        "trend_pct": trend_pct,
    }


def _shift_months(d: date, months_back: int) -> date:
    """`d` shifted back by `months_back` whole months, day fixed at 1 (only
    year/month granularity matters — callers feed this into
    `_last_n_month_keys`)."""
    total = d.year * 12 + (d.month - 1) - months_back
    year, month = divmod(total, 12)
    return date(year, month + 1, 1)


def _prices_by_month(sales: list[dict[str, Any]]) -> dict[str, list[int]]:
    by_month: dict[str, list[int]] = {}
    for sale in sales:
        key = _month_key(sale.get("sold_date"))
        price = sale.get("sold_price")
        if key is None or price is None:
            continue
        by_month.setdefault(key, []).append(price)
    return by_month


def _window_median(by_month: dict[str, list[int]], keys: list[str]) -> Optional[float]:
    prices = [p for k in keys for p in by_month.get(k, [])]
    if len(prices) < _MIN_SALES_FOR_MEDIAN:
        return None
    return median(prices)


def compute_derived_growth(sales: list[dict[str, Any]], *, as_of: date | None = None) -> dict[str, Any]:
    """Median-sold-price growth per house/unit and 1y/3y/5y window, computed
    from our own property_sales — a fallback for wherever PropRadar's own
    SuburbMarketStats.growth_* is null (WS1 research found this true for
    40-59% of suburbs at our plan tier).

    Method: compare the median sold price over the trailing 12 months to the
    median sold price over the 12-month window ending N years earlier. This
    is a naive period-median comparison, not a repeat-sales or hedonic
    index — it can be skewed by a shift in the mix of what sold in either
    window (e.g. more large houses selling this year than last). Treat it as
    a directional proxy, not a precise growth rate; that's why it's only
    ever used to fill a gap, never to override a real PropRadar figure.

    Args:
        sales: list of dicts with `sold_date` (ISO 'YYYY-MM-DD'), `sold_price`,
            and `property_type` (matches property_sales' normalized lowercase
            values, e.g. "house"/"apartment"/"unit"/"flat"/"townhouse"/...).
        as_of: anchor date for the trailing-12-months window — defaults to
            the current UTC date.

    Returns a flat dict of growth_{house,unit}_{1,3,5}y_pct -> float | None
    (None when either window doesn't have enough sales, or the property-type
    bucket doesn't apply — e.g. no unit sales at all in this SA2).
    """
    as_of = as_of or datetime.now(timezone.utc).date()

    house_by_month = _prices_by_month(
        [s for s in sales if (s.get("property_type") or "").lower() in _HOUSE_TYPES]
    )
    unit_by_month = _prices_by_month(
        [s for s in sales if (s.get("property_type") or "").lower() in _UNIT_TYPES]
    )

    recent_keys = _last_n_month_keys(as_of, 12)

    result: dict[str, Any] = {}
    for label, by_month in (("house", house_by_month), ("unit", unit_by_month)):
        recent_median = _window_median(by_month, recent_keys)
        for years in _GROWTH_WINDOW_YEARS:
            comparison_keys = _last_n_month_keys(_shift_months(as_of, years * 12), 12)
            comparison_median = _window_median(by_month, comparison_keys)

            pct = None
            if recent_median is not None and comparison_median:
                pct = round((recent_median / comparison_median - 1) * 100, 1)
            result[f"growth_{label}_{years}y_pct"] = pct

    return result


# Value at/above which a component is treated as "abundant supply" (score
# floors to 0) — below these thresholds scarcity ramps up linearly to 100 at
# zero. Originally set from real-estate-market rules of thumb (a sub-3-month
# inventory is a classic "seller's market" signal) rather than our own data —
# that badly overstated scarcity in practice (median scarcity_score came out
# 72/100 across 2,723 real suburbs, with 76% reading "tight supply"). Each
# ceiling is now set to 2x the actual median of its raw input across that same
# dataset (2026-07 snapshot), so a suburb sitting exactly at the market's
# median scores ~50 on that component instead of ~85. Re-derive periodically
# as coverage/season shifts the underlying distribution — see
# docs/IMPROVEMENT_PLAN_FOR_CLAUDE_CODE.md's data-analysis findings for the
# methodology.
_STOCK_ON_MARKET_CEILING_PCT = 0.7  # % of dwelling stock currently listed for sale (was 3.0; real median was 0.355)
_INVENTORY_MONTHS_CEILING = 4.75  # months of stock at the current sales pace (was 6.0; real median was 2.375)
_APPROVALS_PER_1000_CEILING = 6.8  # new dwellings approved per 1,000 residents in the last year (was 15.0; real median was 3.38)

_SCARCITY_WEIGHTS = {
    "stock_on_market_score": 0.35,
    "inventory_months_score": 0.35,
    "building_approvals_score": 0.30,
}


def _scarcity_subscore(value: Optional[float], ceiling: float) -> Optional[float]:
    """0 (abundant — value >= ceiling) to 100 (scarce — value == 0), linear,
    clamped. None passes through (input not available)."""
    if value is None or value < 0:
        return None
    return round(max(0.0, min(100.0, (1 - value / ceiling) * 100)), 1)


def _avg_available(*values: Optional[float]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def compute_supply_scarcity(
    *,
    stock_on_market_pct_house: Optional[float] = None,
    stock_on_market_pct_unit: Optional[float] = None,
    inventory_months_house: Optional[float] = None,
    inventory_months_unit: Optional[float] = None,
    building_approvals_1yr: Optional[int] = None,
    population: Optional[int] = None,
) -> dict[str, Any]:
    """0-100 supply-scarcity score: how tight the current for-sale supply
    is, from three angles (lower supply -> higher score):

      - stock-on-market %: share of dwelling stock currently listed for
        sale (house/unit averaged where both present) — PropRadar's own
        market_dynamics figures, already ingested.
      - inventory months: months of stock at the current sales pace
        (house/unit averaged) — also already-ingested PropRadar data.
      - building approvals per 1,000 residents in the last year: the
        forward-looking new-supply pipeline (ABS building_approvals_1yr /
        census population) — the only one of the three that's structural
        rather than a live market snapshot.

    Weighted 35% stock-on-market + 35% inventory-months + 30% building
    approvals — the two live market signals outweigh the slower-moving
    approvals pipeline slightly, but approvals still counts since it's the
    only forward-looking input of the three.

    Each component is independently optional — a suburb missing one input
    (e.g. no building_approvals_1yr yet) still gets a score from whichever
    components ARE available, reweighted over just those.
    `scarcity_score` is None only when every single input is missing.
    """
    stock_pct = _avg_available(stock_on_market_pct_house, stock_on_market_pct_unit)
    inventory = _avg_available(inventory_months_house, inventory_months_unit)
    approvals_per_1000 = (
        building_approvals_1yr / population * 1000
        if building_approvals_1yr is not None and population
        else None
    )

    components = {
        "stock_on_market_score": _scarcity_subscore(stock_pct, _STOCK_ON_MARKET_CEILING_PCT),
        "inventory_months_score": _scarcity_subscore(inventory, _INVENTORY_MONTHS_CEILING),
        "building_approvals_score": _scarcity_subscore(approvals_per_1000, _APPROVALS_PER_1000_CEILING),
    }

    available = {k: v for k, v in components.items() if v is not None}
    if available:
        weight_sum = sum(_SCARCITY_WEIGHTS[k] for k in available)
        scarcity_score = round(sum(v * _SCARCITY_WEIGHTS[k] for k, v in available.items()) / weight_sum, 1)
    else:
        scarcity_score = None

    return {
        "scarcity_score": scarcity_score,
        "components": components,
    }


# momentum_score >= this -> "accelerating"; <= this -> "cooling"; anything in
# between -> "steady". Originally a symmetric +/-15, picked without data —
# that badly over-called "accelerating" (82% of 2,723 real suburbs cleared
# it, since the old scarcity-score bug also fed this composite a skewed
# input; see the scarcity ceiling comment above). These are now the actual
# top/bottom quartile of momentum_score across that same dataset (2026-07
# snapshot, post scarcity-fix) — asymmetric on purpose, since the underlying
# market was broadly rising (median growth +9.8%), not because of a
# remaining calibration error. Produces a ~25/49/25 accelerating/steady/
# cooling split. Re-derive periodically the same way as the scarcity
# ceilings above.
_MOMENTUM_ACCELERATING_THRESHOLD = 35.0
_MOMENTUM_COOLING_THRESHOLD = -7.0

_MOMENTUM_WEIGHTS = {
    "sale_velocity": 0.30,
    "growth": 0.25,
    "supply_scarcity": 0.25,
    "heat_score": 0.20,
}


def _clamp_signal(value: float, scale: float) -> float:
    """value/scale clamped to [-1, 1], rounded to 3dp to avoid float noise
    like 0.37599999999999995 leaking into the API response."""
    return round(max(-1.0, min(1.0, value / scale)), 3)


def compute_momentum(
    *,
    sale_velocity_trend_pct: Optional[float] = None,
    growth_house_1y_pct: Optional[float] = None,
    growth_unit_1y_pct: Optional[float] = None,
    scarcity_score: Optional[float] = None,
    heat_score_house: Optional[float] = None,
    heat_score_unit: Optional[float] = None,
) -> dict[str, Any]:
    """Classifies a suburb as accelerating / steady / cooling — the in-house
    substitute for PropRadar's gated market_cycle endpoint — from four
    already-computed signals, each converted to a -1 (cooling) .. +1
    (accelerating) direction before being weighted together:

      - sale velocity trend (compute_sale_velocity's trend_pct): +/-50
        percentage points maps to the full +/-1 range.
      - price growth (growth_house_1y_pct/growth_unit_1y_pct, averaged
        where both given — pass in either PropRadar's own figure or
        compute_derived_growth's fallback, caller's choice): +/-20% maps
        to +/-1.
      - supply scarcity (compute_supply_scarcity's 0-100 scarcity_score):
        50 is treated as neutral, 0/100 as the extremes.
      - PropRadar's own heat_score_house/unit (0-100, averaged): same
        50-as-neutral treatment as scarcity.

    Weighted 30% sale velocity + 25% growth + 25% scarcity + 20% heat score
    — sale velocity leads because it's the most responsive of the four
    (this quarter's transaction count vs last quarter's); heat score trails
    because it's PropRadar's own black-box figure we can't audit or derive
    ourselves.

    Like compute_supply_scarcity, a missing component is excluded and the
    remaining weights renormalized (not treated as zero/neutral) — `phase`
    is None only when every single input is missing.

    Returns:
        {
          "phase": "accelerating" | "steady" | "cooling" | None,
          "momentum_score": float | None,  # -100 (cooling) .. +100 (accelerating)
          "components": {
            "sale_velocity": {"trend_pct": .., "signal": ..},
            "growth": {"growth_pct": .., "signal": ..},
            "supply_scarcity": {"scarcity_score": .., "signal": ..},
            "heat_score": {"value": .., "signal": ..},
          },
        }
    """
    growth_pct = _avg_available(growth_house_1y_pct, growth_unit_1y_pct)
    heat_score = _avg_available(heat_score_house, heat_score_unit)
    if growth_pct is not None:
        growth_pct = round(growth_pct, 2)
    if heat_score is not None:
        heat_score = round(heat_score, 2)

    signals: dict[str, Optional[float]] = {
        "sale_velocity": _clamp_signal(sale_velocity_trend_pct, 50.0) if sale_velocity_trend_pct is not None else None,
        "growth": _clamp_signal(growth_pct, 20.0) if growth_pct is not None else None,
        "supply_scarcity": _clamp_signal(scarcity_score - 50.0, 50.0) if scarcity_score is not None else None,
        "heat_score": _clamp_signal(heat_score - 50.0, 50.0) if heat_score is not None else None,
    }

    components = {
        "sale_velocity": {"trend_pct": sale_velocity_trend_pct, "signal": signals["sale_velocity"]},
        "growth": {"growth_pct": growth_pct, "signal": signals["growth"]},
        "supply_scarcity": {"scarcity_score": scarcity_score, "signal": signals["supply_scarcity"]},
        "heat_score": {"value": heat_score, "signal": signals["heat_score"]},
    }

    available = {k: v for k, v in signals.items() if v is not None}
    if available:
        weight_sum = sum(_MOMENTUM_WEIGHTS[k] for k in available)
        composite = sum(v * _MOMENTUM_WEIGHTS[k] for k, v in available.items()) / weight_sum
        momentum_score = round(composite * 100, 1)
        if momentum_score >= _MOMENTUM_ACCELERATING_THRESHOLD:
            phase = "accelerating"
        elif momentum_score <= _MOMENTUM_COOLING_THRESHOLD:
            phase = "cooling"
        else:
            phase = "steady"
    else:
        momentum_score = None
        phase = None

    return {
        "phase": phase,
        "momentum_score": momentum_score,
        "components": components,
    }


# A suburb whose neighbors are STRICTLY majority-accelerating (or
# majority-cooling) gets flagged with a spillover signal — a 50/50 split is
# a tie, not a majority for either side, so it deliberately reports no
# signal rather than arbitrarily favoring whichever phase is checked first.
# 50% is a simple, interpretable bar —
# not tuned to the exact national base rate (~27% accelerating as of the
# 2026-07 snapshot), but validated against it: across that same dataset,
# accelerating suburbs' neighbors were accelerating 41.3% of the time vs a
# 27.4% base rate (1.51x lift), and cooling suburbs' neighbors were cooling
# 34.2% of the time vs a 22.6% base rate (also 1.51x) — a real, roughly
# symmetric spatial clustering effect, not noise. Needs at least 2 neighbors
# with known momentum to report a signal at all — one neighbor is too small
# a sample to call "surrounded by" anything.
_NEIGHBORHOOD_SIGNAL_THRESHOLD_PCT = 50.0
_NEIGHBORHOOD_MIN_KNOWN_NEIGHBORS = 2


def summarize_neighborhood_momentum(neighbor_phases: list[Optional[str]]) -> dict[str, Any]:
    """Roll up neighboring SA2s' momentum phases (from compute_momentum,
    one per adjacent SA2 — see SA2Region.adjacent_sa2_codes) into a spatial
    "ripple" signal: is this suburb surrounded by suburbs that are
    themselves heating up or cooling down? The classic early-hotspot
    pattern — a suburb next to already-accelerating suburbs is more likely
    to accelerate itself — a spillover effect confirmed in this dataset
    (see threshold comment above), not just a hypothesis.

    Args:
        neighbor_phases: one entry per adjacent SA2 — "accelerating" |
            "steady" | "cooling" | None (None where that neighbor has no
            momentum data yet, e.g. no PropRadar coverage).

    Returns:
        {
          "total_neighbors": int,  # neighbors with a known phase
          "counts": {"accelerating": int, "steady": int, "cooling": int},
          "accelerating_pct": float | None,
          "cooling_pct": float | None,
          "signal": "surrounded_by_acceleration" | "surrounded_by_cooling" | None,
        }
    """
    known = [p for p in neighbor_phases if p is not None]
    counts = {"accelerating": 0, "steady": 0, "cooling": 0}
    for phase in known:
        if phase in counts:
            counts[phase] += 1

    total = len(known)
    if total == 0:
        accelerating_pct = None
        cooling_pct = None
    else:
        accelerating_pct = round(counts["accelerating"] / total * 100, 1)
        cooling_pct = round(counts["cooling"] / total * 100, 1)

    signal = None
    if total >= _NEIGHBORHOOD_MIN_KNOWN_NEIGHBORS:
        if accelerating_pct > _NEIGHBORHOOD_SIGNAL_THRESHOLD_PCT:
            signal = "surrounded_by_acceleration"
        elif cooling_pct > _NEIGHBORHOOD_SIGNAL_THRESHOLD_PCT:
            signal = "surrounded_by_cooling"

    return {
        "total_neighbors": total,
        "counts": counts,
        "accelerating_pct": accelerating_pct,
        "cooling_pct": cooling_pct,
        "signal": signal,
    }


# Split points for the growth/yield quadrant — the real median house 1yr
# growth (9.6%) and median gross house yield (3.62%) across 1,271 real
# suburbs with both figures present (2026-07 snapshot). Using the actual
# median rather than a round number means the four quadrants come out
# close to evenly sized by construction, which is the point of a quadrant
# split — see docs/IMPROVEMENT_PLAN_FOR_CLAUDE_CODE.md's data-analysis
# findings. Re-derive periodically the same way as the momentum/scarcity
# thresholds above.
_QUADRANT_GROWTH_MEDIAN_PCT = 9.6
_QUADRANT_YIELD_MEDIAN_PCT = 3.62

_QUADRANT_LABELS = {
    "hot": "Hot — growth and yield both above the current market median",
    "growth_play": "Growth play — priced for capital gain, yield below median",
    "cash_flow_play": "Cash-flow play — steady income, growth below median",
    "avoid": "Neither growth nor yield is clearing the market median right now",
}


def classify_growth_yield_quadrant(
    growth_house_1y_pct: Optional[float], gross_yield_house_pct: Optional[float]
) -> dict[str, Any]:
    """Classic investor quadrant: split suburbs on house price growth and
    rental yield, both relative to the current market median (not a fixed
    absolute bar — a "high" yield today may not be high in five years).
    `quadrant` is a stable key for filtering/grouping; `label` is the
    display string. Returns both None when either input is missing —
    happens for suburbs with a PropRadar median but no yield data, or vice
    versa; a quadrant needs both axes to mean anything.
    """
    if growth_house_1y_pct is None or gross_yield_house_pct is None:
        return {"quadrant": None, "label": None}

    high_growth = growth_house_1y_pct >= _QUADRANT_GROWTH_MEDIAN_PCT
    high_yield = gross_yield_house_pct >= _QUADRANT_YIELD_MEDIAN_PCT

    if high_growth and high_yield:
        quadrant = "hot"
    elif high_growth:
        quadrant = "growth_play"
    elif high_yield:
        quadrant = "cash_flow_play"
    else:
        quadrant = "avoid"

    return {"quadrant": quadrant, "label": _QUADRANT_LABELS[quadrant]}


# Thresholds behind the Key Insight card's investor verdict + stat tiles.
# Growth: >3%/yr is roughly "beating inflation", <0% is an outright decline.
# Yield: 4%+ gross is a commonly-cited "solid" investor yield in AU capital
# cities; under 2.5% is thin (heavily capital-growth-dependent). Scarcity/
# days-on-market thresholds match compute_supply_scarcity's own scale and a
# standard real-estate "under 3 weeks = seller's market" rule of thumb.
_GROWTH_POSITIVE_PCT = 3.0
_GROWTH_NEGATIVE_PCT = 0.0
_YIELD_POSITIVE_PCT = 4.0
_YIELD_NEGATIVE_PCT = 2.5
_SCARCITY_POSITIVE = 60.0
_SCARCITY_NEGATIVE = 30.0
_DOM_POSITIVE_DAYS = 21.0
_DOM_NEGATIVE_DAYS = 45.0


def _tone_above_below(value: Optional[float], positive_at: float, negative_at: float) -> str:
    """'positive' if value clears the positive threshold, 'negative' if it's
    at/below the negative threshold, else 'neutral' (including missing data).
    Assumes positive_at > negative_at (higher is better)."""
    if value is None:
        return "neutral"
    if value >= positive_at:
        return "positive"
    if value <= negative_at:
        return "negative"
    return "neutral"


def _tone_below_above(value: Optional[float], positive_at: float, negative_at: float) -> str:
    """Same as `_tone_above_below` but for a lower-is-better metric (e.g.
    days on market): 'positive' at/below `positive_at`, 'negative' at/above
    `negative_at`. Assumes positive_at < negative_at."""
    if value is None:
        return "neutral"
    if value <= positive_at:
        return "positive"
    if value >= negative_at:
        return "negative"
    return "neutral"


def generate_investment_snapshot(
    *,
    momentum_phase: Optional[str] = None,
    growth_house_1y_pct: Optional[float] = None,
    gross_yield_house_pct: Optional[float] = None,
    scarcity_score: Optional[float] = None,
    days_on_market_house: Optional[float] = None,
) -> dict[str, Any]:
    """The Key Insight card's content: a terse, data-backed verdict plus a
    handful of stat tiles an investor would actually check first — momentum,
    price growth, rental yield, supply scarcity, days on market. Built from
    signals already computed elsewhere (compute_momentum, compute_supply_scarcity)
    plus raw PropRadar suburb-stat fields, rather than the census-derived
    `investment_score` composite the old insight text was built from.

    Every input is independently optional — whatever's missing just shows as
    "—" in its tile and is left out of the verdict, rather than blocking the
    whole card. Returns `verdict=None` only when literally everything is
    missing (caller should fall back to the census-based insight text).
    """
    fragments: list[str] = []

    if momentum_phase == "accelerating":
        fragments.append("Momentum accelerating")
    elif momentum_phase == "cooling":
        fragments.append("Momentum cooling")
    elif momentum_phase == "steady":
        fragments.append("Momentum steady")

    if growth_house_1y_pct is not None:
        if growth_house_1y_pct > _GROWTH_POSITIVE_PCT:
            fragments.append(f"Prices up {growth_house_1y_pct:.1f}% over the past year")
        elif growth_house_1y_pct < _GROWTH_NEGATIVE_PCT:
            fragments.append(f"Prices down {abs(growth_house_1y_pct):.1f}% over the past year")
        else:
            fragments.append("Prices roughly flat over the past year")

    if gross_yield_house_pct is not None:
        if gross_yield_house_pct >= _YIELD_POSITIVE_PCT:
            fragments.append(f"strong {gross_yield_house_pct:.1f}% rental yield")
        elif gross_yield_house_pct < _YIELD_NEGATIVE_PCT:
            fragments.append(f"thin {gross_yield_house_pct:.1f}% rental yield")

    if scarcity_score is not None:
        if scarcity_score >= _SCARCITY_POSITIVE:
            fragments.append("supply is tight")
        elif scarcity_score <= _SCARCITY_NEGATIVE:
            fragments.append("supply is abundant")

    if days_on_market_house is not None:
        if days_on_market_house <= _DOM_POSITIVE_DAYS:
            fragments.append(f"selling fast ({days_on_market_house:.0f} days on market)")
        elif days_on_market_house >= _DOM_NEGATIVE_DAYS:
            fragments.append(f"selling slowly ({days_on_market_house:.0f} days on market)")

    verdict = "; ".join(f[0].upper() + f[1:] for f in fragments) if fragments else None

    highlights = [
        {
            "label": "Momentum",
            "format": "text",
            "value": momentum_phase.capitalize() if momentum_phase else None,
            "tone": {"accelerating": "positive", "cooling": "negative"}.get(momentum_phase, "neutral"),
        },
        {
            "label": "1yr Price Growth",
            "format": "pct",
            "value": growth_house_1y_pct,
            "tone": _tone_above_below(growth_house_1y_pct, _GROWTH_POSITIVE_PCT, _GROWTH_NEGATIVE_PCT),
        },
        {
            "label": "Gross Rental Yield",
            "format": "rate",
            "value": gross_yield_house_pct,
            "tone": _tone_above_below(gross_yield_house_pct, _YIELD_POSITIVE_PCT, _YIELD_NEGATIVE_PCT),
        },
        {
            "label": "Supply Scarcity",
            "format": "score",
            "value": scarcity_score,
            "tone": _tone_above_below(scarcity_score, _SCARCITY_POSITIVE, _SCARCITY_NEGATIVE),
        },
        {
            "label": "Days on Market",
            "format": "days",
            "value": days_on_market_house,
            "tone": _tone_below_above(days_on_market_house, _DOM_POSITIVE_DAYS, _DOM_NEGATIVE_DAYS),
        },
    ]

    return {
        "verdict": verdict,
        "highlights": highlights,
    }


# The 8-position property cycle clock (Herron Todd White's is the best-known
# version — the one the reference screenshot for this feature was showing).
# PropRadar's own market_cycle endpoint is gated at our plan tier (see this
# module's docstring), so this is derived entirely from two signals we
# already compute in compute_momentum: the growth signal (price direction)
# and the sale-velocity signal (transaction-volume direction).
#
# The two aren't interchangeable — volume is a well-established LEADING
# indicator for price turning points (buyer activity historically picks up
# before prices bottom, and cools before prices peak). Modelling volume as
# leading price by a quarter-cycle (90°) and price growth as a sine wave of
# cycle angle θ gives growth ≈ sin(θ), velocity ≈ cos(θ) — which inverts
# cleanly to θ = atan2(growth_signal, velocity_signal). Walking θ around the
# circle in 45° steps reproduces the clock's own order exactly:
#   θ=0°(g=0,v=+1) start of recovery → 45°(g=+,v=+) rising → 90°(g=+1,v=0)
#   approaching peak → 135°(g=+,v=-) peak → 180°(g=0,v=-1) starting to
#   decline → 225°(g=-,v=-) declining → 270°(g=-1,v=0) approaching bottom
#   → 315°(g=-,v=+) bottom → back to 0°.
# This is a model, not a measurement — treat `confidence` (how far the
# signal sits from dead centre) as a caveat on how much to read into it,
# especially early on with only ~9-12 months of sold-listing history behind
# the velocity signal.
_CYCLE_POSITIONS = [
    "start_of_recovery",
    "rising_market",
    "approaching_peak",
    "peak_of_market",
    "starting_to_decline",
    "declining_market",
    "approaching_bottom",
    "bottom_of_market",
]

_CYCLE_LABELS = {
    "start_of_recovery": "Start of Recovery",
    "rising_market": "Rising Market",
    "approaching_peak": "Approaching Peak of Market",
    "peak_of_market": "Peak of Market",
    "starting_to_decline": "Starting to Decline",
    "declining_market": "Declining Market",
    "approaching_bottom": "Approaching Bottom of Market",
    "bottom_of_market": "Bottom of Market",
}


def classify_property_cycle_position(
    growth_signal: Optional[float], velocity_signal: Optional[float]
) -> dict[str, Any]:
    """Places a suburb on the 8-position property cycle clock from its
    already-computed growth and sale-velocity signals (compute_momentum's
    `components.growth.signal` / `components.sale_velocity.signal`, each
    already on a -1..+1 scale) — see the module-level comment above for the
    derivation. Returns an all-None row when either signal is missing (most
    commonly: no property_sales data for this SA2, so no velocity signal) or
    both are exactly zero (a dead-centre point has no defined angle) —
    honest "not enough signal" rather than a fabricated position.

    Returns:
        {
          "position": "start_of_recovery" | "rising_market" | "approaching_peak" |
                       "peak_of_market" | "starting_to_decline" | "declining_market" |
                       "approaching_bottom" | "bottom_of_market" | None,
          "label": str | None,          # human-readable form of `position`
          "angle_degrees": float | None,  # 0-360, mostly useful for debugging/tests
          "confidence": float | None,    # 0-1, distance from dead-centre — low means the signal is weak/ambiguous
        }
    """
    if growth_signal is None or velocity_signal is None:
        return {"position": None, "label": None, "angle_degrees": None, "confidence": None}
    if growth_signal == 0 and velocity_signal == 0:
        return {"position": None, "label": None, "angle_degrees": None, "confidence": None}

    angle = math.degrees(math.atan2(growth_signal, velocity_signal)) % 360
    index = round(angle / 45) % 8
    position = _CYCLE_POSITIONS[index]
    confidence = round(min(1.0, math.hypot(growth_signal, velocity_signal) / math.sqrt(2)), 2)

    return {
        "position": position,
        "label": _CYCLE_LABELS[position],
        "angle_degrees": round(angle, 1),
        "confidence": confidence,
    }
