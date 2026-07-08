"""Rankings endpoint — returns top suburbs by precomputed score columns."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SA2Region, SuburbScore
from app.db.session import get_db

router = APIRouter()

_VALID_SCORE_TYPES = frozenset({
    "investment_score",
    "demographic_score",
    "economic_score",
    "housing_pressure_score",
    "resilience_score",
    "gov_investment_score",
})


@router.get("/")
async def get_rankings(
    limit: int = Query(25, ge=10, le=200, description="Number of suburbs to return"),
    score_type: str = Query("investment_score", description="Score column to rank by"),
    db: AsyncSession = Depends(get_db),
):
    """Return top suburbs ranked by a precomputed score column.

    Results are drawn from the suburb_scores table, populated by the backfill job.
    """
    if score_type not in _VALID_SCORE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"score_type must be one of {sorted(_VALID_SCORE_TYPES)}",
        )

    order_col = getattr(SuburbScore, score_type)
    stmt = (
        select(SuburbScore, SA2Region.sa2_name, SA2Region.state, SA2Region.distance_to_cbd_km)
        .join(SA2Region, SA2Region.sa2_code == SuburbScore.sa2_code)
        .order_by(order_col.desc().nulls_last())
        .limit(limit)
    )
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
                **{c: getattr(score, c) for c in _VALID_SCORE_TYPES},
            }
            for i, (score, name, state, distance_to_cbd_km) in enumerate(rows)
        ],
    }
