"""Fetch PropRadar's suburb-level market stats for the suburb report.

A SA2 can map to more than one row here (a combined SA2 like "Rochedale -
Burbank" has one row each for Rochedale and Burbank — see
suburb_market_stats_loader.py) — returned as a list, one entry per real
suburb, rather than blended into a single average that could mask real
differences between the parts.

The underlying table keeps one snapshot row per suburb PER CALENDAR MONTH
(see SuburbMarketStats.period), so both functions below need to reason
about "latest" vs "all" periods rather than assuming a single row per
suburb.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SuburbMarketStats

_FIELDS = [
    "suburb_name", "median_house_price", "median_unit_price",
    "median_house_rent_weekly", "median_unit_rent_weekly",
    "growth_house_1y_pct", "growth_house_3y_pct", "growth_house_5y_pct",
    "growth_unit_1y_pct", "growth_unit_3y_pct", "growth_unit_5y_pct",
    "gross_yield_house_pct", "gross_yield_unit_pct",
    "days_on_market_house", "days_on_market_unit",
    "vacancy_rate_pct", "sold_vs_asking_pct",
    "heat_score_house", "heat_score_unit",
    "sales_12mo_house", "sales_12mo_unit",
]

_RENTAL_FIELDS = [
    "period",
    "median_house_rent_weekly", "median_unit_rent_weekly",
    "gross_yield_house_pct", "gross_yield_unit_pct",
    "days_on_market_house", "days_on_market_unit",
    "vacancy_rate_pct",
]


async def fetch_suburb_market_stats(db: AsyncSession, sa2_code: str) -> List[Dict[str, Any]]:
    """Current snapshot per real suburb — the most recent period only, even
    though the table holds one row per suburb per month."""
    columns = [SuburbMarketStats.suburb_name, SuburbMarketStats.period] + [
        getattr(SuburbMarketStats, f) for f in _FIELDS if f != "suburb_name"
    ]
    stmt = select(*columns).where(SuburbMarketStats.sa2_code == sa2_code).order_by(
        SuburbMarketStats.suburb_name, SuburbMarketStats.period.desc()
    )
    rows = (await db.execute(stmt)).all()

    latest_by_suburb: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        record = dict(zip(["suburb_name", "period"] + [f for f in _FIELDS if f != "suburb_name"], row))
        suburb_name = record["suburb_name"]
        if suburb_name not in latest_by_suburb:
            record.pop("period")
            latest_by_suburb[suburb_name] = record

    return [latest_by_suburb[name] for name in sorted(latest_by_suburb)]


async def fetch_rental_market_history(db: AsyncSession, sa2_code: str) -> List[Dict[str, Any]]:
    """Month-over-month rental market history per real suburb — weekly rent,
    yield, days on market, and vacancy rate for house and unit, one entry
    per calendar month the loader has run. Only ever has one data point
    until the loader has been re-run in a later month (see
    suburb_market_stats_loader.py's period-keyed `id` scheme)."""
    columns = [SuburbMarketStats.suburb_name] + [getattr(SuburbMarketStats, f) for f in _RENTAL_FIELDS]
    stmt = select(*columns).where(SuburbMarketStats.sa2_code == sa2_code).order_by(
        SuburbMarketStats.suburb_name, SuburbMarketStats.period.asc()
    )
    rows = (await db.execute(stmt)).all()

    by_suburb: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        suburb_name = row[0]
        snapshot = dict(zip(_RENTAL_FIELDS, row[1:]))
        by_suburb.setdefault(suburb_name, []).append(snapshot)

    return [
        {"suburb_name": name, "history": by_suburb[name]}
        for name in sorted(by_suburb)
    ]
