"""Map data endpoints.

Two endpoints:
  GET /map/centroids          — lightweight: all 2,454 SA2 centroids with scores
                                (~100KB JSON, used for national overview map)
  GET /map/geojson?state=NSW  — heavy: polygon GeoJSON for one state, choropleth
                                (~2-3MB per state, loaded on demand)
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SA2Region, SuburbScore
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Centroid helpers (computed once per worker, cached in memory)
# ---------------------------------------------------------------------------

def _centroid_of_geojson(geojson_str: str) -> tuple[float, float] | None:
    """Return (lon, lat) centroid of a GeoJSON polygon/multipolygon."""
    try:
        geom = json.loads(geojson_str)
        gtype = geom.get("type", "")
        coords: list = geom.get("coordinates", [])

        all_lons: list[float] = []
        all_lats: list[float] = []

        def _collect(rings: list) -> None:
            for ring in rings:
                if ring and isinstance(ring[0], (int, float)):
                    # It's a coordinate pair directly — skip
                    return
                for pt in ring:
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        all_lons.append(float(pt[0]))
                        all_lats.append(float(pt[1]))

        if gtype == "Polygon":
            _collect(coords)
        elif gtype == "MultiPolygon":
            for poly in coords:
                _collect(poly)

        if all_lons:
            return sum(all_lons) / len(all_lons), sum(all_lats) / len(all_lats)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/centroids")
async def map_centroids(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return all SA2 centroids with investment scores as GeoJSON FeatureCollection.

    Lightweight (~100KB) — suitable for loading all 2,454 SA2s at once for
    the national overview dot-map.
    """
    stmt = (
        select(
            SA2Region.sa2_code,
            SA2Region.sa2_name,
            SA2Region.state,
            SA2Region.geometry_geojson,
            SuburbScore.investment_score,
            SuburbScore.liveability_score,
            SuburbScore.growth_score,
        )
        .outerjoin(SuburbScore, SuburbScore.sa2_code == SA2Region.sa2_code)
        .where(SA2Region.geometry_geojson.isnot(None))
    )
    rows = (await db.execute(stmt)).all()

    features = []
    for sa2_code, sa2_name, state, geojson_str, inv, liv, grw in rows:
        centroid = _centroid_of_geojson(geojson_str)
        if centroid is None:
            continue
        lon, lat = centroid
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "sa2_code":        sa2_code,
                "sa2_name":        sa2_name,
                "state":           state,
                "investment_score": round(inv, 2) if inv is not None else None,
                "liveability_score": round(liv, 2) if liv is not None else None,
                "growth_score":     round(grw, 2) if grw is not None else None,
            },
        })

    return {"type": "FeatureCollection", "features": features}


@router.get("/geojson")
async def map_geojson(
    state: str = Query(..., description="State code, e.g. NSW"),
    score_type: str = Query("investment_score", description="Score column to use for choropleth colour"),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return polygon GeoJSON FeatureCollection for a single state.

    Used for choropleth rendering when user zooms into a state.
    ~2-3MB per large state (NSW/VIC/QLD), <1MB for smaller states.
    """
    _valid = {
        "investment_score", "liveability_score", "education_score",
        "growth_score", "demographic_score", "housing_score",
        "infrastructure_score", "gentrification_index",
    }
    if score_type not in _valid:
        raise HTTPException(status_code=400, detail=f"score_type must be one of {sorted(_valid)}")

    stmt = (
        select(
            SA2Region.sa2_code,
            SA2Region.sa2_name,
            SA2Region.geometry_geojson,
            SuburbScore,
        )
        .outerjoin(SuburbScore, SuburbScore.sa2_code == SA2Region.sa2_code)
        .where(SA2Region.state == state.upper())
        .where(SA2Region.geometry_geojson.isnot(None))
    )
    rows = (await db.execute(stmt)).all()

    if not rows:
        raise HTTPException(status_code=404, detail=f"No SA2s found for state '{state}'")

    features = []
    for sa2_code, sa2_name, geojson_str, scores in rows:
        try:
            geom = json.loads(geojson_str)
        except Exception:
            continue

        score_val = getattr(scores, score_type, None) if scores else None
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "sa2_code":  sa2_code,
                "sa2_name":  sa2_name,
                "score":     round(score_val, 2) if score_val is not None else None,
                "score_type": score_type,
                "investment_score":    round(scores.investment_score, 2) if scores and scores.investment_score else None,
                "liveability_score":   round(scores.liveability_score, 2) if scores and scores.liveability_score else None,
                "growth_score":        round(scores.growth_score, 2) if scores and scores.growth_score else None,
                "education_score":     round(scores.education_score, 2) if scores and scores.education_score else None,
                "risk_flags":          scores.risk_flags if scores else [],
            },
        })

    return {"type": "FeatureCollection", "features": features, "state": state.upper()}
