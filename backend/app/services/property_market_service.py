"""Aggregations over `property_sales` for the suburb report's Property Market
and Housing sections. Works against whatever data is currently in the table —
today that's empty (PropRadar ingestion pending), populates automatically once
the loader runs.
"""

from __future__ import annotations

from statistics import median
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PropertySale

_MAX_HISTORY_MONTHS = 60  # 5 years


async def fetch_price_history(db: AsyncSession, sa2_code: str) -> List[Dict[str, Any]]:
    """Monthly median sold price + sale count, oldest to newest, capped at 5 years.

    Grouped from raw `sold_date`/`sold_price` rather than a precomputed
    column, so it reflects whatever range of history the data source
    actually provides (PropRadar's free tier may only cover recent months).
    """
    stmt = (
        select(PropertySale.sold_date, PropertySale.sold_price)
        .where(
            PropertySale.sa2_code == sa2_code,
            PropertySale.sold_date.isnot(None),
            PropertySale.sold_price.isnot(None),
        )
        .order_by(PropertySale.sold_date.asc())
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return []

    by_month: Dict[str, List[int]] = {}
    for sold_date, sold_price in rows:
        period = sold_date[:7]  # "YYYY-MM"
        by_month.setdefault(period, []).append(sold_price)

    periods = sorted(by_month.keys())[-_MAX_HISTORY_MONTHS:]
    return [
        {
            "period": period,
            "median_price": round(median(by_month[period])),
            "sale_count": len(by_month[period]),
        }
        for period in periods
    ]


def _house_type_label(property_type: str | None, bedrooms: int | None) -> str | None:
    """Bucket a listing into a human-readable house-type label.

    Bucket boundaries are a reasonable default (mirrors common real-estate
    listing categories) — adjust freely once real data shows what's useful.
    """
    if property_type is None or bedrooms is None:
        return None
    pt = property_type.lower()

    if pt == "unit":
        if bedrooms <= 1:
            return "1 Bed Apartment"
        if bedrooms == 2:
            return "2 Bed Apartment"
        return "3+ Bed Apartment"

    if pt == "townhouse":
        if bedrooms <= 1:
            return "1 Bed Townhouse"
        if bedrooms <= 4:
            return "2-4 Bed Townhouse"
        return "5+ Bed Townhouse"

    if pt == "house":
        if bedrooms <= 2:
            return "2 Bed House"
        if bedrooms <= 5:
            return "3-5 Bed House"
        return "6+ Bed House"

    return f"{bedrooms} Bed {property_type.title()}"


async def fetch_house_type_breakdown(db: AsyncSession, sa2_code: str) -> List[Dict[str, Any]]:
    """Median sold price + count per house-type bucket (e.g. "2 Bed Apartment",
    "2-4 Bed Townhouse", "3-5 Bed House"), sorted by sale count descending."""
    stmt = select(PropertySale.property_type, PropertySale.bedrooms, PropertySale.sold_price).where(
        PropertySale.sa2_code == sa2_code,
        PropertySale.property_type.isnot(None),
        PropertySale.bedrooms.isnot(None),
        PropertySale.sold_price.isnot(None),
    )
    rows = (await db.execute(stmt)).all()

    buckets: Dict[str, List[int]] = {}
    for property_type, bedrooms, sold_price in rows:
        label = _house_type_label(property_type, bedrooms)
        if label is None:
            continue
        buckets.setdefault(label, []).append(sold_price)

    results = [
        {"label": label, "median_price": round(median(prices)), "sale_count": len(prices)}
        for label, prices in buckets.items()
    ]
    results.sort(key=lambda r: r["sale_count"], reverse=True)
    return results


_LAND_SIZE_BANDS = [
    ("Under 400m²", None, 400),
    ("400-600m²", 400, 600),
    ("600-800m²", 600, 800),
    ("800m²+", 800, None),
]


async def fetch_land_size_breakdown(db: AsyncSession, sa2_code: str) -> List[Dict[str, Any]]:
    """Sale counts bucketed by land size band. Empty until PropRadar provides
    `land_size_sqm` per listing — field name unverified (see
    propradar_sold_loader.py's `_parse_listing`), populates automatically
    once real data lands."""
    stmt = select(PropertySale.land_size_sqm).where(
        PropertySale.sa2_code == sa2_code,
        PropertySale.land_size_sqm.isnot(None),
    )
    sizes = [row[0] for row in (await db.execute(stmt)).all()]
    if not sizes:
        return []

    results = []
    for label, lo, hi in _LAND_SIZE_BANDS:
        count = sum(1 for s in sizes if (lo is None or s >= lo) and (hi is None or s < hi))
        if count > 0:
            results.append({"label": label, "sale_count": count})
    return results
