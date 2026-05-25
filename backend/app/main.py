"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI

from app.api import rankings, search, suburb
from app.api.osm_routes import router as osm_router

app = FastAPI(
    title="Suburb Intelligence API",
    description="Australia's government-data driven property investment decision engine",
    version="1.0.0",
)


@app.get("/")
async def root() -> dict:
    return {
        "service": "Suburb Intelligence API",
        "version": "1.0.0",
        "endpoints": [
            {"method": "GET", "path": "/suburb/{sa2_code}", "description": "Get suburb investment report"},
            {"method": "GET", "path": "/search", "description": "Search suburbs by name or SA2 code"},
            {"method": "GET", "path": "/rankings", "description": "Get top-ranked suburbs"},
            {"method": "GET", "path": "/search/{suburb_name}/osm-amenity-density", "description": "OSM amenity density"},
        ],
    }


@app.get("/health")
async def health_check() -> dict:
    return {"status": "healthy"}


# Routers
app.include_router(suburb.router, prefix="/suburb", tags=["Suburb"])
app.include_router(search.router, prefix="/search", tags=["Search"])
app.include_router(rankings.router, prefix="/rankings", tags=["Rankings"])
# OSM routes already declare `{suburb_name}` in each path, mount them under /search.
app.include_router(osm_router, prefix="/search", tags=["OSM Amenities"])


# NOTE: RateLimitingMiddleware from `backend/middleware/rate_limiter.py` was previously
# installed here with `app.middleware("http")(RateLimitingMiddleware)`, which is not a
# valid install pattern (that decorator expects a function, not a class) and the
# middleware's own __call__ short-circuited every request with a mock JSON body.
# It is intentionally NOT registered here. To enable rate limiting, rewrite the
# middleware to a proper ASGI/Starlette BaseHTTPMiddleware that calls `await call_next(request)`,
# then re-introduce via `app.add_middleware(RateLimitingMiddleware)`.
