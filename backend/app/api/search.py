"""Suburb search endpoints.

Mounted under `/search` by main.py. The ABS-backed per-suburb endpoints
(`/{suburb_name}/population-by-age`, etc.) were previously nested inside the
`search_suburbs` function body which meant the decorators never registered
them with the router. They are now defined at module scope.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.data_sources import AustralianDataSources
from app.db.models import ABSCEntensMetrics, SA2Region
from app.db.session import get_db
from app.services.suburb_filter_service import (
    SuburbFilters,
    list_available_states,
    search_suburbs_filtered,
)

router = APIRouter()

_SA2_CODE_RE = re.compile(r"^\d{5,9}$")


@router.get("/")
async def search_suburbs(
    query: str = Query(..., min_length=2, description="Suburb name or SA2 code to search"),
    state: Optional[str] = Query(None, description="Filter by state, e.g. NSW, VIC, QLD"),
    limit: int = Query(10, ge=1, le=50, description="Maximum results to return"),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]] | Dict[str, Any]:
    """Search by partial suburb name, or exact lookup by SA2 code."""
    if _SA2_CODE_RE.match(query):
        return await _get_exact_sa2(query, db)

    results = await _get_suburbs_by_name(db, query, state=state, limit=limit)
    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No suburbs found matching '{query}'. Use full name or valid SA2 code.",
        )
    return results


# ---------------------------------------------------------------------------
# Live ABS Census endpoints (previously nested inside search_suburbs and
# therefore never registered with the router).
# ---------------------------------------------------------------------------

@router.get("/{suburb_name}/population-by-age")
async def get_population_by_age(
    suburb_name: str, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Age distribution for a suburb (ABS Census 2021)."""
    sa2_code = await _resolve_sa2_code(db, suburb_name)
    result = AustralianDataSources().get_population_by_age(sa2_code)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=f"ABS API error: {result.get('error')}")
    return {"suburb": suburb_name, "sa2_code": sa2_code, "data": result["data"]}


@router.get("/{suburb_name}/income")
async def get_income(
    suburb_name: str, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Median household income (ABS Census 2021)."""
    sa2_code = await _resolve_sa2_code(db, suburb_name)
    result = AustralianDataSources().get_household_income(sa2_code)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=f"ABS API error: {result.get('error')}")
    return {"suburb": suburb_name, "sa2_code": sa2_code, "data": result["data"]}


@router.get("/{suburb_name}/housing-tenure")
async def get_housing_tenure(
    suburb_name: str, db: AsyncSession = Depends(get_db)
) -> Dict[str, Any]:
    """Housing tenure split, owned vs rented (ABS Census 2021)."""
    sa2_code = await _resolve_sa2_code(db, suburb_name)
    result = AustralianDataSources().get_housing_tenure(sa2_code)
    if not result.get("success"):
        raise HTTPException(status_code=502, detail=f"ABS API error: {result.get('error')}")
    return {"suburb": suburb_name, "sa2_code": sa2_code, "data": result["data"]}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _get_exact_sa2(sa2_code: str, db: AsyncSession) -> Dict[str, Any]:
    """Look up a single SA2 region by code, joining latest census metrics if present."""
    region = await db.get(SA2Region, sa2_code)
    if not region:
        raise HTTPException(status_code=404, detail=f"SA2 region '{sa2_code}' not found.")

    metrics = await db.get(ABSCEntensMetrics, (sa2_code, 2021))

    return {
        "sa2_code": region.sa2_code,
        "sa2_name": region.sa2_name,
        "state": region.state,
        "population": metrics.population if metrics else None,
        "median_income": metrics.median_income if metrics else None,
        "median_age": metrics.median_age if metrics else None,
        "distance_to_cbd_km": region.distance_to_cbd_km,
    }


async def _get_suburbs_by_name(
    db: AsyncSession,
    query: str,
    *,
    state: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Case-insensitive partial-name search across SA2Region (+ left-join metrics)."""
    stmt = (
        select(
            SA2Region.sa2_code,
            SA2Region.sa2_name,
            SA2Region.state,
            SA2Region.distance_to_cbd_km,
            ABSCEntensMetrics.population,
            ABSCEntensMetrics.median_income,
            ABSCEntensMetrics.median_age,
            ABSCEntensMetrics.renters_pct,
            ABSCEntensMetrics.owners_pct,
        )
        .select_from(SA2Region)
        .outerjoin(
            ABSCEntensMetrics,
            (ABSCEntensMetrics.sa2_code == SA2Region.sa2_code)
            & (ABSCEntensMetrics.year == 2021),
        )
        .where(SA2Region.sa2_name.ilike(f"%{query}%"))
        .order_by(SA2Region.sa2_name)
        .limit(limit)
    )
    if state:
        stmt = stmt.where(SA2Region.state == state)

    result = await db.execute(stmt)
    return [dict(row._mapping) for row in result.fetchall()]


async def _resolve_sa2_code(db: AsyncSession, suburb_name: str) -> str:
    """Resolve a suburb name (or SA2 code) to a single SA2 code, or 404."""
    if _SA2_CODE_RE.match(suburb_name):
        return suburb_name
    matches = await _get_suburbs_by_name(db, suburb_name, limit=1)
    if not matches:
        raise HTTPException(status_code=404, detail=f"Suburb '{suburb_name}' not found")
    return matches[0]["sa2_code"]


@router.get("/filter")
async def filter_suburbs(
    states: Optional[str] = Query(None, description="Comma-separated state codes, e.g. QLD,NSW"),
    max_distance_to_cbd_km: Optional[float] = Query(None),
    min_median_house_price: Optional[float] = Query(None),
    max_median_house_price: Optional[float] = Query(None),
    min_median_unit_price: Optional[float] = Query(None),
    max_median_unit_price: Optional[float] = Query(None),
    min_population: Optional[int] = Query(None),
    max_population: Optional[int] = Query(None),
    min_pop_growth_5yr_pct: Optional[float] = Query(None),
    min_median_income: Optional[int] = Query(None),
    max_median_income: Optional[int] = Query(None),
    min_median_rent_weekly: Optional[float] = Query(None),
    max_median_rent_weekly: Optional[float] = Query(None),
    min_owner_occupied_pct: Optional[float] = Query(None),
    max_owner_occupied_pct: Optional[float] = Query(None),
    max_social_housing_pct: Optional[float] = Query(None),
    max_unemployment_pct: Optional[float] = Query(None),
    min_seifa_irsd_decile: Optional[int] = Query(None),
    min_avg_school_icsea: Optional[float] = Query(None),
    max_days_on_market: Optional[float] = Query(None),
    min_investment_score: Optional[float] = Query(None),
    min_economic_score: Optional[float] = Query(None),
    min_demographic_score: Optional[float] = Query(None),
    min_gross_yield_house_pct: Optional[float] = Query(None),
    max_vacancy_rate_pct: Optional[float] = Query(None),
    momentum_phase: Optional[str] = Query(None, pattern="^(accelerating|steady|cooling)$"),
    growth_yield_quadrant: Optional[str] = Query(None, pattern="^(hot|growth_play|cash_flow_play|avoid)$"),
    min_scarcity_score: Optional[float] = Query(None, description="0-100 supply-scarcity score — higher means less for-sale supply relative to demand"),
    min_amenity_score: Optional[float] = Query(None, description="Minimum amenity/liveability score 0–10"),
    max_building_approvals_1yr: Optional[int] = Query(None, description="Maximum new dwellings approved in the last year (lower = less new supply)"),
    sort_by: str = Query("population"),
    sort_dir: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Filter, sort, and paginate suburbs for the Search page's filter
    sidebar. All filter params are optional and combine with AND."""
    filters = SuburbFilters(
        states=[s.strip().upper() for s in states.split(",") if s.strip()] if states else None,
        max_distance_to_cbd_km=max_distance_to_cbd_km,
        min_median_house_price=min_median_house_price,
        max_median_house_price=max_median_house_price,
        min_median_unit_price=min_median_unit_price,
        max_median_unit_price=max_median_unit_price,
        min_population=min_population,
        max_population=max_population,
        min_pop_growth_5yr_pct=min_pop_growth_5yr_pct,
        min_median_income=min_median_income,
        max_median_income=max_median_income,
        min_median_rent_weekly=min_median_rent_weekly,
        max_median_rent_weekly=max_median_rent_weekly,
        min_owner_occupied_pct=min_owner_occupied_pct,
        max_owner_occupied_pct=max_owner_occupied_pct,
        max_social_housing_pct=max_social_housing_pct,
        max_unemployment_pct=max_unemployment_pct,
        min_seifa_irsd_decile=min_seifa_irsd_decile,
        min_avg_school_icsea=min_avg_school_icsea,
        max_days_on_market=max_days_on_market,
        min_investment_score=min_investment_score,
        min_economic_score=min_economic_score,
        min_demographic_score=min_demographic_score,
        min_gross_yield_house_pct=min_gross_yield_house_pct,
        max_vacancy_rate_pct=max_vacancy_rate_pct,
        momentum_phase=momentum_phase,
        growth_yield_quadrant=growth_yield_quadrant,
        min_scarcity_score=min_scarcity_score,
        min_amenity_score=min_amenity_score,
        max_building_approvals_1yr=max_building_approvals_1yr,
    )
    page = await search_suburbs_filtered(db, filters, sort_by=sort_by, sort_dir=sort_dir, limit=limit, offset=offset)
    return {
        "total_count": page.total_count,
        "limit": limit,
        "offset": offset,
        "results": page.results,
    }


@router.get("/filter-options")
async def get_filter_options(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    """States present in the DB, for populating the state filter dropdown."""
    return {"states": await list_available_states(db)}


@router.get("/top")
async def get_top_suburbs(
    limit: int = Query(20, ge=5, le=100, description="Number of top suburbs to return"),
    by: str = Query("investment_score", description="Sort by: investment_score, population, median_income"),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return top suburbs by a given metric, sourced from the suburb_scores table."""
    from app.db.models import SuburbScore

    _valid_by = {"investment_score", "population", "median_income"}
    if by not in _valid_by:
        raise HTTPException(status_code=400, detail=f"'by' must be one of {sorted(_valid_by)}")

    if by == "investment_score":
        order_col = SuburbScore.investment_score
        stmt = (
            select(SuburbScore, SA2Region.sa2_name, SA2Region.state,
                   ABSCEntensMetrics.population, ABSCEntensMetrics.median_income)
            .join(SA2Region, SA2Region.sa2_code == SuburbScore.sa2_code)
            .outerjoin(
                ABSCEntensMetrics,
                (ABSCEntensMetrics.sa2_code == SuburbScore.sa2_code)
                & (ABSCEntensMetrics.year == 2021),
            )
            .order_by(order_col.desc().nulls_last())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        suburbs = [
            {
                "sa2_code": score.sa2_code,
                "sa2_name": name,
                "state": state,
                "investment_score": score.investment_score,
                "population": pop,
                "median_income": income,
            }
            for score, name, state, pop, income in rows
        ]
    else:
        order_col = getattr(ABSCEntensMetrics, by)
        stmt = (
            select(SA2Region, ABSCEntensMetrics)
            .join(
                ABSCEntensMetrics,
                (ABSCEntensMetrics.sa2_code == SA2Region.sa2_code)
                & (ABSCEntensMetrics.year == 2021),
            )
            .order_by(order_col.desc().nulls_last())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()
        suburbs = [
            {
                "sa2_code": region.sa2_code,
                "sa2_name": region.sa2_name,
                "state": region.state,
                "investment_score": None,
                "population": census.population,
                "median_income": census.median_income,
            }
            for region, census in rows
        ]

    return {"count": len(suburbs), "by": by, "suburbs": suburbs}
