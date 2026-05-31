"""Suburb-group endpoint — returns aggregated view of a real suburb
that may span multiple SA2 statistical areas.

GET /suburb-group/{suburb_id}   e.g. /suburb-group/keysborough-vic
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SuburbAggregate
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{suburb_id}")
async def suburb_group_report(
    suburb_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return population-weighted aggregate report for a suburb."""

    agg = await db.get(SuburbAggregate, suburb_id)
    if agg is None:
        raise HTTPException(
            status_code=404,
            detail=f"Suburb '{suburb_id}' not found. Use /search to find valid suburb slugs.",
        )

    scores = {
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

        "scores": scores,

        "facts": {
            "median_income":      _r(agg.median_income),
            "median_age":         _r(agg.median_age),
            "unemployment_pct":   _r(agg.unemployment_pct),
            "uni_degree_pct":     _r(agg.uni_degree_pct),
            "pop_growth_proj_pct": _r(agg.pop_growth_proj_pct),
        },

        "risk_flags":    agg.risk_flags or [],
        "tags":          _generate_tags(agg),
        "insight":       _generate_insight(agg),
        "score_version": agg.score_version,
        "note":          f"Scores are population-weighted averages across {agg.sa2_count} ABS statistical areas." if agg.sa2_count > 1 else None,
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
        "liveability":    agg.liveability_score or 0,
        "growth":         agg.growth_score or 0,
        "education":      agg.education_score or 0,
        "demographic":    agg.demographic_score or 0,
        "housing":        agg.housing_score or 0,
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
    best = max(dims, key=dims.get)
    middle = f", driven by strong {labels[best]}." if dims[best] >= 7.0 else "."

    facts = []
    if (agg.pop_growth_proj_pct or 0) >= 15:
        facts.append(f"ABS projects {agg.pop_growth_proj_pct:.0f}% population growth to 2031")
    if (agg.gentrification_index or 0) >= 7.5:
        facts.append("strong gentrification signals suggest above-average capital growth")
    third = f" {facts[0].capitalize()}." if facts else ""

    multi = f" Covers {agg.sa2_count} ABS statistical areas." if agg.sa2_count > 1 else ""
    return lead + middle + third + multi
