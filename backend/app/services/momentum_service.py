"""Async DB-fetch wrappers around app.core.momentum's pure functions, for
the suburb report and (eventually) rankings.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.momentum import (
    compute_momentum,
    compute_sale_velocity,
    compute_supply_scarcity,
    summarize_neighborhood_momentum,
)
from app.db.models import ABSCEntensMetrics, PropertySale, SA2Region, SuburbMarketStats


async def fetch_sale_velocity(db: AsyncSession, sa2_code: str) -> Dict[str, Any]:
    """Sale velocity (monthly counts + 3mo-vs-3mo trend) for one SA2, from
    raw property_sales.sold_date. Empty history if no sold data has been
    ingested yet — compute_sale_velocity handles an empty list cleanly."""
    stmt = select(PropertySale.sold_date).where(
        PropertySale.sa2_code == sa2_code,
        PropertySale.sold_date.isnot(None),
    )
    sold_dates = [row[0] for row in (await db.execute(stmt)).all()]
    return compute_sale_velocity(sold_dates)


async def fetch_neighborhood_momentum(db: AsyncSession, sa2_code: str) -> Dict[str, Any]:
    """Momentum phase for every SA2 bordering this one (SA2Region's
    precomputed adjacent_sa2_codes), rolled up into a spillover signal via
    summarize_neighborhood_momentum. Each neighbor's phase is computed the
    same way as the suburb report's own (first real suburb under that SA2 —
    matches adjacency's SA2-level granularity, not the per-real-suburb split
    market_stats otherwise uses), from the same batch-fetched inputs to
    avoid N separate round-trips per neighbor.
    """
    region = await db.get(SA2Region, sa2_code)
    neighbor_codes: List[str] = (region.adjacent_sa2_codes or []) if region else []
    if not neighbor_codes:
        return summarize_neighborhood_momentum([])

    stats_stmt = (
        select(SuburbMarketStats)
        .where(SuburbMarketStats.sa2_code.in_(neighbor_codes))
        .order_by(SuburbMarketStats.sa2_code, SuburbMarketStats.period.desc())
    )
    stats_by_sa2: Dict[str, SuburbMarketStats] = {}
    for stats in (await db.execute(stats_stmt)).scalars().all():
        stats_by_sa2.setdefault(stats.sa2_code, stats)  # first hit per code = latest period (desc order)

    census_stmt = select(ABSCEntensMetrics).where(
        ABSCEntensMetrics.sa2_code.in_(neighbor_codes), ABSCEntensMetrics.year == 2021
    )
    census_by_sa2 = {c.sa2_code: c for c in (await db.execute(census_stmt)).scalars().all()}

    sold_stmt = select(PropertySale.sa2_code, PropertySale.sold_date).where(
        PropertySale.sa2_code.in_(neighbor_codes), PropertySale.sold_date.isnot(None)
    )
    sold_by_sa2: Dict[str, List[str]] = {}
    for code, sold_date in (await db.execute(sold_stmt)).all():
        sold_by_sa2.setdefault(code, []).append(sold_date)

    phases: List[Optional[str]] = []
    for code in neighbor_codes:
        stats = stats_by_sa2.get(code)
        if stats is None:
            phases.append(None)
            continue
        census = census_by_sa2.get(code)
        velocity = compute_sale_velocity(sold_by_sa2.get(code, []))
        scarcity = compute_supply_scarcity(
            stock_on_market_pct_house=stats.stock_on_market_pct_house,
            stock_on_market_pct_unit=stats.stock_on_market_pct_unit,
            inventory_months_house=stats.inventory_months_house,
            inventory_months_unit=stats.inventory_months_unit,
            building_approvals_1yr=census.building_approvals_1yr if census else None,
            population=census.population if census else None,
        )
        momentum = compute_momentum(
            sale_velocity_trend_pct=velocity["trend_pct"],
            growth_house_1y_pct=stats.growth_house_1y_pct,
            growth_unit_1y_pct=stats.growth_unit_1y_pct,
            scarcity_score=scarcity["scarcity_score"],
            heat_score_house=stats.heat_score_house,
            heat_score_unit=stats.heat_score_unit,
        )
        phases.append(momentum["phase"])

    return summarize_neighborhood_momentum(phases)
