"""Suburb comparison endpoint — returns two suburb reports side-by-side."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.api.suburb import suburb_report

router = APIRouter()


@router.get("/")
async def compare_suburbs(
    a: str = Query(..., description="First SA2 code"),
    b: str = Query(..., description="Second SA2 code"),
    db: AsyncSession = Depends(get_db),
):
    """Return investment reports for two SA2s side-by-side for comparison."""
    if a == b:
        raise HTTPException(status_code=400, detail="Both SA2 codes are the same.")

    # Fetch both reports — reuse suburb_report which handles 404 correctly
    try:
        report_a = await suburb_report(a, db)
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=f"Suburb A ({a}): {e.detail}") from e

    try:
        report_b = await suburb_report(b, db)
    except HTTPException as e:
        raise HTTPException(status_code=e.status_code, detail=f"Suburb B ({b}): {e.detail}") from e

    # Compute deltas: B minus A for each score (positive = B is better)
    score_keys = [
        "investment_score", "liveability_score", "education_score",
        "growth_score", "demographic_score", "housing_score",
        "infrastructure_score", "gentrification_index",
    ]
    deltas = {}
    for key in score_keys:
        va = (report_a["scores"].get(key) or 0)
        vb = (report_b["scores"].get(key) or 0)
        deltas[key] = round(vb - va, 2)

    return {
        "suburb_a": report_a,
        "suburb_b": report_b,
        "deltas":   deltas,   # positive = B is higher, negative = A is higher
    }
