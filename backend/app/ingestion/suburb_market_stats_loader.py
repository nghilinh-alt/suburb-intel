"""PropRadar suburb-level market stats loader.

Fetches PropRadar's own pre-computed suburb aggregate — medians, growth,
yields, market dynamics (days on market, sold-vs-asking%, vacancy), and
PropRadar's own demographics — and upserts onto `suburb_market_stats`.

Endpoint: GET /v1/suburbs/{state}/{suburb}
Authentication: X-API-Key header.

One call per real suburb (not per SA2 — reuses propradar_sold_loader.py's
`_split_suburb_parts`/`_STATE_MAP` so a combined SA2 like "Rochedale -
Burbank" gets a row each for Rochedale and Burbank), and the response is a
single object, not paginated — much cheaper than the /sold listings pull.

Response shape — VERIFIED against a real 200 response (2026-07-09, QLD/cleveland)
──────────────────────────────────────────────────────────────────────────────
{
  "suburb": "CLEVELAND", "state": "QLD", "postcode": 4163,
  "medians": {"house_price": 1280000, "unit_price": 865000,
              "house_weekly_rent": 795, "unit_weekly_rent": 630},
  "growth": {"house": {"qtr_pct": null, "1y_pct": 10.8, "3y_pct": 40,
                        "5y_pct": 84.7, "10y_pct": null},
             "unit": {...same shape...}},
  "yields": {"house_gross_pct": 3.23, "unit_gross_pct": 3.79},
  "market_dynamics": {"house_days_on_market": 15, "unit_days_on_market": 41,
                       "vacancy_rate_pct": 1.12, "house_inventory_months": 4.62,
                       "unit_inventory_months": 1.64, "house_stock_on_market_pct": 0.66,
                       "unit_stock_on_market_pct": 0.31, "sold_vs_asking_pct": 3.4,
                       "house_heat_score": 78, "unit_heat_score": null,
                       "house_sales_12mo": 262, "unit_sales_12mo": 148},
  "demographics": {"population": 15850, "median_age": 51,
                    "median_household_income": 1430, "owner_occupied_pct": 66.8,
                    "renter_pct": 29.4, "unemployment_rate_pct": 3.2,
                    "socioeconomic_score": 49},
  "location": {"distance_to_cbd_km": 24.6},
  "as_of": "2026-07-01T22:45:07.072Z",
  "locked_fields": {"livability": {...Starter+...}, "supply_demand": {...Pro+...},
                     "rent_trends": {...Pro+...}, "auction": {...Pro+...}}
}

Fields under `locked_fields` are plan-tier-gated (our key is on "hobby") and
never appear in the response body at all — not silently null, genuinely
absent. Everything mapped above (medians/growth/yields/market_dynamics/
demographics/location) IS available at hobby tier and was confirmed present.

Quota
─────
1 call per real suburb (no pagination) — a full national refresh (no scope
flags) costs ~3,642 calls, comfortably inside the 5,000/month plan quota.
Each row's `id` embeds the calendar-month period, so a suburb already
fetched this month is skipped unless --force; running again next month
inserts a NEW row rather than overwriting, building up the history the
Rental Market section charts month-over-month changes from.

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.suburb_market_stats                    # full national refresh
    python -m app.ingestion.suburb_market_stats --sa2-codes 301021007
    (API key is read from PROPRADAR_API_KEY env var)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import SA2Region, SuburbMarketStats
from app.ingestion.propradar_sold_loader import _STATE_MAP, _split_suburb_parts

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.propradar.com.au"
_REQUEST_DELAY = 0.5


@dataclass
class SuburbStatsLoadReport:
    suburbs_processed: int = 0
    suburbs_matched: int = 0
    suburbs_not_found: int = 0
    suburbs_skipped_fresh: int = 0
    api_calls: int = 0
    api_errors: int = 0

    def __str__(self) -> str:
        return (
            f"Suburbs processed: {self.suburbs_processed} | "
            f"Matched: {self.suburbs_matched} | "
            f"Not found: {self.suburbs_not_found} | "
            f"Skipped (already fresh this month): {self.suburbs_skipped_fresh} | "
            f"API calls used: {self.api_calls} | "
            f"API errors: {self.api_errors}"
        )


def _current_period() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _already_fetched(db: Session, stats_id: str) -> bool:
    """`stats_id` already embeds the calendar-month period, so existence of
    the row IS the freshness check — no separate date comparison needed."""
    return db.query(SuburbMarketStats.id).filter(SuburbMarketStats.id == stats_id).first() is not None


def load_suburb_market_stats(
    db: Session,
    api_key: str,
    *,
    state: str | None = None,
    suburb: str | None = None,
    sa2_codes: list[str] | None = None,
    force: bool = False,
) -> SuburbStatsLoadReport:
    """Fetch suburb-level market stats for SA2s matching the given scope.

    Args:
        db:        Synchronous SQLAlchemy session.
        api_key:   PropRadar API key.
        state:     If set, only process SA2s in this state.
        suburb:    If set, only process SA2s whose name matches this suburb.
        sa2_codes: If set, process exactly these SA2 codes (can span states).
        force:     Skip the monthly-freshness check and re-fetch regardless.

    Unlike propradar_sold_loader (which paginates and can burn budget
    unpredictably), this endpoint is a flat 1 call per real suburb — a full
    national run costs ~3,642 calls, comfortably inside the 5,000/month plan
    quota, so leaving all three scope args unset (full refresh) is intentional
    and safe rather than an accident to guard against.
    """
    report = SuburbStatsLoadReport()

    q = db.query(SA2Region.sa2_code, SA2Region.sa2_name, SA2Region.state)
    if state:
        q = q.filter(SA2Region.state == state)
    if sa2_codes:
        q = q.filter(SA2Region.sa2_code.in_(sa2_codes))
    elif suburb:
        q = q.filter(SA2Region.sa2_name.ilike(f"%{suburb}%"))
    sa2_rows = q.all()
    logger.info("Processing %d SA2s ...", len(sa2_rows))

    with httpx.Client(timeout=15.0) as client:
        headers = {"X-API-Key": api_key}
        for sa2_code, sa2_name, sa2_state in sa2_rows:
            pr_state = _STATE_MAP.get(sa2_state)
            if pr_state is None:
                logger.warning("Unknown state %s for SA2 %s — skipping", sa2_state, sa2_code)
                continue

            period = _current_period()
            for suburb_name in _split_suburb_parts(sa2_name):
                report.suburbs_processed += 1
                slug = suburb_name.lower().replace(" ", "-")
                stats_id = f"{pr_state}-{slug}-{period}"

                if not force and _already_fetched(db, stats_id):
                    logger.info("Skipping %s — already fetched this month", stats_id)
                    report.suburbs_skipped_fresh += 1
                    continue

                url = f"{_BASE_URL}/v1/suburbs/{pr_state}/{slug}"
                try:
                    resp = client.get(url, headers=headers)
                    report.api_calls += 1
                except httpx.RequestError as exc:
                    logger.warning("Request error for %s: %s", stats_id, exc)
                    report.api_errors += 1
                    continue

                time.sleep(_REQUEST_DELAY)

                if resp.status_code == 404:
                    report.suburbs_not_found += 1
                    continue
                if resp.status_code == 402:
                    raise RuntimeError(
                        "PropRadar returned 402 Payment Required — subscription expired."
                    )
                if resp.status_code == 401:
                    raise RuntimeError("PropRadar returned 401 Unauthorized — check PROPRADAR_API_KEY.")
                if resp.status_code == 403:
                    logger.warning("403 for %s (likely plan-tier gate): %s", stats_id, resp.text[:200])
                    report.api_errors += 1
                    continue
                if resp.status_code != 200:
                    logger.warning("Unexpected %d for %s: %s", resp.status_code, stats_id, resp.text[:200])
                    report.api_errors += 1
                    continue

                data = resp.json()
                stats = _parse_stats(data, stats_id, sa2_code, pr_state, suburb_name, period)
                db.merge(stats)
                db.commit()
                report.suburbs_matched += 1

    return report


def _g(d: dict | None, *keys: str):
    """Safe nested-dict getter — d.get(k1, {}).get(k2, {})... returns None
    on any missing hop instead of raising."""
    cur = d or {}
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
    return cur


def _parse_stats(data: dict, stats_id: str, sa2_code: str, state: str, suburb_name: str, period: str) -> SuburbMarketStats:
    as_of_str = data.get("as_of")
    as_of = None
    if as_of_str:
        try:
            as_of = datetime.fromisoformat(str(as_of_str).replace("Z", "+00:00"))
        except ValueError:
            as_of = None

    return SuburbMarketStats(
        id=stats_id,
        sa2_code=sa2_code,
        suburb_name=suburb_name,
        state=state,
        postcode=str(data["postcode"]) if data.get("postcode") is not None else None,
        period=period,
        median_house_price=_g(data, "medians", "house_price"),
        median_unit_price=_g(data, "medians", "unit_price"),
        median_house_rent_weekly=_g(data, "medians", "house_weekly_rent"),
        median_unit_rent_weekly=_g(data, "medians", "unit_weekly_rent"),
        growth_house_qtr_pct=_g(data, "growth", "house", "qtr_pct"),
        growth_house_1y_pct=_g(data, "growth", "house", "1y_pct"),
        growth_house_3y_pct=_g(data, "growth", "house", "3y_pct"),
        growth_house_5y_pct=_g(data, "growth", "house", "5y_pct"),
        growth_house_10y_pct=_g(data, "growth", "house", "10y_pct"),
        growth_unit_qtr_pct=_g(data, "growth", "unit", "qtr_pct"),
        growth_unit_1y_pct=_g(data, "growth", "unit", "1y_pct"),
        growth_unit_3y_pct=_g(data, "growth", "unit", "3y_pct"),
        growth_unit_5y_pct=_g(data, "growth", "unit", "5y_pct"),
        growth_unit_10y_pct=_g(data, "growth", "unit", "10y_pct"),
        gross_yield_house_pct=_g(data, "yields", "house_gross_pct"),
        gross_yield_unit_pct=_g(data, "yields", "unit_gross_pct"),
        days_on_market_house=_g(data, "market_dynamics", "house_days_on_market"),
        days_on_market_unit=_g(data, "market_dynamics", "unit_days_on_market"),
        vacancy_rate_pct=_g(data, "market_dynamics", "vacancy_rate_pct"),
        inventory_months_house=_g(data, "market_dynamics", "house_inventory_months"),
        inventory_months_unit=_g(data, "market_dynamics", "unit_inventory_months"),
        stock_on_market_pct_house=_g(data, "market_dynamics", "house_stock_on_market_pct"),
        stock_on_market_pct_unit=_g(data, "market_dynamics", "unit_stock_on_market_pct"),
        sold_vs_asking_pct=_g(data, "market_dynamics", "sold_vs_asking_pct"),
        heat_score_house=_g(data, "market_dynamics", "house_heat_score"),
        heat_score_unit=_g(data, "market_dynamics", "unit_heat_score"),
        sales_12mo_house=_g(data, "market_dynamics", "house_sales_12mo"),
        sales_12mo_unit=_g(data, "market_dynamics", "unit_sales_12mo"),
        pr_population=_g(data, "demographics", "population"),
        pr_median_age=_g(data, "demographics", "median_age"),
        pr_median_household_income=_g(data, "demographics", "median_household_income"),
        pr_owner_occupied_pct=_g(data, "demographics", "owner_occupied_pct"),
        pr_renter_pct=_g(data, "demographics", "renter_pct"),
        pr_unemployment_rate_pct=_g(data, "demographics", "unemployment_rate_pct"),
        pr_socioeconomic_score=_g(data, "demographics", "socioeconomic_score"),
        pr_distance_to_cbd_km=_g(data, "location", "distance_to_cbd_km"),
        as_of=as_of,
        fetched_at=datetime.now(timezone.utc),
    )
