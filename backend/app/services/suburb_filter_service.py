"""Multi-filter suburb search for the Search page's filter sidebar.

Combines SA2Region (location), ABSCEntensMetrics (census + Overture + ABS
derived columns), SuburbScore (investment/economic/demographic/etc.
composite scores from app.jobs.backfill_scores), and SuburbMarketStats
(PropRadar — price/rent/yield/vacancy/days-on-market, coverage varies by
suburb, see CLAUDE.md's refresh schedule) into one filterable, sortable,
paginated query.

PropRadar is the sole source for price/rent/yield/days-on-market — there is
no Domain API integration (removed; it was never actually connected, every
domain_* field was permanently null).

SuburbMarketStats has up to one row per real suburb per calendar month (see
that model's docstring), so a SA2 can have several rows — averaged per SA2
here for filtering purposes rather than picked/disambiguated, since this is
a coarse "does this suburb roughly meet the bar" filter, not the suburb
report's precise per-real-suburb breakdown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ABSCEntensMetrics, SA2Region, SuburbMarketStats, SuburbScore

_CENSUS_YEAR = 2021


@dataclass
class SuburbFilters:
    states: Optional[List[str]] = None
    max_distance_to_cbd_km: Optional[float] = None
    min_median_house_price: Optional[float] = None
    max_median_house_price: Optional[float] = None
    min_median_unit_price: Optional[float] = None
    max_median_unit_price: Optional[float] = None
    min_population: Optional[int] = None
    max_population: Optional[int] = None
    min_pop_growth_5yr_pct: Optional[float] = None
    min_median_income: Optional[int] = None
    max_median_income: Optional[int] = None
    min_median_rent_weekly: Optional[float] = None
    max_median_rent_weekly: Optional[float] = None
    min_owner_occupied_pct: Optional[float] = None
    max_owner_occupied_pct: Optional[float] = None
    max_social_housing_pct: Optional[float] = None
    max_unemployment_pct: Optional[float] = None
    min_seifa_irsd_decile: Optional[int] = None
    min_avg_school_icsea: Optional[float] = None
    max_days_on_market: Optional[float] = None
    min_investment_score: Optional[float] = None
    min_economic_score: Optional[float] = None
    min_demographic_score: Optional[float] = None
    min_gross_yield_house_pct: Optional[float] = None
    max_vacancy_rate_pct: Optional[float] = None
    momentum_phase: Optional[str] = None
    growth_yield_quadrant: Optional[str] = None
    min_scarcity_score: Optional[float] = None


_DEFAULT_SORT = "population"


@dataclass
class SuburbSearchPage:
    total_count: int
    results: List[Dict[str, Any]] = field(default_factory=list)


async def search_suburbs_filtered(
    db: AsyncSession,
    filters: SuburbFilters,
    *,
    sort_by: str = _DEFAULT_SORT,
    sort_dir: str = "desc",
    limit: int = 20,
    offset: int = 0,
) -> SuburbSearchPage:
    """Filter + sort + paginate suburbs. Returns the page of results plus the
    total count matching the filters (for "1-20 of N suburbs" headers)."""
    market_agg = (
        select(
            SuburbMarketStats.sa2_code,
            func.avg(SuburbMarketStats.median_house_price).label("avg_median_house_price"),
            func.avg(SuburbMarketStats.median_unit_price).label("avg_median_unit_price"),
            func.avg(SuburbMarketStats.days_on_market_house).label("avg_days_on_market_house"),
            func.avg(SuburbMarketStats.gross_yield_house_pct).label("avg_gross_yield_house_pct"),
            func.avg(SuburbMarketStats.vacancy_rate_pct).label("avg_vacancy_rate_pct"),
            func.avg(SuburbMarketStats.growth_house_1y_pct).label("avg_growth_house_1y_pct"),
            func.avg(SuburbMarketStats.heat_score_house).label("avg_heat_score_house"),
        )
        .group_by(SuburbMarketStats.sa2_code)
        .subquery()
    )

    base = (
        select(
            SA2Region.sa2_code,
            SA2Region.sa2_name,
            SA2Region.state,
            SA2Region.distance_to_cbd_km,
            ABSCEntensMetrics.population,
            ABSCEntensMetrics.median_income,
            ABSCEntensMetrics.median_rent_weekly,
            ABSCEntensMetrics.owners_pct,
            ABSCEntensMetrics.social_housing_pct,
            ABSCEntensMetrics.unemployment_pct,
            ABSCEntensMetrics.seifa_irsd_decile,
            ABSCEntensMetrics.avg_school_icsea,
            ABSCEntensMetrics.pop_growth_5yr,
            ABSCEntensMetrics.pop_growth_proj_pct,
            SuburbScore.investment_score,
            SuburbScore.economic_score,
            SuburbScore.demographic_score,
            SuburbScore.momentum_score,
            SuburbScore.momentum_phase,
            SuburbScore.growth_yield_quadrant,
            SuburbScore.neighborhood_signal,
            SuburbScore.scarcity_score,
            market_agg.c.avg_median_house_price,
            market_agg.c.avg_median_unit_price,
            market_agg.c.avg_days_on_market_house,
            market_agg.c.avg_gross_yield_house_pct,
            market_agg.c.avg_vacancy_rate_pct,
            market_agg.c.avg_growth_house_1y_pct,
            market_agg.c.avg_heat_score_house,
        )
        .select_from(SA2Region)
        .join(
            ABSCEntensMetrics,
            (ABSCEntensMetrics.sa2_code == SA2Region.sa2_code)
            & (ABSCEntensMetrics.year == _CENSUS_YEAR),
        )
        .outerjoin(SuburbScore, SuburbScore.sa2_code == SA2Region.sa2_code)
        .outerjoin(market_agg, market_agg.c.sa2_code == SA2Region.sa2_code)
    )

    base = _apply_filters(base, filters, market_agg)

    total_count = (await db.execute(
        select(func.count()).select_from(base.subquery())
    )).scalar_one()

    sortable_columns: Dict[str, Any] = {
        "population": ABSCEntensMetrics.population,
        "median_income": ABSCEntensMetrics.median_income,
        "median_house_price": market_agg.c.avg_median_house_price,
        "median_unit_price": market_agg.c.avg_median_unit_price,
        "pop_growth_5yr_pct": ABSCEntensMetrics.pop_growth_5yr,
        "median_rent_weekly": ABSCEntensMetrics.median_rent_weekly,
        "distance_to_cbd_km": SA2Region.distance_to_cbd_km,
        "investment_score": SuburbScore.investment_score,
        "economic_score": SuburbScore.economic_score,
        "demographic_score": SuburbScore.demographic_score,
        "momentum_score": SuburbScore.momentum_score,
        "scarcity_score": SuburbScore.scarcity_score,
    }
    sort_col = sortable_columns.get(sort_by, sortable_columns[_DEFAULT_SORT])
    order = sort_col.asc().nulls_last() if sort_dir == "asc" else sort_col.desc().nulls_last()
    page_stmt = base.order_by(order).limit(limit).offset(offset)

    rows = (await db.execute(page_stmt)).all()
    results = [_row_to_dict(row) for row in rows]

    return SuburbSearchPage(total_count=total_count, results=results)


async def list_available_states(db: AsyncSession) -> List[str]:
    """Distinct states present in sa2_regions, for populating the state filter."""
    rows = (await db.execute(select(SA2Region.state).distinct().order_by(SA2Region.state))).scalars().all()
    return list(rows)


def _apply_filters(stmt, filters: SuburbFilters, market_agg):
    f = filters
    if f.states:
        stmt = stmt.where(SA2Region.state.in_(f.states))
    if f.max_distance_to_cbd_km is not None:
        stmt = stmt.where(SA2Region.distance_to_cbd_km <= f.max_distance_to_cbd_km)
    if f.min_median_house_price is not None:
        stmt = stmt.where(market_agg.c.avg_median_house_price >= f.min_median_house_price)
    if f.max_median_house_price is not None:
        stmt = stmt.where(market_agg.c.avg_median_house_price <= f.max_median_house_price)
    if f.min_median_unit_price is not None:
        stmt = stmt.where(market_agg.c.avg_median_unit_price >= f.min_median_unit_price)
    if f.max_median_unit_price is not None:
        stmt = stmt.where(market_agg.c.avg_median_unit_price <= f.max_median_unit_price)
    if f.min_population is not None:
        stmt = stmt.where(ABSCEntensMetrics.population >= f.min_population)
    if f.max_population is not None:
        stmt = stmt.where(ABSCEntensMetrics.population <= f.max_population)
    if f.min_pop_growth_5yr_pct is not None:
        stmt = stmt.where(ABSCEntensMetrics.pop_growth_5yr >= f.min_pop_growth_5yr_pct)
    if f.min_median_income is not None:
        stmt = stmt.where(ABSCEntensMetrics.median_income >= f.min_median_income)
    if f.max_median_income is not None:
        stmt = stmt.where(ABSCEntensMetrics.median_income <= f.max_median_income)
    if f.min_median_rent_weekly is not None:
        stmt = stmt.where(ABSCEntensMetrics.median_rent_weekly >= f.min_median_rent_weekly)
    if f.max_median_rent_weekly is not None:
        stmt = stmt.where(ABSCEntensMetrics.median_rent_weekly <= f.max_median_rent_weekly)
    if f.min_owner_occupied_pct is not None:
        stmt = stmt.where(ABSCEntensMetrics.owners_pct >= f.min_owner_occupied_pct)
    if f.max_owner_occupied_pct is not None:
        stmt = stmt.where(ABSCEntensMetrics.owners_pct <= f.max_owner_occupied_pct)
    if f.max_social_housing_pct is not None:
        stmt = stmt.where(ABSCEntensMetrics.social_housing_pct <= f.max_social_housing_pct)
    if f.max_unemployment_pct is not None:
        stmt = stmt.where(ABSCEntensMetrics.unemployment_pct <= f.max_unemployment_pct)
    if f.min_seifa_irsd_decile is not None:
        stmt = stmt.where(ABSCEntensMetrics.seifa_irsd_decile >= f.min_seifa_irsd_decile)
    if f.min_avg_school_icsea is not None:
        stmt = stmt.where(ABSCEntensMetrics.avg_school_icsea >= f.min_avg_school_icsea)
    if f.max_days_on_market is not None:
        stmt = stmt.where(market_agg.c.avg_days_on_market_house <= f.max_days_on_market)
    if f.min_investment_score is not None:
        stmt = stmt.where(SuburbScore.investment_score >= f.min_investment_score)
    if f.min_economic_score is not None:
        stmt = stmt.where(SuburbScore.economic_score >= f.min_economic_score)
    if f.min_demographic_score is not None:
        stmt = stmt.where(SuburbScore.demographic_score >= f.min_demographic_score)
    if f.min_gross_yield_house_pct is not None:
        stmt = stmt.where(market_agg.c.avg_gross_yield_house_pct >= f.min_gross_yield_house_pct)
    if f.max_vacancy_rate_pct is not None:
        stmt = stmt.where(market_agg.c.avg_vacancy_rate_pct <= f.max_vacancy_rate_pct)
    if f.momentum_phase is not None:
        stmt = stmt.where(SuburbScore.momentum_phase == f.momentum_phase)
    if f.growth_yield_quadrant is not None:
        stmt = stmt.where(SuburbScore.growth_yield_quadrant == f.growth_yield_quadrant)
    if f.min_scarcity_score is not None:
        stmt = stmt.where(SuburbScore.scarcity_score >= f.min_scarcity_score)
    return stmt


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "sa2_code": row.sa2_code,
        "sa2_name": row.sa2_name,
        "state": row.state,
        "distance_to_cbd_km": row.distance_to_cbd_km,
        "population": row.population,
        "median_income": row.median_income,
        "median_rent_weekly": row.median_rent_weekly,
        "owner_occupied_pct": row.owners_pct,
        "social_housing_pct": row.social_housing_pct,
        "unemployment_pct": row.unemployment_pct,
        "seifa_irsd_decile": row.seifa_irsd_decile,
        "avg_school_icsea": row.avg_school_icsea,
        "pop_growth_5yr_pct": row.pop_growth_5yr,
        "pop_growth_proj_pct": row.pop_growth_proj_pct,
        "median_house_price": row.avg_median_house_price,
        "median_unit_price": row.avg_median_unit_price,
        "days_on_market": row.avg_days_on_market_house,
        "investment_score": row.investment_score,
        "economic_score": row.economic_score,
        "demographic_score": row.demographic_score,
        "momentum_score": row.momentum_score,
        "momentum_phase": row.momentum_phase,
        "growth_yield_quadrant": row.growth_yield_quadrant,
        "neighborhood_signal": row.neighborhood_signal,
        "scarcity_score": row.scarcity_score,
        "gross_yield_house_pct": row.avg_gross_yield_house_pct,
        "vacancy_rate_pct": row.avg_vacancy_rate_pct,
        "growth_1yr_house_pct": row.avg_growth_house_1y_pct,
        "heat_score": row.avg_heat_score_house,
    }
