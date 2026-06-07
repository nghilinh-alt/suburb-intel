"""Rankings endpoint — returns top suburbs by precomputed score columns."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ABSCEntensMetrics, SA2Region, SuburbAggregate, SuburbScore
from app.db.session import get_db

router = APIRouter()

_VALID_SCORE_TYPES = frozenset({
    "investment_score",
    "liveability_score",
    "education_score",
    "growth_score",
    "demographic_score",
    "housing_score",
    "infrastructure_score",
    "gentrification_index",
})

_SCORE_LABELS = {
    "investment_score":    "Overall Investment",
    "liveability_score":   "Liveability",
    "education_score":     "Education",
    "growth_score":        "Growth",
    "demographic_score":   "Demographics",
    "housing_score":       "Housing Market",
    "infrastructure_score": "Infrastructure Pipeline",
    "gentrification_index": "Gentrification",
}


@router.get("/")
async def get_rankings(
    limit:      int = Query(25, ge=5, le=200, description="Number of suburbs to return"),
    score_type: str = Query("investment_score", description="Score column to rank by"),
    state:      str | None = Query(None, description="Filter by state code, e.g. NSW"),
    db: AsyncSession = Depends(get_db),
):
    """Return top suburbs ranked by a precomputed score column."""

    if score_type not in _VALID_SCORE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"score_type must be one of: {', '.join(sorted(_VALID_SCORE_TYPES))}",
        )

    order_col = getattr(SuburbScore, score_type)

    stmt = (
        select(
            SuburbScore,
            SA2Region.sa2_name,
            SA2Region.state,
            ABSCEntensMetrics.population,
            ABSCEntensMetrics.median_income,
        )
        .join(SA2Region, SA2Region.sa2_code == SuburbScore.sa2_code)
        .outerjoin(
            ABSCEntensMetrics,
            (ABSCEntensMetrics.sa2_code == SuburbScore.sa2_code)
            & (ABSCEntensMetrics.year == 2021),
        )
        # Exclude ABS statistical phantom SA2s (Migratory/Offshore/No usual address)
        # These end in 7979799 or 9999499 and are not real residential areas
        .where(~SA2Region.sa2_code.like('%7979799'))
        .where(~SA2Region.sa2_code.like('%9999499'))
        .order_by(order_col.desc().nulls_last())
        .limit(limit)
    )

    if state:
        stmt = stmt.where(SA2Region.state == state.upper())

    rows = (await db.execute(stmt)).all()

    # Build a sa2_code → suburb_id lookup from SuburbAggregate
    # (each aggregate row has a JSON list of sa2_codes it covers)
    sa2_codes_in_results = {score.sa2_code for score, *_ in rows}
    agg_rows = (await db.execute(select(SuburbAggregate))).scalars().all()
    sa2_to_suburb_id: dict[str, str] = {}
    for agg in agg_rows:
        for code in (agg.sa2_codes or []):
            if code in sa2_codes_in_results:
                sa2_to_suburb_id[code] = agg.suburb_id

    return {
        "score_type":  score_type,
        "score_label": _SCORE_LABELS.get(score_type, score_type),
        "count":       len(rows),
        "available_score_types": sorted(_VALID_SCORE_TYPES),
        "rankings": [
            {
                "rank":        i + 1,
                "sa2_code":    score.sa2_code,
                "suburb_id":   sa2_to_suburb_id.get(score.sa2_code),
                "sa2_name":    name,
                "state":       st,
                "population":  pop,
                "median_income": inc,
                "scores": {
                    "investment_score":    _r(score.investment_score),
                    "liveability_score":   _r(score.liveability_score),
                    "education_score":     _r(score.education_score),
                    "growth_score":        _r(score.growth_score),
                    "demographic_score":   _r(score.demographic_score),
                    "housing_score":       _r(score.housing_score),
                    "infrastructure_score": _r(score.infrastructure_score),
                    "gentrification_index": _r(score.gentrification_index),
                },
                "risk_flags": score.risk_flags or [],
            }
            for i, (score, name, st, pop, inc) in enumerate(rows)
        ],
    }


def _r(v: float | None) -> float | None:
    return round(v, 2) if v is not None else None
