from fastapi import FastAPI

from app.api import suburb, search, rankings
from app.api.osm_routes import osm  # NEW: OpenStreetMap amenity routes
from middleware.rate_limiter import RateLimitingMiddleware  # Add rate limiting support

app = FastAPI(
    title="Suburb Intelligence API",
    description="Australia's government-data driven property investment decision engine",
    version="1.0.0"
)

# Apply rate limiting middleware for all API requests (production ready)
app.middleware("http")(RateLimitingMiddleware)


@app.get("/")
async def root():
    return {
        "service": "Suburb Intelligence API",
        "version": "1.0.0",
        "endpoints": [
            {"method": "GET", "path": "/suburb/{sa2_code}", "description": "Get suburb investment report"},
            {"method": "GET", "path": "/search", "description": "Search suburbs by name or SA2 code"},
            {"method": "GET", "path": "/rankings", "description": "Get top-ranked suburbs"}
        ]
    }


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# Include routers with prefix
app.include_router(suburb.router, prefix="/suburb", tags=["Suburb"])
app.include_router(search.router, prefix="/search", tags=["Search"])
app.include_router(rankings.router, prefix="/rankings", tags=["Rankings"])
app.include_router(osm.router, prefix="/search/{suburb_name}", tags=["OSM Amenities"])  # NEW: OSM amenity routes
