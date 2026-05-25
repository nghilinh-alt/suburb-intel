"""Common utility helpers used by scoring & API layers."""

from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from sqlalchemy.ext.asyncio import AsyncSession


def parse_jsonb(data_str: Any) -> dict:
    """Parse a JSON-ish string into a dict; empty dict on failure."""
    try:
        if data_str:
            return json.loads(str(data_str))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return {}


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Division that tolerates zero/None denominators."""
    if not denominator:
        return default
    return numerator / denominator


def format_currency(amount: int) -> str:
    """Locale-free currency formatter, ``$12,345`` style."""
    try:
        return f"${int(amount):,}"
    except (TypeError, ValueError):
        return "$0"


async def calculate_population_growth(
    db: AsyncSession, sa2_code: str, year: int
) -> float:
    """Year-over-year population growth rate (percent) for a suburb.

    Requires both `year` and `year-1` rows in `abs_census_metrics`; returns 0.0
    if either is missing.
    """
    from app.db.models import ABSCEntensMetrics

    current = await db.get(ABSCEntensMetrics, (sa2_code, year))
    previous = await db.get(ABSCEntensMetrics, (sa2_code, year - 1))

    if not current or not previous or not previous.population:
        return 0.0

    current_pop = current.population or 0
    prev_pop = previous.population
    return safe_divide(current_pop - prev_pop, prev_pop) * 100


def get_industry_diversity(industry_profile: Optional[Mapping[str, float]]) -> float:
    """Sector-count diversity score (0-100). More distinct sectors = more diverse."""
    if not industry_profile:
        return 50.0
    num_sectors = len(industry_profile)
    return round(min(num_sectors / 8.0 * 100, 100), 2)


def calculate_employment_diversity(
    industry_profile: Optional[Mapping[str, float]],
) -> float:
    """Inverse-concentration diversity score (0-100)."""
    if not industry_profile:
        return 50.0
    max_share = max(industry_profile.values())
    diversity = (1 - max_share) * 100 + 25  # floor ~25, cap 100
    return round(min(diversity, 100), 2)


def calculate_household_pressure(renters_pct: float) -> float:
    """Housing-pressure proxy from renter percentage (capped at 100)."""
    return round(min((renters_pct or 0) * 0.85, 100), 2)
