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


@router.get("/top")
async def get_top_suburbs(
    limit: int = Query(20, ge=5, le=100, description="Number of top suburbs to return"),
    by: str = Query("investment_score", description="Sort by: investment_score, population, median_income"),
) -> Dict[str, Any]:
    """Return top suburbs by a given metric.

    Currently returns mock data; in production this should query `suburb_scores`.
    """
    import random

    sa2_codes = ["30150", "34005", "48210", "47002", "22625"]
    top_suburbs = [
        {
            "sa2_code": code,
            "investment_score": round(random.uniform(65, 90), 1),
            "population": random.randint(10000, 30000),
            "median_income": random.randint(70000, 120000),
        }
        for code in sa2_codes
    ]

    if by == "population":
        top_suburbs.sort(key=lambda x: x["population"], reverse=True)
    elif by == "median_income":
        top_suburbs.sort(key=lambda x: x["median_income"], reverse=True)
    else:
        top_suburbs.sort(key=lambda x: x["investment_score"], reverse=True)

    return {"count": len(top_suburbs), "by": by, "suburbs": top_suburbs[:limit]}
