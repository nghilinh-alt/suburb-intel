"""Suburb investment-report endpoint."""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.gov_score import analyze_risk_flags, generate_insight
from app.core.scoring import calculate_investment_score
from app.core.utils import (
    calculate_employment_diversity,
    calculate_household_pressure,
    get_industry_diversity,
)
from app.db.models import ABSCEntensMetrics, InfrastructureProject, SA2ProjectLink
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{sa2_code}")
async def suburb_report(
    sa2_code: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return investment-score report for an SA2 region."""
    try:
        census_metrics = await db.get(ABSCEntensMetrics, (sa2_code, 2021))
        if not census_metrics:
            raise HTTPException(
                status_code=404,
                detail=f"SA2 region '{sa2_code}' not found. Use /search to find valid codes.",
            )

        gov_projects = await _fetch_linked_projects(db, sa2_code)
        features = _build_features(census_metrics, gov_projects)
        scores = calculate_investment_score(features)

        census_dict = _census_to_dict(census_metrics)
        risk_flags = analyze_risk_flags(gov_projects, census_dict)
        insight = generate_insight(scores, census_dict, gov_projects)

        return {
            "sa2_code": sa2_code,
            "sa2_name": getattr(census_metrics, "sa2_name", None),
            "state": getattr(census_metrics, "state", None),
            "scores": scores,
            "insight": insight,
            "risk_flags": risk_flags,
            "tags": _generate_tags(scores),
            "census_year": 2021,
            "population": census_metrics.population,
            "median_income": census_metrics.median_income,
            "median_age": census_metrics.median_age,
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to generate suburb report for %s", sa2_code)
        raise HTTPException(status_code=500, detail=f"Error generating report: {e}") from e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _fetch_linked_projects(db: AsyncSession, sa2_code: str) -> List[Dict[str, Any]]:
    """Pull infrastructure projects linked to this SA2."""
    stmt = (
        select(InfrastructureProject, SA2ProjectLink.impact_score)
        .join(SA2ProjectLink, SA2ProjectLink.project_id == InfrastructureProject.project_id)
        .where(SA2ProjectLink.sa2_code == sa2_code)
    )
    result = await db.execute(stmt)
    rows = result.all()
    projects: List[Dict[str, Any]] = []
    for project, impact_score in rows:
        projects.append(
            {
                "project_id": project.project_id,
                "name": project.name,
                "type": project.type,
                "value_aud": project.value_aud,
                "status": project.status,
                "impact_score": impact_score,
            }
        )
    return projects


def _build_features(
    census_metrics: ABSCEntensMetrics, gov_projects: List[Dict[str, Any]]
) -> Dict[str, Any]:
    industry_profile = census_metrics.industry_profile or {}

    # TODO: replace with real growth & age-band metrics once we have multi-year census loaded.
    pop_growth = 35.0
    young_population_pct = 32.0

    income_index = (
        census_metrics.median_income / 85000.0 * 100 if census_metrics.median_income else 70.0
    )
    renter_pct = census_metrics.renters_pct or 40.0

    return {
        "pop_growth": pop_growth,
        "young_population_pct": young_population_pct,
        "income_index": income_index,
        "employment_diversity": calculate_employment_diversity(industry_profile),
        "renter_pct": renter_pct,
        "household_pressure": calculate_household_pressure(renter_pct),
        "industry_diversity": get_industry_diversity(industry_profile),
        "projects": gov_projects,
    }


def _census_to_dict(metrics: ABSCEntensMetrics) -> Dict[str, Any]:
    """SQLAlchemy model -> plain dict, so downstream code can `.get()` safely."""
    return {
        "sa2_code": metrics.sa2_code,
        "year": metrics.year,
        "population": metrics.population,
        "median_income": metrics.median_income,
        "median_age": metrics.median_age,
        "renters_pct": metrics.renters_pct or 0,
        "owners_pct": metrics.owners_pct or 0,
        "industry_profile": metrics.industry_profile or {},
    }


def _generate_tags(scores: Dict[str, Any]) -> List[str]:
    investment_score = scores.get("investment_score", 0)
    tags: List[str] = []

    if investment_score > 85:
        tags.append("Premium Investment")
    elif investment_score > 75:
        tags.append("Strong Investment")
    elif investment_score > 65:
        tags.append("Moderate Growth")
    else:
        tags.append("Development Opportunity")

    gov_score = scores.get("gov_investment_score", 0)
    if gov_score > 80:
        tags.append("Infrastructure-Driven")
    elif gov_score > 50:
        tags.append("Government-Supported")

    return tags
