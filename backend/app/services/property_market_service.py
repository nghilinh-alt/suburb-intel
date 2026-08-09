"""Aggregations over `property_sales` for the suburb report's Property Market
and Housing sections. Works against whatever data is currently in the table —
today that's empty (PropRadar ingestion pending), populates automatically once
the loader runs.
"""

from __future__ import annotations

from statistics import mean, median
from typing import Any, Dict, List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import PropertySale

_MAX_HISTORY_MONTHS = 60  # 5 years

# Bedrooms at or above this collapse into a single "N+" bucket.
_MAX_BED_BUCKET = 6


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


# PropRadar's real property_type values (verified against a live pilot pull
# across 9 suburbs, 2026-07-08) are far more varied than the original 3-value
# guess: house, apartment, unit, townhouse, villa, "duplex+semi detached",
# residential+land, flat. Normalize the synonyms so "apartment"/"unit"/"flat"
# share one bucket set instead of "unit" being the only one that got bucketed
# and everything else falling into an ungrouped per-bedroom-count fallback.
_TYPE_LABELS: dict[str, str] = {
    "house": "House",
    "unit": "Apartment",
    "apartment": "Apartment",
    "flat": "Apartment",
    "townhouse": "Townhouse",
    "villa": "Villa",
    "duplex+semi detached": "Duplex/Semi-Detached",
}


def _house_type_label(property_type: str | None, bedrooms: int | None) -> str | None:
    """Bucket a listing into a human-readable house-type label.

    Bucket boundaries are a reasonable default (mirrors common real-estate
    listing categories) — adjust freely once real data shows what's useful.
    Unrecognized types (e.g. "residential+land") fall back to a plain
    "{bedrooms} Bed {Type}" label rather than being dropped.
    """
    if property_type is None or bedrooms is None:
        return None

    type_label = _TYPE_LABELS.get(property_type.lower())
    if type_label is None:
        return f"{bedrooms} Bed {property_type.title()}"

    if type_label == "Apartment":
        if bedrooms <= 1:
            return f"1 Bed {type_label}"
        if bedrooms == 2:
            return f"2 Bed {type_label}"
        return f"3+ Bed {type_label}"

    if type_label == "House":
        if bedrooms <= 2:
            return f"2 Bed {type_label}"
        if bedrooms <= 5:
            return f"3-5 Bed {type_label}"
        return f"6+ Bed {type_label}"

    # Townhouse / Villa / Duplex-Semi-Detached share one range shape
    if bedrooms <= 1:
        return f"1 Bed {type_label}"
    if bedrooms <= 4:
        return f"2-4 Bed {type_label}"
    return f"5+ Bed {type_label}"


async def fetch_price_by_type_bedroom(db: AsyncSession, sa2_code: str) -> Dict[str, Any]:
    """Median & average sold price per (property type, bedroom count), with each
    segment ratio (suburb_median / group_median) against the suburb-wide median
    of all sold listings. Empty until property_sales has data for this SA2."""
    stmt = select(PropertySale.property_type, PropertySale.bedrooms, PropertySale.sold_price).where(
        PropertySale.sa2_code == sa2_code,
        PropertySale.property_type.isnot(None),
        PropertySale.bedrooms.isnot(None),
        PropertySale.sold_price.isnot(None),
    )
    rows = (await db.execute(stmt)).all()
    if not rows:
        return {"suburb_median": None, "groups": []}

    suburb_median = round(median([price for _, _, price in rows]))

    buckets: Dict[tuple, List[int]] = {}
    for property_type, bedrooms, sold_price in rows:
        type_label = _TYPE_LABELS.get(property_type.lower(), property_type.title())
        bed = min(bedrooms, _MAX_BED_BUCKET)
        buckets.setdefault((type_label, bed), []).append(sold_price)

    groups: List[Dict[str, Any]] = []
    for (type_label, bed), prices in buckets.items():
        group_median = round(median(prices))
        bed_label = f"{_MAX_BED_BUCKET}+" if bed >= _MAX_BED_BUCKET else str(bed)
        groups.append(
            {
                "type": type_label,
                "bedrooms": bed,
                "label": f"{bed_label} Bed {type_label}",
                "median_price": group_median,
                "avg_price": round(mean(prices)),
                "sale_count": len(prices),
                "ratio_to_suburb_median": round(suburb_median / group_median, 2) if group_median else None,
            }
        )

    groups.sort(key=lambda g: (g["type"], g["bedrooms"]))
    return {"suburb_median": suburb_median, "groups": groups}


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


def _exact_spec_key(property_type: str | None, bedrooms: int | None, bathrooms: int | None, parking: int | None) -> tuple | None:
    """Bucket a listing into its exact spec — a (type_label, bedrooms, bathrooms,
    parking) key, e.g. ("House", 5, 3, 2) -> "5 Bed / 3 Bath / 2 Garage House".
    Unlike `_house_type_label`'s coarse bedroom ranges, this is the precise
    bed/bath/parking combo. Reuses the same type-name normalization
    (apartment/unit/flat -> "Apartment", etc.) so the two views stay
    consistent with each other.
    """
    if property_type is None or bedrooms is None or bathrooms is None:
        return None
    type_label = _TYPE_LABELS.get(property_type.lower(), property_type.title())
    return (type_label, bedrooms, bathrooms, parking)


def _exact_spec_label(spec_key: tuple) -> str:
    type_label, bedrooms, bathrooms, parking = spec_key
    spec = f"{bedrooms} Bed / {bathrooms} Bath"
    if parking is not None:
        spec += f" / {parking} Garage"
    return f"{spec} {type_label}"


def _exact_spec_sort_key(spec_key: tuple) -> tuple:
    """Sort specs progressively — bedrooms, then bathrooms, then parking
    (unknown parking sorts before any known count), then type name — e.g.
    1 Bed/1 Bath, 1 Bed/2 Bath, 2 Bed/1 Bath, ... rather than by popularity."""
    type_label, bedrooms, bathrooms, parking = spec_key
    return (bedrooms, bathrooms, parking if parking is not None else -1, type_label)


async def fetch_detailed_specs(db: AsyncSession, sa2_code: str) -> List[Dict[str, Any]]:
    """Median sold price + count per EXACT bed/bath/parking/type combo (e.g.
    "2 Bed / 1 Bath Apartment", "5 Bed / 3 Bath / 2 Garage House") — finer
    grained than `fetch_house_type_breakdown`'s bedroom-range buckets.
    Sorted progressively by bed/bath/parking rather than by popularity.
    Derived entirely from data already ingested via propradar_sold — no
    extra API calls."""
    stmt = select(
        PropertySale.property_type, PropertySale.bedrooms, PropertySale.bathrooms,
        PropertySale.parking, PropertySale.sold_price,
    ).where(
        PropertySale.sa2_code == sa2_code,
        PropertySale.property_type.isnot(None),
        PropertySale.bedrooms.isnot(None),
        PropertySale.bathrooms.isnot(None),
        PropertySale.sold_price.isnot(None),
    )
    rows = (await db.execute(stmt)).all()

    buckets: Dict[tuple, List[int]] = {}
    for property_type, bedrooms, bathrooms, parking, sold_price in rows:
        spec_key = _exact_spec_key(property_type, bedrooms, bathrooms, parking)
        if spec_key is None:
            continue
        buckets.setdefault(spec_key, []).append(sold_price)

    sorted_keys = sorted(buckets.keys(), key=_exact_spec_sort_key)
    return [
        {
            "label": _exact_spec_label(spec_key),
            "median_price": round(median(buckets[spec_key])),
            "sale_count": len(buckets[spec_key]),
        }
        for spec_key in sorted_keys
    ]


async def fetch_price_history_by_spec(db: AsyncSession, sa2_code: str) -> List[Dict[str, Any]]:
    """Monthly median sold price + sale count per EXACT bed/bath/parking/type
    combo, oldest to newest, capped at 5 years — the per-spec equivalent of
    `fetch_price_history`, since blending e.g. a 2 bed apartment with a 5 bed
    house into one trend line hides more than it shows. Sorted progressively
    by bed/bath/parking, same order as `fetch_detailed_specs`."""
    stmt = select(
        PropertySale.property_type, PropertySale.bedrooms, PropertySale.bathrooms,
        PropertySale.parking, PropertySale.sold_price, PropertySale.sold_date,
    ).where(
        PropertySale.sa2_code == sa2_code,
        PropertySale.property_type.isnot(None),
        PropertySale.bedrooms.isnot(None),
        PropertySale.bathrooms.isnot(None),
        PropertySale.sold_price.isnot(None),
        PropertySale.sold_date.isnot(None),
    )
    rows = (await db.execute(stmt)).all()

    buckets: Dict[tuple, Dict[str, List[int]]] = {}
    for property_type, bedrooms, bathrooms, parking, sold_price, sold_date in rows:
        spec_key = _exact_spec_key(property_type, bedrooms, bathrooms, parking)
        if spec_key is None:
            continue
        period = sold_date[:7]  # "YYYY-MM"
        by_month = buckets.setdefault(spec_key, {})
        by_month.setdefault(period, []).append(sold_price)

    sorted_keys = sorted(buckets.keys(), key=_exact_spec_sort_key)
    results = []
    for spec_key in sorted_keys:
        by_month = buckets[spec_key]
        periods = sorted(by_month.keys())[-_MAX_HISTORY_MONTHS:]
        history = [
            {
                "period": period,
                "median_price": round(median(by_month[period])),
                "sale_count": len(by_month[period]),
            }
            for period in periods
        ]
        results.append({"label": _exact_spec_label(spec_key), "history": history})
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
