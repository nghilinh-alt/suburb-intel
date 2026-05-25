from fastapi import APIRouter, Query, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_db
from app.db.models import SA2Region, ABSCEntensMetrics
from app.api.data_sources import OSMOverpassDataSource

router = APIRouter(prefix="/{suburb_name}")


@router.get("/osm-amenity-density")
async def get_osm_amenity_density(suburb_name: str):
    """
    Get amenity density score from OpenStreetMap Overpass API.
    
    Returns:
        Amenity density score (0-10) and detailed breakdown
    
    Example Response:
        {
            "suburb": "South Yarra VIC",
            "density_score": 8.7,
            "amenities_breakdown": {
                "cafe": {"count_500m": 42, "count_1km": 87, "count_2km": 156},
                "grocery": {"count_500m": 6, "count_1km": 12, "count_2km": 18}
            }
        }
    """
    osm_source = OSMOverpassDataSource()
    
    # Fetch all amenity types
    try:
        data = await osm_source.fetch_all_amenity_types(suburb_name)
        
        # Calculate density score
        if not data.get("error"):
            score = await osm_source.calculate_amenity_density_score(suburb_name)
            
            return {
                "suburb": suburb_name,
                "density_score": score,
                "amenities_breakdown": data.get("amenities", {}),
                "timestamp": data.get("timestamp"),
                "data_source": "OpenStreetMap Overpass API"
            }
        else:
            raise HTTPException(
                status_code=502, 
                detail=f"Overpass API error: {data.get('error')}"
            )
            
    except Exception as e:
        print(f"Error fetching OSM data for {suburb_name}: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Temporary service unavailable. Please try again later."
        )


@router.get("/osm-cafe-density")
async def get_osm_cafe_density(suburb_name: str):
    """
    Get cafe density specifically for lifestyle scoring.
    
    Returns:
        Cafe counts within 500m, 1km, and 2km radii
    """
    osm_source = OSMOverpassDataSource()
    
    try:
        data = await osm_source.fetch_amenity_counts(suburb_name, "cafe")
        
        return {
            "suburb": suburb_name,
            "amenity": "cafe",
            "counts": {
                "within_500m": data["count_500m"],
                "within_1km": data["count_1km"],
                "within_2km": data["count_2km"]
            },
            "density_indicator": "HIGH" if data["count_500m"] >= 30 else 
                                 "MODERATE" if data["count_500m"] >= 15 else "LOW",
            "data_source": "OpenStreetMap Overpass API"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching cafe data for {suburb_name}: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Temporary service unavailable."
        )


@router.get("/osm-amenity-overview")
async def get_osm_amenity_overview(suburb_name: str):
    """
    Get comprehensive amenity overview for suburb lifestyle scoring.
    
    Returns breakdown of all major amenity types (cafes, gyms, hospitals, 
    groceries, banks, pharmacies, etc.) with counts at 3 radii.
    
    Example Response:
        {
            "suburb": "South Yarra VIC",
            "overall_amenity_score": 8.5,
            "amenities": [
                {"type": "cafe", "count_500m": 42, "score_contribution": 3.6},
                {"type": "grocery", "count_500m": 6, "score_contribution": 0.6}
            ]
        }
    """
    osm_source = OSMOverpassDataSource()
    
    try:
        # Fetch all priority amenities
        data = await osm_source.fetch_all_amenity_types(suburb_name)
        
        amenities_breakdown = []
        total_score = 0.0
        
        for amenity_type, counts in data.get("amenities", {}).items():
            # Get weight for this amenity type
            weight = osm_source.AMENITY_WEIGHTS.get(
                amenity_type, 
                5.0  # default weight
            )
            
            # Calculate score contribution (normalized count * weight)
            max_expected = {
                "cafe": 50, "grocery": 15, "supermarket": 8, "pharmacy": 6,
                "hospital": 2, "gym": 8, "park": 15, "bank": 6,
                "swimming_pool": 4, "restaurant": 30, "bar": 20, "clinic": 4
            }.get(amenity_type, 20)
            
            normalized_count = min(counts["count_500m"] / max_expected, 1.0)
            score_contribution = weight * normalized_count
            total_score += score_contribution
        
        # Normalize to 0-10 scale
        amenity_overall_score = (min(total_score, 25) / 25) * 10
        
        return {
            "suburb": suburb_name,
            "overall_amenity_score": round(amenity_overall_score, 2),
            "amenities": amenities_breakdown[:10],  # Top 10 amenity types
            "data_source": "OpenStreetMap Overpass API",
            "timestamp": data.get("timestamp"),
            "notes": [
                f"Cafe density: {counts['cafe']['count_500m'] if counts else 'N/A'} within 500m",
                "High cafe count = vibrant lifestyle area",
                "Essential amenities (groceries, pharmacies) boost score"
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching amenity overview for {suburb_name}: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Temporary service unavailable. Overpass API may be overloaded."
        )


@router.get("/osm-healthcare")
async def get_osm_healthcare(suburb_name: str):
    """
    Get healthcare amenities (hospitals, clinics, pharmacies) from OSM.
    
    Healthcare access is critical for suburb livability scoring.
    """
    osm_source = OSMOverpassDataSource()
    
    try:
        # Fetch all relevant healthcare amenities
        data = await osm_source.fetch_all_amenity_types(suburb_name)
        
        healthcare = {
            "hospitals": data.get("amenities", {}).get("hospital", {}),
            "clinics": data.get("amenities", {}).get("clinic", {}),
            "pharmacies": data.get("amenities", {}).get("pharmacy", {}),
            "doctors": data.get("amenities", {}).get("doctors", {})
        }
        
        # Calculate healthcare access score
        hospital_500m = healthcare["hospitals"].get("count_500m", 0)
        clinic_1km = healthcare["clinics"].get("count_1km", 0)
        pharmacy_500m = healthcare["pharmacies"].get("count_500m", 0)
        
        healthcare_access_score = (
            (hospital_500m * 9.5) + 
            (clinic_1km * 8.0) + 
            (pharmacy_500m * 8.5)
        ) / 25.0  # Normalize
        
        return {
            "suburb": suburb_name,
            "healthcare_facilities": healthcare,
            "access_score": round(min(healthcare_access_score, 10), 2),
            "nearby_hospitals_500m": hospital_500m,
            "nearby_clinics_1km": clinic_1km,
            "nearby_pharmacies_500m": pharmacy_500m,
            "rating": "EXCELLENT" if healthcare_access_score >= 7.0 else
                      "GOOD" if healthcare_access_score >= 4.5 else
                      "ADEQUATE",
            "data_source": "OpenStreetMap Overpass API"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching healthcare data for {suburb_name}: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Temporary service unavailable."
        )


@router.get("/osm-lifestyle")
async def get_osm_lifestyle_score(suburb_name: str):
    """
    Get lifestyle amenity score (non-essential amenities for lifestyle scoring).
    
    Includes: cafes, gyms, restaurants, parks, swimming pools, bars
    
    This is distinct from essential amenities (groceries, pharmacies, hospitals).
    """
    osm_source = OSMOverpassDataSource()
    
    try:
        # Fetch all amenities
        data = await osm_source.fetch_all_amenity_types(suburb_name)
        
        lifestyle_amenities = [
            "cafe", "restaurant", "bar", "pub", "fast_food",
            "gym", "swimming_pool", "park"
        ]
        
        amenities_list = []
        total_lifestyle_score = 0.0
        
        for amenity_type in lifestyle_amenities:
            if amenity_type in data.get("amenities", {}):
                counts = data["amenities"][amenity_type]
                weight = osm_source.AMENITY_WEIGHTS.get(amenity_type, 5.0)
                
                # Calculate score contribution
                max_expected = {
                    "cafe": 50, "restaurant": 30, "bar": 20, "pub": 15,
                    "gym": 8, "swimming_pool": 4, "park": 15, "fast_food": 10
                }.get(amenity_type, 20)
                
                normalized_count = min(counts["count_500m"] / max_expected, 1.0)
                score_contribution = weight * normalized_count
                total_lifestyle_score += score_contribution
                
                amenities_list.append({
                    "type": amenity_type,
                    "count_500m": counts["count_500m"],
                    "score_contribution": round(score_contribution, 2)
                })
        
        # Normalize to 0-10 scale
        lifestyle_score = (min(total_lifestyle_score, 20) / 20) * 10
        
        return {
            "suburb": suburb_name,
            "lifestyle_amenities": amenities_list,
            "overall_lifestyle_score": round(lifestyle_score, 2),
            "cafe_count_500m": data.get("amenities", {}).get("cafe", {}).get("count_500m", 0),
            "gym_count_500m": data.get("amenities", {}).get("gym", {}).get("count_500m", 0),
            "park_count_500m": data.get("amenities", {}).get("park", {}).get("count_500m", 0),
            "data_source": "OpenStreetMap Overpass API",
            "lifestyle_rating": "VIBRANT" if lifestyle_score >= 7.5 else
                               "LIVEABLE" if lifestyle_score >= 5.0 else
                               "STANDARD"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching lifestyle data for {suburb_name}: {e}")
        raise HTTPException(
            status_code=503, 
            detail="Temporary service unavailable."
        )
