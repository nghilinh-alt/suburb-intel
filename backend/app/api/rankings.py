"""Rankings endpoint — returns top suburbs by precomputed score columns."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SA2Region, SuburbMarketStats, SuburbScore
from app.db.session import get_db

router = APIRouter()

_VALID_SCORE_TYPES = frozenset({
    "investment_score",
    "demographic_score",
    "economic_score",
    "housing_pressure_score",
    "resilience_score",
    "gov_investment_score",
    "momentum_score",
    "scarcity_score",
})


@router.get("/")
async def get_rankings(
    limit: int = Query(25, ge=10, le=200, description="Number of suburbs to return"),
    score_type: str = Query("investment_score", description="Score column to rank by"),
    states: Optional[str] = Query(None, description="Comma-separated state codes to filter, e.g. QLD,NSW"),
    db: AsyncSession = Depends(get_db),
):
    """Return top suburbs ranked by a precomputed score column.

    Results are drawn from the suburb_scores table, populated by the backfill job.
    Optionally filtered to specific states via the `states` param.
    Each row includes median_house_price and gross_yield_house_pct averaged from
    SuburbMarketStats so investors can gauge affordability without clicking through.
    """
    if score_type not in _VALID_SCORE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"score_type must be one of {sorted(_VALID_SCORE_TYPES)}",
        )

    # Average market stats per SA2 (may have multiple rows per month/suburb).
    market_agg = (
        select(
            SuburbMarketStats.sa2_code,
            func.avg(SuburbMarketStats.median_house_price).label("avg_median_house_price"),
            func.avg(SuburbMarketStats.gross_yield_house_pct).label("avg_gross_yield_house_pct"),
        )
        .group_by(SuburbMarketStats.sa2_code)
        .subquery()
    )

    order_col = getattr(SuburbScore, score_type)
    stmt = (
        select(
            SuburbScore,
            SA2Region.sa2_name,
            SA2Region.state,
            SA2Region.distance_to_cbd_km,
            market_agg.c.avg_median_house_price,
            market_agg.c.avg_gross_yield_house_pct,
        )
        .join(SA2Region, SA2Region.sa2_code == SuburbScore.sa2_code)
        .outerjoin(market_agg, market_agg.c.sa2_code == SuburbScore.sa2_code)
        .order_by(order_col.desc().nulls_last())
        .limit(limit)
    )

    if states:
        state_list = [s.strip().upper() for s in states.split(",") if s.strip()]
        if state_list:
            stmt = stmt.where(SA2Region.state.in_(state_list))

    rows = (await db.execute(stmt)).all()

    return {
        "score_type": score_type,
        "count": len(rows),
        "rankings": [
            {
                "rank": i + 1,
                "sa2_code": score.sa2_code,
                "sa2_name": name,
                "state": state,
                "distance_to_cbd_km": distance_to_cbd_km,
                "momentum_phase": score.momentum_phase,
                "growth_yield_quadrant": score.growth_yield_quadrant,
                "neighborhood_signal": score.neighborhood_signal,
                "median_house_price": avg_price,
                "gross_yield_house_pct": avg_yield,
                **{c: getattr(score, c) for c in _VALID_SCORE_TYPES},
            }
            for i, (score, name, state, distance_to_cbd_km, avg_price, avg_yield) in enumerate(rows)
        ],
    }
