"""Suburb-group endpoint — aggregated view of a real suburb
that may span multiple SA2 statistical areas.

GET /suburb-group/{suburb_id}   e.g. /suburb-group/keysborough-vic
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ABSCEntensMetrics, SuburbAggregate, SuburbScore, SA2Region
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{suburb_id}")
async def suburb_group_report(
    suburb_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return population-weighted aggregate report for a suburb,
    including per-SA2 score breakdown and dimension-level input facts."""

    agg = await db.get(SuburbAggregate, suburb_id)
    if agg is None:
        raise HTTPException(
            status_code=404,
            detail=f"Suburb '{suburb_id}' not found. Use /search to find valid suburb slugs.",
        )

    # Fetch suburb_scores + census facts for each constituent SA2
    sa2_codes = agg.sa2_codes or []
    stmt = (
        select(SuburbScore, ABSCEntensMetrics, SA2Region.sa2_name)
        .join(ABSCEntensMetrics,
              (ABSCEntensMetrics.sa2_code == SuburbScore.sa2_code) &
              (ABSCEntensMetrics.year == 2021),
              isouter=True)
        .join(SA2Region, SA2Region.sa2_code == SuburbScore.sa2_code, isouter=True)
        .where(SuburbScore.sa2_code.in_(sa2_codes))
    )
    rows = (await db.execute(stmt)).all()

    # Build per-SA2 breakdown
    sa2_breakdown = []
    for scores, census, sa2_name in rows:
        pop = census.population if census else None
        sa2_breakdown.append({
            "sa2_code": scores.sa2_code,
            "sa2_name": sa2_name,
            "population": pop,
            "scores": {
                "investment_score":     _r(scores.investment_score),
                "liveability_score":    _r(scores.liveability_score),
                "education_score":      _r(scores.education_score),
                "growth_score":         _r(scores.growth_score),
                "demographic_score":    _r(scores.demographic_score),
                "housing_score":        _r(scores.housing_score),
                "infrastructure_score": _r(scores.infrastructure_score),
                "gentrification_index": _r(scores.gentrification_index),
            },
            # Intermediates — what drove each dimension score
            "intermediates": {
                "transit_score_raw":     _r(scores.transit_score_raw),
                "edu_avg_icsea":         _r(scores.edu_avg_icsea),
                "edu_top_school_count":  scores.edu_top_school_count,
                "edu_secondary_count":   scores.edu_secondary_count,
                "edu_tertiary_count":    scores.edu_tertiary_count,
                "health_hospital_score": _r(scores.health_hospital_score),
                "health_gp_count":       scores.health_gp_count,
                "infra_committed_aud":   scores.infra_committed_aud,
                "infra_project_count":   scores.infra_project_count,
            },
            # Key census facts for dimension explanations
            "facts": {
                "population":               pop,
                "median_income":            census.median_income if census else None,
                "median_age":               _r(census.median_age) if census else None,
                "unemployment_pct":         _r(census.unemployment_pct) if census else None,
                "uni_degree_pct":           _r(census.uni_degree_pct) if census else None,
                "professionals_managers_pct": _r(census.professionals_managers_pct) if census else None,
                "separate_house_pct":       _r(census.separate_house_pct) if census else None,
                "flat_apartment_pct":       _r(census.flat_apartment_pct) if census else None,
                "flat_high_rise_pct":       _r(census.flat_high_rise_pct) if census else None,
                "renters_pct":              _r(census.renters_pct) if census else None,
                "high_mortgage_stress_pct": _r(census.high_mortgage_stress_pct) if census else None,
                "high_rent_stress_pct":     _r(census.high_rent_stress_pct) if census else None,
                "social_housing_pct":       _r(census.social_housing_pct) if census else None,
                "pop_growth_proj_pct":      _r(census.pop_growth_proj_pct) if census else None,
                "building_approvals_1yr":   census.building_approvals_1yr if census else None,
                "pt_stop_train":            census.pt_stop_train if census else None,
                "pt_stop_tram":             census.pt_stop_tram if census else None,
                "pt_stop_bus":              census.pt_stop_bus if census else None,
                "osm_cafes":                census.osm_cafes if census else None,
                "osm_restaurants":          census.osm_restaurants if census else None,
                "osm_parks":                census.osm_parks if census else None,
                "osm_gyms":                 census.osm_gyms if census else None,
                "osm_medical_centers":      census.osm_medical_centers if census else None,
                "osm_pharmacies":           census.osm_pharmacies if census else None,
                "osm_hospitals":            census.osm_hospitals if census else None,
                "seifa_irsd_decile":        census.seifa_irsd_decile if census else None,
                "seifa_irsad_decile":       census.seifa_irsad_decile if census else None,
                "seifa_ieo_decile":         census.seifa_ieo_decile if census else None,
            },
            "risk_flags": scores.risk_flags or [],
        })

    # Sort by SA2 name for consistent ordering
    sa2_breakdown.sort(key=lambda x: x["sa2_name"] or "")

    # For single SA2 — surface the full breakdown as top-level intermediates/facts too
    top_intermediates = sa2_breakdown[0]["intermediates"] if len(sa2_breakdown) == 1 else {}
    top_facts_detail  = sa2_breakdown[0]["facts"]         if len(sa2_breakdown) == 1 else {}

    scores_agg = {
        "investment_score":     _r(agg.investment_score),
        "liveability_score":    _r(agg.liveability_score),
        "education_score":      _r(agg.education_score),
        "growth_score":         _r(agg.growth_score),
        "demographic_score":    _r(agg.demographic_score),
        "housing_score":        _r(agg.housing_score),
        "infrastructure_score": _r(agg.infrastructure_score),
        "gentrification_index": _r(agg.gentrification_index),
    }

    return {
        "suburb_id":   suburb_id,
        "suburb_name": agg.suburb_name,
        "state":       agg.state,
        "sa2_count":   agg.sa2_count,
        "sa2_codes":   agg.sa2_codes,
        "sa2_names":   agg.sa2_names,
        "population":  agg.population,
        "is_aggregate": agg.sa2_count > 1,

        "scores":      scores_agg,
        "sa2_breakdown": sa2_breakdown,

        # Weighted averages for top-level facts panel
        "facts": {
            "median_income":      _r(agg.median_income),
            "median_age":         _r(agg.median_age),
            "unemployment_pct":   _r(agg.unemployment_pct),
            "uni_degree_pct":     _r(agg.uni_degree_pct),
            "pop_growth_proj_pct": _r(agg.pop_growth_proj_pct),
            # Granular facts (single SA2 only, null for multi)
            **top_facts_detail,
        },
        "intermediates": top_intermediates,

        "risk_flags":    agg.risk_flags or [],
        "tags":          _generate_tags(agg),
        "insight":       _generate_insight(agg),
        "score_version": agg.score_version,
        "note": f"Scores are population-weighted averages across {agg.sa2_count} ABS statistical areas." if agg.sa2_count > 1 else None,
    }


def _r(v: float | None) -> float | None:
    return round(v, 2) if v is not None else None


def _generate_tags(agg: SuburbAggregate) -> list[str]:
    tags: list[str] = []
    inv = agg.investment_score or 0
    if inv >= 7.5:   tags.append("Premium Investment")
    elif inv >= 6.5: tags.append("Strong Investment")
    elif inv >= 5.5: tags.append("Moderate Growth")
    else:            tags.append("Emerging Opportunity")
    if (agg.gentrification_index or 0) >= 7.0: tags.append("Gentrifying")
    if (agg.growth_score or 0) >= 7.5:         tags.append("High Growth")
    if (agg.liveability_score or 0) >= 7.5:    tags.append("High Liveability")
    if (agg.education_score or 0) >= 7.5:      tags.append("Strong Schools")
    if (agg.infrastructure_score or 0) >= 7.5: tags.append("Infrastructure Pipeline")
    return tags


def _generate_insight(agg: SuburbAggregate) -> str:
    name = agg.suburb_name
    inv  = agg.investment_score or 0
    if inv >= 7.5:   lead = f"{name} is a premium investment prospect"
    elif inv >= 6.5: lead = f"{name} presents a strong investment case"
    elif inv >= 5.5: lead = f"{name} shows moderate investment potential"
    else:            lead = f"{name} is an emerging opportunity"

    dims = {
        "liveability": agg.liveability_score or 0,
        "growth":      agg.growth_score or 0,
        "education":   agg.education_score or 0,
        "demographic": agg.demographic_score or 0,
        "housing":     agg.housing_score or 0,
        "infrastructure": agg.infrastructure_score or 0,
    }
    labels = {
        "liveability": "liveability and amenity access",
        "growth": "growth and gentrification signals",
        "education": "education quality",
        "demographic": "demographic fundamentals",
        "housing": "housing market conditions",
        "infrastructure": "government infrastructure pipeline",
    }
    best  = max(dims, key=dims.get)
    worst = min(dims, key=dims.get)
    middle = f", driven by strong {labels[best]}." if dims[best] >= 7.0 else "."

    facts = []
    if (agg.pop_growth_proj_pct or 0) >= 15:
        facts.append(f"ABS projects {agg.pop_growth_proj_pct:.0f}% population growth to 2031")
    if (agg.gentrification_index or 0) >= 7.5:
        facts.append("strong gentrification signals suggest above-average capital growth")
    if dims[worst] < 4.0:
        facts.append(f"{labels[worst]} is the primary drag on the overall score")
    third = f" {facts[0].capitalize()}." if facts else ""
    multi = f" Covers {agg.sa2_count} ABS statistical areas." if agg.sa2_count > 1 else ""
    return lead + middle + third + multi
