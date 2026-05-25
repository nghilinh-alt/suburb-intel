"""Geographic Mapping Utilities for SA2 Regions
    
This module handles geographic operations:
- SA2 code to lat/lon mapping
- Project proximity calculations
- Geographic filtering
- Region boundary handling
    
Usage:
    from app.ingestion.geo_mapper import (
        get_sa2_coords,
        find_projects_nearby,
        map_project_to_sa2s
    )
    
"""

import math
from typing import List, Dict, Optional, Tuple


# Pre-populated SA2 coordinate mappings (expand with full geocoder in production)
SA2_COORDS = {
    "30150": (-37.8644, 144.9056),      # Altona Gardens VIC
    "34005": (-27.6394, 153.1444),       # Ashtabula QLD
    "48210": (-27.4700, 153.0300),       # Brisbane Waters QLD
    "47002": (-27.4850, 153.0600),       # Chermside QLD
    "22625": (-33.9200, 151.1800),       # Cronulla Sydney NSW
}


def get_sa2_coords(sa2_code: str) -> Optional[Tuple[float, float]]:
    """Get lat/lon coordinates for an SA2 code
    
    Args:
        sa2_code: SA2 identifier (e.g., "47002")
    
    Returns:
        Tuple of (latitude, longitude) or None if not found
    """
    return SA2_COORDS.get(sa2_code)


def get_suburb_name_from_coords(lat: float, lon: float) -> Optional[str]:
    """Reverse lookup: approximate suburb name from coordinates
    
    Args:
        lat: Latitude
        lon: Longitude
    
    Returns:
        Approximate suburb name or None
    """
    for sa2_code, coords in SA2_COORDS.items():
        if math.isclose(coords[0], lat, abs_tol=0.05) and \
           math.isclose(coords[1], lon, abs_tol=0.05):
            # Return first matching SA2 name from seeded data
            return "Unknown"  # Would return actual name in production
    
    return None


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in kilometers
    
    Args:
        lat1, lon1: First point coordinates
        lat2, lon2: Second point coordinates
    
    Returns:
        Distance in kilometers
    """
    R = 6371.0  # Earth's radius in km
    lat1, lon1, lat2, lon2 = map(math.radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    
    return R * c


def find_projects_nearby(
    sa2_code: str,
    max_distance_km: float = 15.0
) -> List[Dict]:
    """Find infrastructure projects within radius of an SA2 region
    
    Args:
        sa2_code: SA2 identifier
        max_distance_km: Maximum distance (default 15km for typical suburb footprint)
    
    Returns:
        List of nearby projects with distances
    """
    from app.db.session import get_db
    from app.db.models import InfrastructureProject
    
    sa2_lat, sa2_lon = get_sa2_coords(sa2_code)
    if not sa2_lat or not sa2_lon:
        return []
    
    async with get_db() as session:
        all_projects = await session.query(InfrastructureProject).all()
    
    nearby = []
    
    for project in all_projects:
        proj_lat, proj_lon = project.lat, project.lon
        
        if not proj_lat or not proj_lon:
            continue
        
        distance = haversine_distance(sa2_lat, sa2_lon, proj_lat, proj_lon)
        
        if distance <= max_distance_km:
            project_dict = project.__dict__.copy()
            project_dict["distance_km"] = round(distance, 1)
            nearby.append(project_dict)
    
    # Sort by distance
    nearby.sort(key=lambda x: x["distance_km"])
    
    return nearby


def calculate_impact_score(
    project_value_aud: int,
    project_type: str,
    project_stage: str,
    proximity_factor: float
) -> float:
    """Calculate weighted impact score for an infrastructure project
    
    Args:
        project_value_aud: Project value in AUD
        project_type: One of transport, health, education, civic, etc.
        project_stage: under_construction, approved, planned, completed
        proximity_factor: 0-1 based on distance from SA2 center (closer = higher impact)
    
    Returns:
        Impact score between 0 and 100
    """
    # Type weightings (from gov_score.py)
    type_weights = {
        "transport": 1.0,
        "health": 0.9,
        "education": 0.7,
        "civic": 0.4
    }
    
    stage_weights = {
        "under_construction": 1.0,
        "approved": 0.7,
        "planned": 0.4,
        "completed": 0.2,
        "cancelled": 0.0
    }
    
    type_weight = type_weights.get(project_type.lower(), 0.5)
    stage_weight = stage_weights.get(project_stage.lower(), 0.3)
    
    # Normalize project value (million AUD base)
    normalized_value = min(project_value_aud / 1_000_000, 200)
    
    # Apply proximity factor (closer projects have higher impact)
    scaled_value = normalized_value * proximity_factor
    
    raw_score = scaled_value * type_weight * stage_weight
    
    # Normalize to 0-100 scale
    impact_score = min(raw_score / 1_000_000 * 100, 100)
    
    return round(impact_score, 2)


def map_project_to_sa2s(
    project_id: str,
    max_distance_km: float = 20.0
) -> List[Dict]:
    """Map an infrastructure project to all impacted SA2 regions
    
    Args:
        project_id: Infrastructure project identifier
        max_distance_km: Maximum impact radius
    
    Returns:
        List of {sa2_code, sa2_name, impact_score} dictionaries
    """
    from app.db.session import get_db
    from app.db.models import InfrastructureProject, SA2Region, SA2ProjectLink
    
    async with get_db() as session:
        project = await session.get(InfrastructureProject, project_id)
    
    if not project:
        return []
    
    # Get project coordinates
    proj_lat, proj_lon = project.lat, project.lon
    if not proj_lat or not proj_lon:
        return []
    
    # Find all SA2 regions within impact radius
    async with get_db() as session:
        all_sa2s = await session.query(SA2Region).all()
    
    impacts = []
    
    for sa2 in all_sa2s:
        sa2_lat, sa2_lon = get_sa2_coords(sa2.sa2_code)
        
        if not sa2_lat or not sa2_lon:
            continue
        
        distance = haversine_distance(proj_lat, proj_lon, sa2_lat, sa2_lon)
        proximity_factor = max(0, 1 - (distance / max_distance_km))
        
        # Calculate impact score using helper function
        impact_score = calculate_impact_score(
            project.value_aud or 0,
            project.type,
            project.status,
            proximity_factor
        )
        
        impacts.append({
            "sa2_code": sa2.sa2_code,
            "sa2_name": sa2.sa2_name,
            "state": sa2.state,
            "distance_km": round(distance, 1),
            "impact_score": impact_score
        })
    
    # Sort by impact score (descending)
    impacts.sort(key=lambda x: x["impact_score"], reverse=True)
    
    return impacts[:50]  # Return top 50 SA2s per project


def generate_sa2_boundary_buffer(lat: float, lon: float, buffer_km: float = 3.0) -> Dict:
    """Generate approximate SA2 boundary polygon (for mapping visualization)
    
    Args:
        lat, lon: Center coordinates of SA2
        buffer_km: Distance to extend in each direction
    
    Returns:
        Polygon geometry as GeoJSON-like dict
    """
    # Simplified: generate a circle approximation
    n_points = 36
    points = []
    
    for i in range(n_points):
        angle = (2 * math.pi * i) / n_points
        x = buffer_km * math.cos(angle)
        y = buffer_km * math.sin(angle)
        
        # Convert to lat/lon coordinates (simplified, not geodetically correct)
        lat_delta = (x / 111.0)  # km to degrees latitude
        lon_delta = (y / (111.0 * math.cos(math.radians(lat))))  # km to degrees longitude
        
        points.append({
            "lat": round(lat + lat_delta, 5),
            "lon": round(lon + lon_delta, 5)
        })
    
    return {
        "type": "Polygon",
        "coordinates": [map["lon"] for map in points]  # Simplified
    }
