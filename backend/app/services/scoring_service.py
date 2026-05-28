"""Shared feature-building helpers used by the suburb endpoint and backfill job.

Extracted from app.api.suburb so both the live endpoint and the batch backfill
job call identical feature-engineering logic.
"""

from __future__ import annotations

from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils import (
    calculate_employment_diversity,
    calculate_household_pressure,
    get_industry_diversity,
)
from app.db.models import ABSCEntensMetrics, InfrastructureProject, SA2ProjectLink

# Suburbs with median income at or above this number get a maxed-out income sub-score.
_INCOME_INDEX_CEILING = 85_000.0


async def fetch_linked_projects(db: AsyncSession, sa2_code: str) -> List[Dict[str, Any]]:
    """Pull infrastructure projects linked to this SA2."""
    stmt = (
        select(InfrastructureProject, SA2ProjectLink.impact_score)
        .join(SA2ProjectLink, SA2ProjectLink.project_id == InfrastructureProject.project_id)
        .where(SA2ProjectLink.sa2_code == sa2_code)
    )
    result = await db.execute(stmt)
    rows = result.all()
    return [
        {
            "project_id": project.project_id,
            "name": project.name,
            "type": project.type,
            "value_aud": project.value_aud,
            "status": project.status,
            "impact_score": impact_score,
        }
        for project, impact_score in rows
    ]


def build_features(
    census_metrics: ABSCEntensMetrics,
    gov_projects: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Convert raw census + project data into the feature dict expected by the scorer."""
    industry_profile = census_metrics.industry_profile or {}

    pop_growth = (
        census_metrics.pop_growth_5yr
        if census_metrics.pop_growth_5yr is not None
        else 35.0
    )
    young_population_pct = (
        census_metrics.young_population_pct
        if census_metrics.young_population_pct is not None
        else 32.0
    )

    if census_metrics.median_income:
        income_index = min(
            census_metrics.median_income / _INCOME_INDEX_CEILING * 100, 100.0
        )
    else:
        income_index = 70.0

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
