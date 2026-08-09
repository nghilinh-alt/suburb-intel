"""Production entrypoint: serves the API under /api AND the built React SPA
(frontend/dist) from one process. Dev is unchanged (app.main:app + Vite)."""
from __future__ import annotations
import base64, os, secrets
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from app.api import nl_search, rankings, search, suburb
from app.api.osm_routes import router as osm_router

_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
app = FastAPI(title="Suburb Intelligence", version="1.0.0")
_AUTH_USER = os.environ.get("BASIC_AUTH_USER")
_AUTH_PASS = os.environ.get("BASIC_AUTH_PASS")

class _BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if _AUTH_USER and _AUTH_PASS:
            header = request.headers.get("authorization", "")
            ok = False
            if header.startswith("Basic "):
                try:
                    u, _, p = base64.b64decode(header[6:]).decode().partition(":")
                    ok = secrets.compare_digest(u, _AUTH_USER) and secrets.compare_digest(p, _AUTH_PASS)
                except Exception:
                    ok = False
            if not ok:
                return Response("Authentication required", status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="suburb-intel"'})
        return await call_next(request)

app.add_middleware(_BasicAuthMiddleware)
app.include_router(suburb.router, prefix="/api/suburb", tags=["Suburb"])
app.include_router(search.router, prefix="/api/search", tags=["Search"])
app.include_router(rankings.router, prefix="/api/rankings", tags=["Rankings"])
app.include_router(osm_router, prefix="/api/search", tags=["OSM Amenities"])
app.include_router(nl_search.router, prefix="/api/search", tags=["NL Search"])

@app.get("/api/health")
async def health() -> dict:
    return {"status": "healthy"}

if (_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=_DIST / "assets"), name="assets")

@app.get("/{full_path:path}")
async def spa(full_path: str):
    candidate = _DIST / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(_DIST / "index.html")
