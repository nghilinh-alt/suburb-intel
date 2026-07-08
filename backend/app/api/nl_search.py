"""Plain-English suburb search.

Mounted under `/search` by main.py (no collision with search.py's routes —
this only adds POST /search/ask). See app.core.nl_query_parser for what the
parser currently understands and why it's scoped to state/distance/population/
income/investment_score rather than bedrooms/price (that needs PropRadar
sold-listing data, not yet ingested).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nl_query_parser import SuburbSearchFilter, parse_with_rules
from app.db.models import ABSCEntensMetrics, SA2Region, SuburbScore
from app.db.session import get_db

router = APIRouter()

_CENSUS_YEAR = 2021

_SORT_COLUMNS = {
    "distance_to_cbd": SA2Region.distance_to_cbd_km,
    "investment_score": SuburbScore.investment_score,
    "population": ABSCEntensMetrics.population,
    "median_income": ABSCEntensMetrics.median_income,
}


class AskRequest(BaseModel):
    prompt: str


@router.post("/ask")
async def ask_search(body: AskRequest, db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    parsed = parse_with_rules(body.prompt)
    results = await _run_query(db, parsed)

    message: Optional[str] = None
    if not results:
        message = (
            "No suburbs match this filter. "
            "Try widening the distance-to-CBD range or checking the city/state name."
        )

    return {
        "parsed_filter": parsed.model_dump(),
        "results": results,
        "message": message,
    }


async def _run_query(db: AsyncSession, parsed: SuburbSearchFilter) -> List[Dict[str, Any]]:
    order_col = _SORT_COLUMNS[parsed.sort_by]
    order_expr = order_col.asc().nulls_last() if parsed.sort_dir == "asc" else order_col.desc().nulls_last()

    stmt = (
        select(
            SA2Region.sa2_code,
            SA2Region.sa2_name,
            SA2Region.state,
            SA2Region.distance_to_cbd_km,
            ABSCEntensMetrics.population,
            ABSCEntensMetrics.median_income,
            SuburbScore.investment_score,
        )
        .select_from(SA2Region)
        .outerjoin(
            ABSCEntensMetrics,
            (ABSCEntensMetrics.sa2_code == SA2Region.sa2_code)
            & (ABSCEntensMetrics.year == _CENSUS_YEAR),
        )
        .outerjoin(SuburbScore, SuburbScore.sa2_code == SA2Region.sa2_code)
        .order_by(order_expr)
        .limit(parsed.limit)
    )

    if parsed.state:
        stmt = stmt.where(SA2Region.state == parsed.state)
    if parsed.max_distance_to_cbd_km is not None:
        stmt = stmt.where(
            SA2Region.distance_to_cbd_km.isnot(None),
            SA2Region.distance_to_cbd_km <= parsed.max_distance_to_cbd_km,
        )

    rows = (await db.execute(stmt)).all()
    return [
        {
            "sa2_code": sa2_code,
            "sa2_name": sa2_name,
            "state": state,
            "distance_to_cbd_km": distance_to_cbd_km,
            "population": population,
            "median_income": median_income,
            "investment_score": investment_score,
        }
        for sa2_code, sa2_name, state, distance_to_cbd_km, population, median_income, investment_score in rows
    ]
