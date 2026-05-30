"""Suburb investment-report endpoint.

Reads pre-computed scores from suburb_scores (populated by backfill_scores.py)
and joins census metadata + linked data to build a rich report response.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ABSCEntensMetrics, SA2Region, SuburbScore
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{sa2_code}")
async def suburb_report(
    sa2_code: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return full investment-score report for an SA2 region."""

    # Single query: SA2 metadata + census metrics + pre-computed scores
    stmt = (
        select(SA2Region, ABSCEntensMetrics, SuburbScore)
        .join(
            ABSCEntensMetrics,
            (ABSCEntensMetrics.sa2_code == SA2Region.sa2_code)
            & (ABSCEntensMetrics.year == 2021),
        )
        .outerjoin(SuburbScore, SuburbScore.sa2_code == SA2Region.sa2_code)
        .where(SA2Region.sa2_code == sa2_code)
    )
    result = await db.execute(stmt)
    row = result.first()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=f"SA2 region '{sa2_code}' not found. Use /search to find valid codes.",
        )

    region, census, scores = row

    if scores is None:
        raise HTTPException(
            status_code=503,
            detail="Scores not yet computed for this region. Run backfill_scores.",
        )

    return {
        "sa2_code":  sa2_code,
        "sa2_name":  region.sa2_name,
        "state":     region.state,
        "census_year": 2021,

        # Composite + dimension scores (all 0–10)
        "scores": {
            "investment_score":    _r(scores.investment_score),
            "liveability_score":   _r(scores.liveability_score),
            "education_score":     _r(scores.education_score),
            "growth_score":        _r(scores.growth_score),
            "demographic_score":   _r(scores.demographic_score),
            "housing_score":       _r(scores.housing_score),
            "infrastructure_score": _r(scores.infrastructure_score),
            "gentrification_index": _r(scores.gentrification_index),
        },

        # Key intermediates (explain the scores)
        "intermediates": {
            "edu_avg_icsea":          _r(scores.edu_avg_icsea),
            "edu_top_school_count":   scores.edu_top_school_count,
            "edu_secondary_count":    scores.edu_secondary_count,
            "edu_tertiary_count":     scores.edu_tertiary_count,
            "health_hospital_score":  _r(scores.health_hospital_score),
            "health_gp_count":        scores.health_gp_count,
            "infra_committed_aud":    scores.infra_committed_aud,
            "infra_project_count":    scores.infra_project_count,
            "transit_score_raw":      _r(scores.transit_score_raw),
        },

        # Census facts
        "facts": {
            "population":               census.population,
            "median_income":            census.median_income,
            "median_age":               census.median_age,
            "unemployment_pct":         _r(census.unemployment_pct),
            "uni_degree_pct":           _r(census.uni_degree_pct),
            "professionals_managers_pct": _r(census.professionals_managers_pct),
            "separate_house_pct":       _r(census.separate_house_pct),
            "flat_apartment_pct":       _r(census.flat_apartment_pct),
            "flat_high_rise_pct":       _r(census.flat_high_rise_pct),
            "renters_pct":              _r(census.renters_pct),
            "high_mortgage_stress_pct": _r(census.high_mortgage_stress_pct),
            "pop_growth_proj_pct":      _r(census.pop_growth_proj_pct),
            "building_approvals_1yr":   census.building_approvals_1yr,
            "pt_stop_train":            census.pt_stop_train,
            "pt_stop_bus":              census.pt_stop_bus,
            "osm_cafes":               census.osm_cafes,
            "osm_medical_centers":     census.osm_medical_centers,
            "seifa_irsd_decile":        census.seifa_irsd_decile,
            "seifa_ieo_decile":         census.seifa_ieo_decile,
        },

        "risk_flags":    scores.risk_flags or [],
        "tags":          _generate_tags(scores),
        "insight":       _generate_insight(region, census, scores),
        "score_version": scores.score_version,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _r(v: float | None, dp: int = 2) -> float | None:
    """Round a float to dp decimal places, pass None through."""
    return round(v, dp) if v is not None else None


def _generate_tags(scores: SuburbScore) -> list[str]:
    tags: list[str] = []
    inv = scores.investment_score or 0

    if inv >= 7.5:
        tags.append("Premium Investment")
    elif inv >= 6.5:
        tags.append("Strong Investment")
    elif inv >= 5.5:
        tags.append("Moderate Growth")
    else:
        tags.append("Emerging Opportunity")

    if (scores.gentrification_index or 0) >= 7.0:
        tags.append("Gentrifying")
    if (scores.growth_score or 0) >= 7.5:
        tags.append("High Growth")
    if (scores.liveability_score or 0) >= 7.5:
        tags.append("High Liveability")
    if (scores.education_score or 0) >= 7.5:
        tags.append("Strong Schools")
    if (scores.infrastructure_score or 0) >= 7.5:
        tags.append("Infrastructure Pipeline")

    return tags


def _generate_insight(
    region: SA2Region,
    census: ABSCEntensMetrics,
    scores: SuburbScore,
) -> str:
    """Generate a 2-3 sentence plain-English summary of the suburb's investment profile."""
    name = region.sa2_name or "This suburb"
    inv = scores.investment_score or 0

    # Lead sentence — overall verdict
    if inv >= 7.5:
        lead = f"{name} is a premium investment prospect"
    elif inv >= 6.5:
        lead = f"{name} presents a strong investment case"
    elif inv >= 5.5:
        lead = f"{name} shows moderate investment potential"
    else:
        lead = f"{name} is an emerging opportunity"

    # Find strongest dimension (exclude composite and gentrification)
    dims = {
        "liveability":    scores.liveability_score or 0,
        "growth":         scores.growth_score or 0,
        "education":      scores.education_score or 0,
        "demographic":    scores.demographic_score or 0,
        "housing":        scores.housing_score or 0,
        "infrastructure": scores.infrastructure_score or 0,
    }
    best_dim  = max(dims, key=dims.get)
    worst_dim = min(dims, key=dims.get)

    _dim_labels = {
        "liveability":    "liveability and amenity access",
        "growth":         "growth and gentrification signals",
        "education":      "education quality",
        "demographic":    "demographic fundamentals",
        "housing":        "housing market conditions",
        "infrastructure": "government infrastructure pipeline",
    }

    strength = f"driven by strong {_dim_labels[best_dim]}"
    if dims[best_dim] >= 7.0:
        middle = f", {strength}."
    else:
        middle = "."

    # Third sentence — notable fact
    facts = []
    if (scores.infra_committed_aud or 0) > 50_000_000:
        aud_m = int((scores.infra_committed_aud or 0) / 1_000_000)
        facts.append(f"${aud_m}M in committed government projects is linked to this SA2")
    if (scores.gentrification_index or 0) >= 7.5:
        facts.append("strong gentrification signals suggest above-average capital growth")
    if (scores.edu_avg_icsea or 0) >= 1100:
        facts.append(f"nearby schools average ICSEA {scores.edu_avg_icsea:.0f} — well above the national mean")
    if (scores.edu_top_school_count or 0) >= 3:
        facts.append(f"{scores.edu_top_school_count} high-performing schools (ICSEA ≥ 1100) are within or adjacent to this area")
    if census.pop_growth_proj_pct and census.pop_growth_proj_pct >= 15:
        facts.append(f"ABS projects {census.pop_growth_proj_pct:.0f}% population growth to 2031")
    if dims[worst_dim] < 4.0:
        facts.append(f"{_dim_labels[worst_dim]} is the primary drag on the overall score")

    third = f" {facts[0].capitalize()}." if facts else ""

    return lead + middle + third
