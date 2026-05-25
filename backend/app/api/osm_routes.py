"""OSM Overpass amenity-density routes.

Mounted at `/search` by main.py so the public paths are
`/search/{suburb_name}/osm-*`.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from app.api.data_sources.osm_overpass import OSMOverpassDataSource

logger = logging.getLogger(__name__)
router = APIRouter()


def _osm_source() -> OSMOverpassDataSource:
    """Indirection so tests can monkey-patch the data source."""
    return OSMOverpassDataSource()


@router.get("/{suburb_name}/osm-amenity-density")
async def get_osm_amenity_density(suburb_name: str) -> Dict[str, Any]:
    """Aggregate amenity-density score (0-10) from OpenStreetMap."""
    osm_source = _osm_source()
    try:
        data = await osm_source.fetch_all_amenity_types(suburb_name)
        if data.get("error"):
            raise HTTPException(
                status_code=502, detail=f"Overpass API error: {data['error']}"
            )

        score = await osm_source.calculate_amenity_density_score(suburb_name)
        return {
            "suburb": suburb_name,
            "density_score": score,
            "amenities_breakdown": data.get("amenities", {}),
            "timestamp": data.get("timestamp"),
            "data_source": "OpenStreetMap Overpass API",
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001 - external API failure surface
        logger.exception("OSM amenity-density failed for %s", suburb_name)
        raise HTTPException(
            status_code=503, detail="Temporary service unavailable. Please try again later."
        ) from e


@router.get("/{suburb_name}/osm-cafe-density")
async def get_osm_cafe_density(suburb_name: str) -> Dict[str, Any]:
    """Cafe counts within 500m / 1km / 2km radii."""
    osm_source = _osm_source()
    try:
        data = await osm_source.fetch_amenity_counts(suburb_name, "cafe")
        if "error" in data and data.get("count_500m", 0) == 0:
            # Pass through upstream errors but still return zeros where applicable
            pass

        count_500m = int(data.get("count_500m", 0))
        if count_500m >= 30:
            indicator = "HIGH"
        elif count_500m >= 15:
            indicator = "MODERATE"
        else:
            indicator = "LOW"

        return {
            "suburb": suburb_name,
            "amenity": "cafe",
            "counts": {
                "within_500m": count_500m,
                "within_1km": int(data.get("count_1km", 0)),
                "within_2km": int(data.get("count_2km", 0)),
            },
            "density_indicator": indicator,
            "data_source": "OpenStreetMap Overpass API",
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("OSM cafe-density failed for %s", suburb_name)
        raise HTTPException(status_code=503, detail="Temporary service unavailable.") from e


@router.get("/{suburb_name}/osm-amenity-overview")
async def get_osm_amenity_overview(suburb_name: str) -> Dict[str, Any]:
    """Comprehensive amenity overview across all priority amenity types."""
    osm_source = _osm_source()
    try:
        data = await osm_source.fetch_all_amenity_types(suburb_name)
        if data.get("error"):
            raise HTTPException(
                status_code=502, detail=f"Overpass API error: {data['error']}"
            )

        max_expected = {
            "cafe": 50, "grocery": 15, "supermarket": 8, "pharmacy": 6,
            "hospital": 2, "gym": 8, "park": 15, "bank": 6,
            "swimming_pool": 4, "restaurant": 30, "bar": 20, "clinic": 4,
        }

        amenities_breakdown = []
        total_score = 0.0
        amenities = data.get("amenities", {})

        for amenity_type, counts in amenities.items():
            weight = osm_source.AMENITY_WEIGHTS.get(amenity_type, 5.0)
            cap = max_expected.get(amenity_type, 20)
            normalized = min(counts.get("count_500m", 0) / cap, 1.0) if cap else 0.0
            contribution = weight * normalized
            total_score += contribution
            amenities_breakdown.append(
                {
                    "type": amenity_type,
                    "count_500m": counts.get("count_500m", 0),
                    "score_contribution": round(contribution, 2),
                }
            )

        overall = (min(total_score, 25) / 25) * 10

        return {
            "suburb": suburb_name,
            "overall_amenity_score": round(overall, 2),
            "amenities": amenities_breakdown[:10],
            "data_source": "OpenStreetMap Overpass API",
            "timestamp": data.get("timestamp"),
            "notes": [
                f"Cafe density: {amenities.get('cafe', {}).get('count_500m', 'N/A')} within 500m",
                "High cafe count = vibrant lifestyle area",
                "Essential amenities (groceries, pharmacies) boost score",
            ],
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("OSM amenity-overview failed for %s", suburb_name)
        raise HTTPException(
            status_code=503,
            detail="Temporary service unavailable. Overpass API may be overloaded.",
        ) from e


@router.get("/{suburb_name}/osm-healthcare")
async def get_osm_healthcare(suburb_name: str) -> Dict[str, Any]:
    """Healthcare-amenity access score for a suburb."""
    osm_source = _osm_source()
    try:
        data = await osm_source.fetch_all_amenity_types(suburb_name)
        amenities = data.get("amenities", {})
        healthcare = {
            "hospitals": amenities.get("hospital", {}),
            "clinics": amenities.get("clinic", {}),
            "pharmacies": amenities.get("pharmacy", {}),
            "doctors": amenities.get("doctors", {}),
        }

        hospital_500m = healthcare["hospitals"].get("count_500m", 0)
        clinic_1km = healthcare["clinics"].get("count_1km", 0)
        pharmacy_500m = healthcare["pharmacies"].get("count_500m", 0)

        raw_score = (hospital_500m * 9.5) + (clinic_1km * 8.0) + (pharmacy_500m * 8.5)
        access_score = min(raw_score / 25.0, 10)

        if access_score >= 7.0:
            rating = "EXCELLENT"
        elif access_score >= 4.5:
            rating = "GOOD"
        else:
            rating = "ADEQUATE"

        return {
            "suburb": suburb_name,
            "healthcare_facilities": healthcare,
            "access_score": round(access_score, 2),
            "nearby_hospitals_500m": hospital_500m,
            "nearby_clinics_1km": clinic_1km,
            "nearby_pharmacies_500m": pharmacy_500m,
            "rating": rating,
            "data_source": "OpenStreetMap Overpass API",
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("OSM healthcare failed for %s", suburb_name)
        raise HTTPException(status_code=503, detail="Temporary service unavailable.") from e


@router.get("/{suburb_name}/osm-lifestyle")
async def get_osm_lifestyle_score(suburb_name: str) -> Dict[str, Any]:
    """Lifestyle-amenity score (cafes, gyms, parks, bars, etc.)."""
    osm_source = _osm_source()
    try:
        data = await osm_source.fetch_all_amenity_types(suburb_name)
        amenities = data.get("amenities", {})

        lifestyle_amenities = (
            "cafe", "restaurant", "bar", "pub", "fast_food",
            "gym", "swimming_pool", "park",
        )

        max_expected = {
            "cafe": 50, "restaurant": 30, "bar": 20, "pub": 15,
            "gym": 8, "swimming_pool": 4, "park": 15, "fast_food": 10,
        }

        amenities_list = []
        total = 0.0
        for amenity_type in lifestyle_amenities:
            if amenity_type not in amenities:
                continue
            counts = amenities[amenity_type]
            weight = osm_source.AMENITY_WEIGHTS.get(amenity_type, 5.0)
            cap = max_expected.get(amenity_type, 20)
            normalized = min(counts.get("count_500m", 0) / cap, 1.0) if cap else 0.0
            contribution = weight * normalized
            total += contribution
            amenities_list.append(
                {
                    "type": amenity_type,
                    "count_500m": counts.get("count_500m", 0),
                    "score_contribution": round(contribution, 2),
                }
            )

        score = (min(total, 20) / 20) * 10

        if score >= 7.5:
            rating = "VIBRANT"
        elif score >= 5.0:
            rating = "LIVEABLE"
        else:
            rating = "STANDARD"

        return {
            "suburb": suburb_name,
            "lifestyle_amenities": amenities_list,
            "overall_lifestyle_score": round(score, 2),
            "cafe_count_500m": amenities.get("cafe", {}).get("count_500m", 0),
            "gym_count_500m": amenities.get("gym", {}).get("count_500m", 0),
            "park_count_500m": amenities.get("park", {}).get("count_500m", 0),
            "data_source": "OpenStreetMap Overpass API",
            "lifestyle_rating": rating,
        }
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("OSM lifestyle failed for %s", suburb_name)
        raise HTTPException(status_code=503, detail="Temporary service unavailable.") from e
