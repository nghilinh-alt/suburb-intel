"""Production application entrypoint.

Wraps the dev FastAPI app with:
  - /api/* → all API routes (mirrors the Vite dev-server /api proxy rewrite)
  - /assets/* → built React static assets (hashed JS/CSS/images, long-cache)
  - /* → React SPA index.html (client-side routing catch-all)

Run from the repo root with:
  cd backend && uvicorn app.main_prod:prod_app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.main import app as api_app

# Path to the Vite build output (frontend/dist), resolved relative to this file
_ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
_INDEX = os.path.join(_ROOT, "index.html")
_ASSETS = os.path.join(_ROOT, "assets")

prod_app = FastAPI(
    title="Suburb Intel",
    # Hide interactive docs in production
    docs_url=None,
    redoc_url=None,
)

# 1. API routes — mounted at /api to mirror the Vite dev proxy's rewrite rule:
#    frontend calls /api/search/filter → backend receives /search/filter
prod_app.mount("/api", api_app)

# 2. Hashed static assets from the Vite build (safe to serve with long cache).
if os.path.isdir(_ASSETS):
    prod_app.mount("/assets", StaticFiles(directory=_ASSETS), name="assets")


# 3. SPA catch-all — every non-/api path serves index.html so React Router
#    can handle client-side navigation (/suburb/47002, /rankings, etc.).
@prod_app.get("/{full_path:path}")
async def spa_fallback(full_path: str) -> FileResponse:
    return FileResponse(_INDEX)
