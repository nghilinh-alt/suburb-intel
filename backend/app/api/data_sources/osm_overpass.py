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
  way["amenity"="cafe"](around:1000,"{query_string}");
  relation["amenity"="cafe"](around:1000,"{query_string}");
);
out count;

Returns amenity counts within 500m, 1km, and 2km radii from suburb center.

Author: Suburb Intel MVP Team
Last Updated: 2026-05-25
"""

import requests
from typing import Dict, Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import db
from datetime import datetime


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
        "cafe": "amenity=cafe",  # Coffee shops, cafe-style venues
        "restaurant": "amenity=restaurant",  # Full service restaurants
        "fast_food": "amenity=fast_food",  # Fast food outlets
        "bar": "amenity=bar",  # Pubs, bars
        "pub": "amenity=pub",  # Traditional pubs (if tagged)
        "hospital": "amenity=hospital",  # Hospitals
        "clinic": "amenity=clinic",  # Medical clinics
        "doctors": "amenity=doctors",  # Doctor offices
        "dentist": "amenity=dentist",  # Dental practices
        "pharmacy": "amenity=pharmacy",  # Pharmacies
        "grocery": "shop=supermarket",  # Grocery stores/supermarkets
        "supermarket": "shop=supermarket",
        "convenience_store": "shop=convenience",
        "shopping_centre": "shop=mall",
        "bank": "amenity=bank",  # Banks/ATMs
        "atm": "amenity=atm",
        "school": "amenity=school",  # Schools (requires careful mapping)
        "kindergarten": "amenity=kindergarten",  # Kindergartens
        "childcare": "amenity=childcare",
        "child_mindcare": "amenity=child_mindcare",
        "library": "amenity=library",  # Libraries
        "post_office": "amenity=post_office",
        "bank": "amenity=bank",
        "fitness_centre": "leisure=fitness_centre",  # Gyms/fitness centres
        "gym": "leisure=fitness_centre",
        "swimming_pool": "leisure=pool",  # Swimming pools
        "sports_centre": "leisure=sports_centre",
        "park": "landuse=recreation_ground",  # Parks
        "community_centre": "amenity=community_centre",
    }
    
    # Amenity density scoring weights (for lifestyle score calculation)
    AMENITY_WEIGHTS = {
        "cafe": 8.0,  # High lifestyle indicator
        "restaurant": 7.5,
        "bar": 6.0,
        "pub": 6.0,
        "fast_food": 3.0,
        "grocery": 9.0,  # Essential amenity
        "supermarket": 9.0,
        "pharmacy": 8.5,
        "bank": 7.0,
        "hospital": 9.5,  # Critical healthcare access
        "clinic": 8.0,
        "doctors": 8.0,
        "dental": 6.0,
        "swimming_pool": 7.0,
        "gym": 6.5,
        "park": 7.5,
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.timeout = 30  # seconds
    
    async def fetch_suburb_coordinates(self, suburb_name: str) -> Dict[str, Any]:
        """
        Fetch suburb centrepoint coordinates from Geocoder or OSM search.
        
        Args:
            suburb_name: Suburb name (e.g., "South Yarra")
            
        Returns:
            Dict with latitude, longitude, and confidence score
            
        Raises:
            ValueError: If suburb not found
        """
        # First try simple Geonames lookup for suburb + state
        geonames_url = f"https://geonames.org/find?q={suburb_name}&country=AU"
        
        try:
            response = requests.get(geonames_url, timeout=self.timeout)
            if response.status_code == 200:
                data = response.json()
                results = data.get("results", [])
                
                if len(results) > 0:
                    location = results[0]
                    return {
                        "latitude": location["lat"],
                        "longitude": location["lon"],
                        "display_name": location.get("display_name", ""),
                        "confidence": "high"
                    }
        except Exception as e:
            print(f"Geonames lookup failed for {suburb_name}: {e}")
        
        # Fallback: Return placeholder coordinates (use state capital approximate)
        # This will be improved with better geocoding later
        lat_lon_map = {
            "Melbourne": (-37.8136, 144.9631),
            "Sydney": (-33.8688, 151.2093),
            "Brisbane": (-27.4697, 153.0251),
            "Perth": (-31.9505, 115.8605),
            "Adelaide": (-34.9285, 138.6007),
            "Darwin": (-12.4634, 130.8456),
            "Hobart": (-42.8821, 147.3272),
        }
        
        # Extract state from suburb name (e.g., "South Yarra VIC" -> VIC)
        import re
        match = re.search(r'\b(ME|SYD|BNE|PER|ADL|DRW|HBA)\b', suburb_name.upper())
        
        if not match:
            # Default to Melbourne as fallback
            return {
                "latitude": -37.8136,
                "longitude": 144.9631,
                "display_name": f"{suburb_name} (Default Location)",
                "confidence": "low"
            }
        
        # Use appropriate state capital coordinates
        lat_lon_map[state_code] = None
        
        return {
            "latitude": -37.8136,
            "longitude": 144.9631,
            "display_name": f"{suburb_name} (Approximate Location)",
            "confidence": "low"
        }
    
    def build_overpass_query(self, query_string: str, amenity_tag: str) -> str:
        """
        Build Overpass API query for specific amenity type.
        
        Args:
            query_string: Suburb name (e.g., "South Yarra VIC")
            amenity_tag: OSM amenity tag string (e.g., "amenity=cafe")
            
        Returns:
            Overpass QL query string
        """
        # Escape single quotes in query string
        escaped_suburb = query_string.replace("'", "\\'").replace('\"', '\\"')
        
        # Query structure with configurable radius
        return f"""
[out:json][timeout:60];
(
  // Node amenities (shops, cafes, banks, etc.)
  node["{amenity_tag}"](around:2000,"{escaped_suburb}");
  
  // Way amenities (restaurants, larger venues)
  way["{amenity_tag}"](around:2000,"{escaped_suburb}");
  
  // Relation amenities (shopping centres, malls)
  relation["{amenity_tag}"](around:2000,"{escaped_suburb}");
);
out count;"""
    
    async def fetch_amenity_counts(self, query_string: str, amenity_type: str = "cafe") -> Dict[str, Any]:
        """
        Fetch amenity counts from Overpass API.
        
        Args:
            query_string: Suburb name/area to search
            amenity_type: Amenity type (e.g., "cafe", "gym", "hospital")
            
        Returns:
            Dict with count breakdown by radius
            
        Raises:
            ValueError: If Overpass API returns error
        """
        # Build and execute query
        query = self.build_overpass_query(query_string, self.AMENITY_TAGS.get(amenity_type, amenity_type))
        
        try:
            response = requests.post(self.BASE_URL, data=query, timeout=self.timeout)
            
            if response.status_code != 200:
                raise ValueError(f"Overpass API error: {response.status_code} - {response.text}")
            
            result = response.json()
            
            # Parse Overpass response format
            elements = result.get("elements", [])
            
            return {
                "amenity": amenity_type,
                "count_500m": len([e for e in elements if e.get("@radius", 0) <= 500]),
                "count_1km": len([e for e in elements if e.get("@radius", 0) <= 1000]),
                "count_2km": len([e for e in elements if e.get("@radius", 0) <= 2000]),
                "total_elements": len(elements),
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except requests.RequestException as e:
            print(f"Overpass API request failed for {amenity_type}: {e}")
            return {
                "amenity": amenity_type,
                "count_500m": 0,
                "count_1km": 0,
                "count_2km": 0,
                "total_elements": 0,
                "error": str(e),
                "last_updated": datetime.utcnow().isoformat()
            }
    
    async def fetch_all_amenity_types(self, query_string: str) -> Dict[str, Any]:
        """
        Fetch counts for all supported amenity types.
        
        Args:
            query_string: Suburb name to search
            
        Returns:
            Dict mapping amenity_type to count breakdown
        """
        amenity_counts = {}
        
        # List of amenity types to fetch (prioritize high-value ones first)
        priority_amenities = [
            "cafe", "grocery", "supermarket", "pharmacy", 
            "hospital", "clinic", "bank", "gym", "swimming_pool",
            "park", "bar", "restaurant"
        ]
        
        for amenity in priority_amenities:
            try:
                counts = await self.fetch_amenity_counts(query_string, amenity)
                amenity_counts[amenity] = counts
            except Exception as e:
                print(f"Error fetching {amenity}: {e}")
                continue
        
        return {
            "query": query_string,
            "amenities": amenity_counts,
            "timestamp": datetime.utcnow().isoformat()
        }
    
    async def calculate_amenity_density_score(self, suburb: str) -> float:
        """
        Calculate overall amenity density score for a suburb (0-10 scale).
        
        Args:
            suburb: Suburb name
            
        Returns:
            Float score between 0 and 10
        """
        # Fetch all amenity types
        data = await self.fetch_all_amenity_types(suburb)
        
        amenities = data.get("amenities", {})
        total_score = 0.0
        
        # Weighted scoring based on amenity type importance and density
        for amenity_type, counts in amenities.items():
            # Get weight for this amenity type (or use default of 5)
            weight = self.AMENITY_WEIGHTS.get(amenity_type, 5.0)
            
            # Normalize count to 0-1 scale (based on typical suburb values)
            max_expected = {
                "cafe": 50, "grocery": 15, "supermarket": 8, "pharmacy": 6,
                "hospital": 2, "gym": 8, "park": 15, "bank": 6,
                "swimming_pool": 4, "restaurant": 30, "bar": 20, "clinic": 4
            }.get(amenity_type, 20)
            
            normalized_count = min(counts["count_500m"] / max_expected, 1.0)
            total_score += weight * normalized_count
        
        # Normalize to 0-10 scale
        raw_score = min(total_score, 25)  # Cap at reasonable max
        final_score = (raw_score / 25) * 10
        
        return round(final_score, 2)
    
    async def store_amenity_data(self, db_session: AsyncSession, 
                                 suburb_id: str, 
                                 data: Dict[str, Any]):
        """
        Store amenity counts in database.
        
        Args:
            db_session: SQLAlchemy async session
            suburb_id: Suburb ID (or name)
            data: Amenity count data from Overpass API
        """
        # Query for existing record or create new
        amenities_record = await db.query(AmenityData).filter(
            AmenityData.suburb == suburb_id
        ).first()
        
        if not amenities_record:
            amenities_record = AmenityData(suburb=suburb_id)
            
            db.add(amenities_record)
            data["suburb_id"] = suburb_id
            
            # Store all amenity counts as a JSON field for flexibility
            amenities_json = json.dumps(data.get("amenities", {}))
            amenities_record.amenities_json = amenities_json
        
        # Update last_updated timestamp
        amenities_record.last_updated = datetime.utcnow()
        
        db.commit()


async def run_amenity_fetcher():
    """Background task to periodically fetch amenity data for all suburbs."""
    from backend.models.database import ammenty_data
    
    osm_source = OSMOverpassDataSource()
    
    # Example: Fetch for a specific suburb
    suburb_name = "South Yarra VIC"  # or any suburb with state code
    
    print(f"Fetching amenity data for {suburb_name}...")
    data = await osm_source.fetch_all_amenity_types(suburb_name)
    print(json.dumps(data, indent=2))
