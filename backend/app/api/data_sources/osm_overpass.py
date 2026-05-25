"""
OpenStreetMap Overpass API Data Source

Fetches amenity density data (cafes, gyms, childcare, hospitals, shops, etc.)
for suburb-level intelligence using the free Overpass API.

Example query structure:
POST https://overpass-api.de/api/interpreter
Body:
[out:json][timeout:60];
(
  node["amenity"="cafe"](around:1000,"{query_string}");
);
out count;

Returns amenity counts within 500m, 1km, and 2km radii from suburb center.

Author: Suburb Intel MVP Team
Last Updated: 2026-05-25
"""

import requests
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json


class OSMOverpassDataSource:
    """
    Data source for OpenStreetMap amenity density data via Overpass API.
    
    Features:
    - Cafes, gyms, childcare centres, hospitals, shops, pubs/bars
    - Counts within 500m, 1km, and 2km radius from suburb center
    - Amenity type classification (e.g., "coffee_shop", "restaurant")
    
    API Documentation: https://overpass-turbo.de/
    Overpass API Docs: https://overpass-api.de/api/changelog
    """
    
    # Overpass API server
    BASE_URL = "https://overpass-api.de/api/interpreter"
    
    # Supported amenity types mapped to OSM tags
    AMENITY_TAGS = {
        "cafe": "amenity=cafe",
        "restaurant": "amenity=restaurant",
        "fast_food": "amenity=fast_food",
        "bar": "amenity=bar",
        "pub": "amenity=pub",
        "hospital": "amenity=hospital",
        "clinic": "amenity=clinic",
        "doctors": "amenity=doctors",
        "dentist": "amenity=dentist",
        "pharmacy": "amenity=pharmacy",
        "grocery": "shop=supermarket",
        "supermarket": "shop=supermarket",
        "bank": "amenity=bank",
        "school": "amenity=school",
        "kindergarten": "amenity=kindergarten",
        "childcare": "amenity=childcare",
        "library": "amenity=library",
        "post_office": "amenity=post_office",
        "fitness_centre": "leisure=fitness_centre",
        "gym": "leisure=fitness_centre",
        "swimming_pool": "leisure=pool",
        "park": "landuse=recreation_ground",
    }
    
    # Amenity density scoring weights (for lifestyle score calculation)
    AMENITY_WEIGHTS = {
        "cafe": 8.0,
        "restaurant": 7.5,
        "bar": 6.0,
        "pub": 6.0,
        "fast_food": 3.0,
        "grocery": 9.0,
        "supermarket": 9.0,
        "pharmacy": 8.5,
        "bank": 7.0,
        "hospital": 9.5,
        "clinic": 8.0,
        "doctors": 8.0,
        "swimming_pool": 7.0,
        "gym": 6.5,
        "park": 7.5,
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; SuburbIntel/1.0)',
            'Accept-Encoding': 'gzip',
            'Connection': 'keep-alive',
        })
    
    def get_amenity_query_string(self, amenity_type: str) -> str:
        """Construct Overpass query string for amenity type."""
        # Build query with multiple radii in one request
        nodes = f'node["{self.AMENITY_TAGS.get(amenity_type, amenity_type)}"](around:500,"{amenity_type}");'
        ways = f'way["{self.AMENITY_TAGS.get(amenity_type, amenity_type)}"](around:1000,"{amenity_type}");'
        relations = f'relation["{self.AMENITY_TAGS.get(amenity_type, amenity_type)}"](around:2000,"{amenity_type}");'
        return f'[{nodes}{ways}{relations}]; out count;'
    
    async def fetch_amenity_counts(self, suburb_name: str, amenity_type: str) -> Dict[str, Any]:
        """
        Fetch amenity counts for a specific type within 500m, 1km, and 2km.
        
        Args:
            suburb_name: Name of suburb (used as query string in Overpass API)
            amenity_type: Type of amenity to fetch (e.g., "cafe", "grocery")
        
        Returns:
            Dict with count_500m, count_1km, count_2km or error message
        
        Example:
            >>> osm_source = OSMOverpassDataSource()
            >>> result = await osm_source.fetch_amenity_counts("South Yarra", "cafe")
            >>> print(result["count_500m"])  # e.g., 42
        """
        try:
            query_string = self.get_amenity_query_string(amenity_type)
            
            # Encode suburb name for Overpass API URL parameter
            encoded_suburb = urllib.parse.quote(suburb_name)
            
            url = f"{self.BASE_URL}?{query_string}"
            params = {
                'data': f'"[{urllib.parse.quote(suburb_name)}]";',
                'timeout': 60
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            # Parse Overpass output - should be in format like: {"count_500m": "42", "count_1km": "87", ...}
            if isinstance(data, dict):
                counts = {
                    "count_500m": int(data.get("count_500m", 0) or 0),
                    "count_1km": int(data.get("count_1km", 0) or 0), 
                    "count_2km": int(data.get("count_2km", 0) or 0)
                }
                
                return counts
            
            # Fallback: try to parse different Overpass response formats
            if isinstance(data, list):
                # Empty result
                return {
                    "count_500m": 0,
                    "count_1km": 0,
                    "count_2km": 0
                }
            
            # Return raw data with error flag
            return {"error": f"Unexpected response format: {type(data)}"}
            
        except requests.exceptions.RequestException as e:
            print(f"Request error fetching {amenity_type} for {suburb_name}: {e}")
            return {
                "count_500m": 0,
                "count_1km": 0,
                "count_2km": 0,
                "error": str(e)
            }
        except Exception as e:
            print(f"Unexpected error fetching {amenity_type} for {suburb_name}: {e}")
            return {"error": str(e)}


import urllib.parse
