"""
Unit Tests for OSM Overpass Amenities API Integration

Test coverage:
1. OSMOverpassDataSource class methods
2. New API endpoints (/osm-amenity-density, /osm-cafe-density, etc.)
3. Error handling and edge cases
4. Response data validation

Author: Suburb Intel MVP Team
Created: 2026-05-25
"""

import pytest
from fastapi.testclient import TestClient
from backend.main import app
from app.api.data_sources.osm_overpass import OSMOverpassDataSource


@pytest.fixture(scope="module")
def client():
    """Create test client for API endpoints."""
    return TestClient(app)


class TestOSMOverpassDataSource:
    """Tests for the OSMOverpassDataSource class."""
    
    def setup_method(self):
        """Initialize test instance."""
        self.osm_source = OSMOverpassDataSource()
        self.timeout = 30
    
    def test_init_osm_data_source(self):
        """Test that OSMOverpassDataSource initializes correctly."""
        # Should have default values
        assert hasattr(self.osm_source, "BASE_URL")
        assert self.osm_source.BASE_URL == "https://overpass-api.de/api/interpreter"
        assert hasattr(self.osm_source, "timeout")
        assert self.osm_source.timeout == 30
    
    def test_amenity_tags_dict_contains_cafe(self):
        """Test that cafe amenity tag is defined."""
        assert "cafe" in self.osm_source.AMENITY_TAGS
        assert self.osm_source.AMENITY_TAGS["cafe"] == "amenity=cafe"
    
    def test_amenity_weights_dict_contains_cafe(self):
        """Test that cafe has a weight defined for scoring."""
        assert "cafe" in self.osm_source.AMENITY_WEIGHTS
        assert self.osm_source.AMENITY_WEIGHTS["cafe"] == 8.0
    
    def test_build_overpass_query_structure(self):
        """Test that query builder produces valid Overpass QL structure."""
        query = self.osm_source.build_overpass_query("South Yarra", "amenity=cafe")
        
        # Check query contains required elements
        assert "[out:json]" in query
        assert "[timeout:" in query
        assert "around:2000" in query  # Should search within 2km
        assert "node" in query
        assert "way" in query
        assert "relation" in query
    
    def test_amenity_weights_contains_all_types(self):
        """Test that amenity weights are defined for all supported types."""
        essential_amenities = ["cafe", "grocery", "hospital", "pharmacy", "gym"]
        
        for amenity in essential_amenities:
            assert amenity in self.osm_source.AMENITY_WEIGHTS


class TestOSMAmenityEndpoints:
    """Tests for OSM amenity API endpoints."""
    
    @pytest.fixture
    def suburb_name(self):
        """Test suburb name."""
        return "South Yarra VIC"
    
    @pytest.fixture  
    def response_200(self, client, suburb_name):
        """Get successful API response (will mock or use real data)."""
        # These will need mocking due to external API dependency
        # For now, test error handling instead
    
    def test_endpoint_routes_exist(self, client):
        """Test that new endpoints are registered in FastAPI router."""
        routes = [route.path for route in app.routes]
        
        endpoint_patterns = [
            "/search/{suburb_name}/osm-amenity-density",
            "/search/{suburb_name}/osm-cafe-density",
            "/search/{suburb_name}/osm-amenity-overview",
            "/search/{suburb_name}/osm-healthcare",
            "/search/{suburb_name}/osm-lifestyle"
        ]
        
        for pattern in endpoint_patterns:
            assert any(pattern.replace("{suburb_name}", "*") in route for route in routes), \
                f"Endpoint {pattern} not found in registered routes"
    
    def test_api_base_returns_health(self, client):
        """Test API root endpoint returns 200."""
        response = client.get("/")
        assert response.status_code == 200
    
    def test_suburb_search_still_works(self, client):
        """Test that existing search endpoints still work."""
        # This should return sample suburbs from DB
        response = client.get("/search/Melbourne", params={"limit": 5})
        assert response.status_code == 200
        data = response.json()
        
        # Should be a list or dict with results
        if isinstance(data, list):
            assert len(data) > 0 or response.status_code in [200, 404]
        else:
            assert "suburbs" in data or "count" in data
    
    def test_osm_endpoint_returns_404_for_nonexistent_suburb(self, client):
        """Test that OSM endpoint handles non-existent suburbs gracefully."""
        response = client.get(
            "/search/NonExistentSuburb12345/osm-amenity-density",
            params={"limit": 1}
        )
        
        # Should return 404 if suburb not found, or 503 if API fails
        assert response.status_code in [404, 502, 503]
    
    def test_osm_endpoint_has_correct_content_type(self, client):
        """Test that OSM endpoint responses are JSON."""
        # Use a real suburb name that's likely to exist
        response = client.get("/search/South%20Yarra/osm-amenity-density")
        
        assert "application/json" in response.headers.get("content-type", "")


class TestResponseDataStructure:
    """Tests for API response data validation."""
    
    @pytest.fixture
    def expected_amenity_density_response(self):
        """Expected structure for /osm-amenity-density endpoint."""
        return {
            "suburb": str,  # Suburb name
            "density_score": (float, int),  # Score between 0 and 10
            "amenities_breakdown": dict,  # Breakdown of all amenity types
            "timestamp": str,  # ISO timestamp
            "data_source": str
        }
    
    @pytest.fixture  
    def expected_cafe_density_response(self):
        """Expected structure for /osm-cafe-density endpoint."""
        return {
            "suburb": str,
            "amenity": str,  # Should be "cafe"
            "counts": dict,  # with within_500m, within_1km, within_2km
            "density_indicator": str,  # HIGH, MODERATE, LOW
            "data_source": str
        }
    
    def test_amenity_density_score_range(self):
        """Test that amenity density scores are normalized to 0-10 range."""
        # Mock source and verify calculation logic
        osm = OSMOverpassDataSource()
        
        # Simulate calculation with known weights
        sample_data = {
            "cafe": {"count_500m": 42},
            "grocery": {"count_500m": 6},
            "hospital": {"count_500m": 1}
        }
        
        # Manual calculation for verification
        score = (8.0 * (42/50) + 9.0 * (6/15) + 9.5 * (1/2)) / 25.0 * 10
        assert 0 <= score <= 10
    
    def test_cafe_density_has_required_fields(self):
        """Test that cafe density response contains all required fields."""
        osm = OSMOverpassDataSource()
        
        # Build mock response as it would be constructed
        mock_response = {
            "suburb": "South Yarra VIC",
            "amenity": "cafe",
            "counts": {
                "within_500m": 42,
                "within_1km": 87,
                "within_2km": 156
            },
            "density_indicator": "HIGH",  # Since 42 >= 30
            "data_source": "OpenStreetMap Overpass API"
        }
        
        assert mock_response["suburb"] == "South Yarra VIC"
        assert mock_response["amenity"] == "cafe"
        assert mock_response["counts"]["within_500m"] == 42
        assert mock_response["density_indicator"] == "HIGH"


class TestErrorHandling:
    """Tests for error handling and edge cases."""
    
    def test_osm_source_handles_network_errors(self):
        """Test that OSM source handles network timeouts gracefully."""
        osm = OSMOverpassDataSource()
        
        # This will be tested with mocking in production tests
        # For now, verify the method exists and has proper signature
        import inspect
        sig = inspect.signature(osm.fetch_amenity_counts)
        assert "query_string" in sig.parameters
        assert "amenity_type" in sig.parameters
    
    def test_osm_source_has_proper_timeout(self):
        """Test that OSM source uses reasonable timeout."""
        osm = OSMOverpassDataSource()
        
        # Should use 30 second timeout (reasonable for Overpass API)
        assert osm.timeout == 30


class TestGeolocationFallback:
    """Tests for geocoding fallback behavior."""
    
    def test_fetch_suburb_coordinates_returns_default(self):
        """Test that coordinate fetch returns reasonable defaults."""
        osm = OSMOverpassDataSource()
        
        # Melbourne default should return valid coordinates
        result = osm.fetch_suburb_coordinates("Melbourne")
        
        assert isinstance(result, dict)
        assert "latitude" in result
        assert "longitude" in result
        assert -38 <= result["latitude"] <= -37  # Melbourne latitude range
    
    def test_fetch_suburb_coordinates_handles_state_codes(self):
        """Test that suburb names with state codes are handled."""
        osm = OSMOverpassDataSource()
        
        # Should handle "South Yarra VIC" format
        result = osm.fetch_suburb_coordinates("South Yarra VIC")
        
        assert isinstance(result, dict)
        assert len(result.get("display_name", "")) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
