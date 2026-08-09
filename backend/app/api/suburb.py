"""Suburb investment-report endpoint.

Returns raw, section-grouped data rather than the 0-100 composite scores
(investment/demographic/economic/housing/resilience/gov scores are still
computed internally to drive `insight`/`tags`/`risk_flags` text, but the
numbers themselves are not part of the response — see each section below
for the underlying metrics a reader would actually want per topic).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.gov_score import analyze_risk_flags, generate_insight
from app.core.momentum import (
    classify_growth_yield_quadrant,
    classify_property_cycle_position,
    compute_momentum,
    compute_supply_scarcity,
    generate_investment_snapshot,
)
from app.core.scoring import calculate_investment_score
from app.db.models import (
    ABSCEntensMetrics,
    InfrastructureProject,
    PropertySale,
    SA2ProjectLink,
    SA2Region,
)
from app.db.session import get_db
from app.services.momentum_service import fetch_neighborhood_momentum, fetch_sale_velocity
from app.services.property_market_service import (
    fetch_detailed_specs,
    fetch_house_type_breakdown,
    fetch_land_size_breakdown,
    fetch_price_by_type_bedroom,
    fetch_price_history,
    fetch_price_history_by_spec,
)
from app.services.neighbour_comparison_service import fetch_neighbour_comparison
from app.services.regional_comparison_service import fetch_regional_comparison
from app.services.school_rating_service import fetch_school_percentile
from app.services.points_of_interest_service import fetch_points_of_interest
from app.services.school_service import fetch_schools
from app.services.suburb_market_stats_service import fetch_rental_market_history, fetch_suburb_market_stats
from app.services.scoring_service import build_features, fetch_linked_projects

logger = logging.getLogger(__name__)
router = APIRouter()

_CUISINE_COLUMNS = {
    "chinese": "osm_rest_chinese",
    "indian": "osm_rest_indian",
    "thai": "osm_rest_thai",
    "italian": "osm_rest_italian",
    "japanese": "osm_rest_japanese",
    "vietnamese": "osm_rest_vietnamese",
    "korean": "osm_rest_korean",
    "greek": "osm_rest_greek",
    "mexican": "osm_rest_mexican",
    "middle_eastern": "osm_rest_middle_eastern",
    "seafood": "osm_rest_seafood",
}


@router.get("/{sa2_code}")
async def suburb_report(
    sa2_code: str,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Return a section-grouped investment report for an SA2 region."""
    try:
        stmt = (
            select(SA2Region, ABSCEntensMetrics)
            .join(
                ABSCEntensMetrics,
                (ABSCEntensMetrics.sa2_code == SA2Region.sa2_code)
                & (ABSCEntensMetrics.year == 2021),
            )
            .where(SA2Region.sa2_code == sa2_code)
        )
        result = await db.execute(stmt)
        row = result.first()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"SA2 region '{sa2_code}' not found. Use /search to find valid codes.",
            )
        region, m = row

        gov_projects = await fetch_linked_projects(db, sa2_code)
        features = build_features(m, gov_projects)
        scores = calculate_investment_score(features)

        census_dict = _census_to_dict(m)
        risk_flags = analyze_risk_flags(gov_projects, census_dict)
        insight = generate_insight(scores, census_dict, gov_projects)

        projects = await _fetch_projects_full(db, sa2_code)
        recent_sales = await _fetch_recent_sales(db, sa2_code)
        price_history = await fetch_price_history(db, sa2_code)
        price_history_by_spec = await fetch_price_history_by_spec(db, sa2_code)
        house_type_breakdown = await fetch_house_type_breakdown(db, sa2_code)
        detailed_specs = await fetch_detailed_specs(db, sa2_code)
        land_size_breakdown = await fetch_land_size_breakdown(db, sa2_code)
        price_by_type_bedroom = await fetch_price_by_type_bedroom(db, sa2_code)
        sale_velocity = await fetch_sale_velocity(db, sa2_code)
        market_stats = await fetch_suburb_market_stats(db, sa2_code)
        supply_scarcity = [
            {
                "suburb_name": stats["suburb_name"],
                **compute_supply_scarcity(
                    stock_on_market_pct_house=stats.get("stock_on_market_pct_house"),
                    stock_on_market_pct_unit=stats.get("stock_on_market_pct_unit"),
                    inventory_months_house=stats.get("inventory_months_house"),
                    inventory_months_unit=stats.get("inventory_months_unit"),
                    building_approvals_1yr=m.building_approvals_1yr,
                    population=m.population,
                ),
            }
            for stats in market_stats
        ]
        momentum_composite = [
            {
                "suburb_name": stats["suburb_name"],
                **compute_momentum(
                    sale_velocity_trend_pct=sale_velocity["trend_pct"],
                    growth_house_1y_pct=stats.get("growth_house_1y_pct"),
                    growth_unit_1y_pct=stats.get("growth_unit_1y_pct"),
                    scarcity_score=scarcity["scarcity_score"],
                    heat_score_house=stats.get("heat_score_house"),
                    heat_score_unit=stats.get("heat_score_unit"),
                ),
            }
            for stats, scarcity in zip(market_stats, supply_scarcity)
        ]
        growth_yield_quadrant = [
            {
                "suburb_name": stats["suburb_name"],
                **classify_growth_yield_quadrant(
                    growth_house_1y_pct=stats.get("growth_house_1y_pct"),
                    gross_yield_house_pct=stats.get("gross_yield_house_pct"),
                ),
            }
            for stats in market_stats
        ]
        property_cycle = [
            {
                "suburb_name": m["suburb_name"],
                **classify_property_cycle_position(
                    growth_signal=m["components"]["growth"]["signal"],
                    velocity_signal=m["components"]["sale_velocity"]["signal"],
                ),
            }
            for m in momentum_composite
        ]
        investment_snapshot = (
            generate_investment_snapshot(
                momentum_phase=momentum_composite[0]["phase"],
                growth_house_1y_pct=market_stats[0].get("growth_house_1y_pct"),
                gross_yield_house_pct=market_stats[0].get("gross_yield_house_pct"),
                scarcity_score=supply_scarcity[0]["scarcity_score"],
                days_on_market_house=market_stats[0].get("days_on_market_house"),
            )
            if market_stats
            else None
        )
        neighborhood_momentum = await fetch_neighborhood_momentum(db, sa2_code)
        rental_market = await fetch_rental_market_history(db, sa2_code)
        regional_comparison = await fetch_regional_comparison(db, sa2_code)
        neighbour_comparison = await fetch_neighbour_comparison(db, sa2_code)
        schools = await fetch_schools(db, sa2_code)
        school_percentile = await fetch_school_percentile(db, sa2_code)
        points_of_interest = await fetch_points_of_interest(db, sa2_code)

        return {
            "sa2_code": sa2_code,
            "sa2_name": region.sa2_name,
            "state": region.state,
            "census_year": 2021,
            "show_census_sections": settings.SHOW_CENSUS_SECTIONS,
            "insight": insight,
            "investment_snapshot": investment_snapshot,
            "risk_flags": risk_flags,
            "tags": _generate_tags(scores),
            "regional_comparison": regional_comparison,
            "neighbour_comparison": neighbour_comparison,
            "location": {
                "distance_to_cbd_km": region.distance_to_cbd_km,
            },
            "momentum": {
                "sale_velocity": sale_velocity,
                "supply_scarcity": supply_scarcity,
                "composite": momentum_composite,
                "neighborhood": neighborhood_momentum,
                "growth_yield_quadrant": growth_yield_quadrant,
                "property_cycle": property_cycle,
            },
            "market_stats": market_stats,
            "rental_market": rental_market,
            "property_market": {
                "building_approvals_1yr": m.building_approvals_1yr,
                "recent_sales": recent_sales,
                "recent_sales_available": len(recent_sales) > 0,
                "price_history": price_history,
                "price_history_by_spec": price_history_by_spec,
                "detailed_specs": detailed_specs,
                "land_size_breakdown": land_size_breakdown,
                "by_type_bedroom": price_by_type_bedroom,
            },
            "investment_outlook": {
                "pop_growth_5yr": m.pop_growth_5yr,
                "pop_proj_2026": m.pop_proj_2026,
                "pop_proj_2031": m.pop_proj_2031,
                "pop_growth_proj_pct": m.pop_growth_proj_pct,
                "building_approvals_1yr": m.building_approvals_1yr,
                "distance_to_cbd_km": region.distance_to_cbd_km,
            },
            "demographics": {
                "population": m.population,
                "median_age": m.median_age,
                "avg_household_size": m.avg_household_size,
                "families_with_children_pct": m.families_with_children_pct,
                "overseas_born_pct": m.overseas_born_pct,
                "moved_in_1yr_pct": m.moved_in_1yr_pct,
                "moved_in_5yr_pct": m.moved_in_5yr_pct,
                "uni_degree_pct": m.uni_degree_pct,
                "professionals_managers_pct": m.professionals_managers_pct,
            },
            "economy": {
                "median_income": m.median_income,
                "unemployment_pct": m.unemployment_pct,
            },
            "housing": {
                "renters_pct": m.renters_pct,
                "owners_pct": m.owners_pct,
                "median_rent_weekly": m.median_rent_weekly,
                "median_mortgage_monthly": m.median_mortgage_monthly,
                "high_rent_stress_pct": m.high_rent_stress_pct,
                "high_mortgage_stress_pct": m.high_mortgage_stress_pct,
                "separate_house_pct": m.separate_house_pct,
                "flat_apartment_pct": m.flat_apartment_pct,
                "one_bedroom_pct": m.one_bedroom_pct,
                "social_housing_pct": m.social_housing_pct,
                "by_house_type": house_type_breakdown,
            },
            "community": {
                "seifa_irsd_score": m.seifa_irsd_score,
                "seifa_irsd_decile": m.seifa_irsd_decile,
                "seifa_irsad_score": m.seifa_irsad_score,
                "seifa_irsad_decile": m.seifa_irsad_decile,
                "seifa_ier_decile": m.seifa_ier_decile,
                "seifa_ieo_decile": m.seifa_ieo_decile,
            },
            "government_investment": {
                "projects": projects,
            },
            "schools": {
                "avg_school_icsea": m.avg_school_icsea,
                "num_schools": m.num_schools,
                "local": schools["local"],
                "nearby": schools["nearby"],
                "state_percentile": school_percentile,
            },
            "amenities": _build_amenities(m),
            "points_of_interest": points_of_interest,
            "transport": {
                "pt_stop_train": m.pt_stop_train,
                "pt_stop_tram": m.pt_stop_tram,
                "pt_stop_bus": m.pt_stop_bus,
                "pt_stop_ferry": m.pt_stop_ferry,
                "car_commute_pct": m.car_commute_pct,
                "pt_commute_pct": m.pt_commute_pct,
                "work_from_home_pct": m.work_from_home_pct,
                "zero_car_dwellings_pct": m.zero_car_dwellings_pct,
                "distance_to_cbd_km": region.distance_to_cbd_km,
            },
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("Failed to generate suburb report for %s", sa2_code)
        raise HTTPException(status_code=500, detail=f"Error generating report: {e}") from e


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _census_to_dict(metrics: ABSCEntensMetrics) -> Dict[str, Any]:
    """SQLAlchemy model -> plain dict so downstream code can `.get()` safely."""
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


def _build_amenities(m: ABSCEntensMetrics) -> Dict[str, Any]:
    cuisines = {
        label: getattr(m, col)
        for label, col in _CUISINE_COLUMNS.items()
        if getattr(m, col)
    }
    return {
        "cafes": m.osm_cafes,
        "bakeries": m.osm_bakeries,
        "restaurants": m.osm_restaurants,
        "fast_food": m.osm_fast_food,
        "supermarkets": m.osm_supermarkets,
        "parks": m.osm_parks,
        "gyms": m.osm_gyms,
        "hospitals": m.osm_hospitals,
        "pharmacies": m.osm_pharmacies,
        "shopping_centres": m.osm_shopping_centres,
        "cuisines": cuisines,
    }


async def _fetch_projects_full(db: AsyncSession, sa2_code: str) -> List[Dict[str, Any]]:
    """Nearby infrastructure projects with full display fields (not just the
    scoring-oriented subset in scoring_service.fetch_linked_projects)."""
    stmt = (
        select(InfrastructureProject)
        .join(SA2ProjectLink, SA2ProjectLink.project_id == InfrastructureProject.project_id)
        .where(SA2ProjectLink.sa2_code == sa2_code)
        .order_by(InfrastructureProject.value_aud.desc().nulls_last())
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "name": p.name,
            "type": p.type,
            "status": p.status,
            "value_aud": p.value_aud,
            "timing": p.timing,
            "expected_start": p.expected_start,
            "expected_end": p.expected_end,
        }
        for p in rows
    ]


async def _fetch_recent_sales(db: AsyncSession, sa2_code: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Recent PropRadar-sourced sold listings for this SA2. Empty today (no
    PROPRADAR_API_KEY configured yet) — populates automatically once Phase 2's
    ingestion loader runs, no shape change needed."""
    stmt = (
        select(PropertySale)
        .where(PropertySale.sa2_code == sa2_code)
        .order_by(PropertySale.sold_date.desc().nulls_last())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [
        {
            "address": s.address,
            "bedrooms": s.bedrooms,
            "bathrooms": s.bathrooms,
            "property_type": s.property_type,
            "sold_price": s.sold_price,
            "sold_date": s.sold_date,
        }
        for s in rows
    ]
