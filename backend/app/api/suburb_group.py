"""Suburb-group endpoint — aggregated view of a real suburb
that may span multiple SA2 statistical areas.

GET /suburb-group/{suburb_id}   e.g. /suburb-group/keysborough-vic
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import os
from sqlalchemy import func, text
from app.db.models import ABSCEntensMetrics, SuburbAggregate, SuburbScore, SA2Region, School, SA2SchoolLink, HealthFacility, SA2HealthLink
from app.db.session import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{suburb_id}")
async def suburb_group_report(
    suburb_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return population-weighted aggregate report for a suburb,
    including per-SA2 score breakdown and dimension-level input facts."""

    agg = await db.get(SuburbAggregate, suburb_id)
    if agg is None:
        raise HTTPException(
            status_code=404,
            detail=f"Suburb '{suburb_id}' not found. Use /search to find valid suburb slugs.",
        )

    # Fetch suburb_scores + census facts for each constituent SA2
    sa2_codes = agg.sa2_codes or []
    stmt = (
        select(SuburbScore, ABSCEntensMetrics, SA2Region.sa2_name)
        .join(ABSCEntensMetrics,
              (ABSCEntensMetrics.sa2_code == SuburbScore.sa2_code) &
              (ABSCEntensMetrics.year == 2021),
              isouter=True)
        .join(SA2Region, SA2Region.sa2_code == SuburbScore.sa2_code, isouter=True)
        .where(SuburbScore.sa2_code.in_(sa2_codes))
    )
    rows = (await db.execute(stmt)).all()

    # Build per-SA2 breakdown
    sa2_breakdown = []
    for scores, census, sa2_name in rows:
        pop = census.population if census else None
        sa2_breakdown.append({
            "sa2_code": scores.sa2_code,
            "sa2_name": sa2_name,
            "population": pop,
            "scores": {
                "investment_score":     _r(scores.investment_score),
                "liveability_score":    _r(scores.liveability_score),
                "education_score":      _r(scores.education_score),
                "growth_score":         _r(scores.growth_score),
                "demographic_score":    _r(scores.demographic_score),
                "housing_score":        _r(scores.housing_score),
                "infrastructure_score": _r(scores.infrastructure_score),
                "gentrification_index": _r(scores.gentrification_index),
            },
            # Intermediates — what drove each dimension score
            "intermediates": {
                "transit_score_raw":     _r(scores.transit_score_raw),
                "edu_avg_icsea":         _r(scores.edu_avg_icsea),
                "edu_top_school_count":  scores.edu_top_school_count,
                "edu_secondary_count":   scores.edu_secondary_count,
                "edu_tertiary_count":    scores.edu_tertiary_count,
                "health_hospital_score": _r(scores.health_hospital_score),
                "health_gp_count":       scores.health_gp_count,
                "infra_committed_aud":   scores.infra_committed_aud,
                "infra_project_count":   scores.infra_project_count,
            },
            # Key census facts for dimension explanations
            "facts": {
                "population":               pop,
                # ABS Business Register counts (more accurate than Overture)
                "biz_food_services":  census.biz_food_services  if census else None,
                "biz_health_social":  census.biz_health_social  if census else None,
                "biz_retail_trade":   census.biz_retail_trade   if census else None,
                "biz_arts_recreation":census.biz_arts_recreation if census else None,
                "biz_other_services": census.biz_other_services  if census else None,
                "biz_total":          census.biz_total           if census else None,
                "median_income":            census.median_income if census else None,
                "median_age":               _r(census.median_age) if census else None,
                "unemployment_pct":         _r(census.unemployment_pct) if census else None,
                "uni_degree_pct":           _r(census.uni_degree_pct) if census else None,
                "professionals_managers_pct": _r(census.professionals_managers_pct) if census else None,
                "separate_house_pct":       _r(census.separate_house_pct) if census else None,
                "flat_apartment_pct":       _r(census.flat_apartment_pct) if census else None,
                "flat_high_rise_pct":       _r(census.flat_high_rise_pct) if census else None,
                "renters_pct":              _r(census.renters_pct) if census else None,
                "high_mortgage_stress_pct": _r(census.high_mortgage_stress_pct) if census else None,
                "high_rent_stress_pct":     _r(census.high_rent_stress_pct) if census else None,
                "social_housing_pct":       _r(census.social_housing_pct) if census else None,
                "pop_growth_proj_pct":      _r(census.pop_growth_proj_pct) if census else None,
                "building_approvals_1yr":   census.building_approvals_1yr if census else None,
                "pt_stop_train":            census.pt_stop_train if census else None,
                "pt_stop_tram":             census.pt_stop_tram if census else None,
                "pt_stop_bus":              census.pt_stop_bus if census else None,
                "pt_stop_ferry":            census.pt_stop_ferry if census else None,
                "osm_cafes":                census.osm_cafes if census else None,
                "osm_restaurants":          census.osm_restaurants if census else None,
                "osm_parks":                census.osm_parks if census else None,
                "osm_gyms":                 census.osm_gyms if census else None,
                "osm_medical_centers":      census.osm_medical_centers if census else None,
                "osm_pharmacies":           census.osm_pharmacies if census else None,
                "osm_hospitals":            census.osm_hospitals if census else None,
                "seifa_irsd_decile":        census.seifa_irsd_decile if census else None,
                "seifa_irsad_decile":       census.seifa_irsad_decile if census else None,
                "seifa_ieo_decile":         census.seifa_ieo_decile if census else None,
            },
            "risk_flags": scores.risk_flags or [],
        })

    # Sort by SA2 name for consistent ordering
    sa2_breakdown.sort(key=lambda x: x["sa2_name"] or "")

    # For single SA2 — surface the full breakdown as top-level intermediates/facts too
    top_intermediates = sa2_breakdown[0]["intermediates"] if len(sa2_breakdown) == 1 else {}
    top_facts_detail  = sa2_breakdown[0]["facts"]         if len(sa2_breakdown) == 1 else {}

    # ── Schools: fetch all linked schools for these SA2 codes ──────────────
    schools_stmt = (
        select(School, SA2SchoolLink.impact_score, SA2SchoolLink.sa2_code)
        .join(SA2SchoolLink, SA2SchoolLink.acara_id == School.acara_id)
        .where(SA2SchoolLink.sa2_code.in_(sa2_codes))
        .where(School.school_type.in_(["Primary", "Secondary", "Combined"]))  # K-12 only
        .order_by(SA2SchoolLink.impact_score.desc(), School.icsea.desc().nulls_last())
    )
    school_rows = (await db.execute(schools_stmt)).all()

    # Deduplicate schools (may appear via multiple SA2 links) — keep highest impact_score
    seen_schools: dict[str, dict] = {}
    for school, impact, _ in school_rows:
        aid = school.acara_id
        if aid not in seen_schools or impact > seen_schools[aid]["impact_score"]:
            # ICSEA percentile label
            pct = school.icsea_percentile
            icsea = school.icsea
            if pct is not None:
                # 5% bands: "Top 5%", "Top 10%", ..., "Bottom 5%"
                for threshold in [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]:
                    if pct >= (100 - threshold):
                        rating = f"Top {threshold}%"
                        break
                else:
                    # Below median — show bottom bands
                    for threshold in [5, 10, 15, 20, 25, 30, 35, 40, 45, 50]:
                        if pct < threshold:
                            rating = f"Bottom {threshold}%"
                            break
                    else:
                        rating = "Middle 50%"
            elif icsea is not None:
                if icsea >= 1130:   rating = "Top 10%"
                elif icsea >= 1100: rating = "Top 20%"
                elif icsea >= 1050: rating = "Top 35%"
                elif icsea >= 1000: rating = "Top 50%"
                elif icsea >= 950:  rating = "Bottom 40%"
                else:               rating = "Bottom 20%"
            else:
                rating = None

            seen_schools[aid] = {
                "name":         school.name,
                "sector":       school.sector,    # Government | Catholic | Independent
                "school_type":  school.school_type,  # Primary | Secondary | Combined
                "icsea":        _r(icsea),
                "icsea_percentile": _r(pct),
                "rating":       rating,
                "impact_score": impact,
                "in_suburb":    impact == 1.0,    # True = in this SA2, False = adjacent
                "total_enrolments": school.total_enrolments,
            }

    schools_in  = sorted([s for s in seen_schools.values() if s["in_suburb"]],  key=lambda x: -(x["icsea"] or 0))
    schools_adj = sorted([s for s in seen_schools.values() if not s["in_suburb"]], key=lambda x: -(x["icsea"] or 0))

    # ── Adjacent train check ───────────────────────────────────────────────
    # Find neighbouring SA2s via schools that are IN our suburb (impact_score=1.0)
    # then look at those schools' 0.5 links → those SA2s border our suburb.
    in_suburb_ids = [aid for aid, s in seen_schools.items() if s["in_suburb"]]
    adj_sa2_stmt = (
        select(SA2SchoolLink.sa2_code)
        .where(SA2SchoolLink.acara_id.in_(in_suburb_ids))
        .where(SA2SchoolLink.impact_score == 0.5)
        .where(SA2SchoolLink.sa2_code.notin_(sa2_codes))
        .distinct()
    )
    adj_sa2_codes = [r[0] for r in (await db.execute(adj_sa2_stmt)).all()]

    adjacent_has_train = False
    if adj_sa2_codes:
        adj_train_stmt = (
            select(ABSCEntensMetrics.sa2_code, SA2Region.sa2_name)
            .join(SA2Region, SA2Region.sa2_code == ABSCEntensMetrics.sa2_code)
            .where(ABSCEntensMetrics.sa2_code.in_(adj_sa2_codes))
            .where(ABSCEntensMetrics.year == 2021)
            .where(ABSCEntensMetrics.pt_stop_train > 0)
        )
        adj_train_rows = (await db.execute(adj_train_stmt)).all()
        adjacent_has_train = len(adj_train_rows) > 0
        adjacent_train_suburbs = [r[1] for r in adj_train_rows]
    else:
        adjacent_train_suburbs = []

    # ── Key nearby facilities (radius-based, not just adjacency) ─────────
    # Get SA2 centroid for distance calculations
    centroid_lat, centroid_lon = await _get_centroid(db, sa2_codes[0])

    unis: list[dict] = []
    hospitals_nearby: list[dict] = []

    if centroid_lat is not None:
        # Universities / TAFE within ~15km (using bounding box pre-filter then haversine)
        DEGREE_15KM = 0.135
        uni_stmt = text("""
            SELECT s.name, s.school_type, s.lat, s.lon
            FROM schools s
            WHERE s.school_type IN ('University','TAFE')
              AND s.lat BETWEEN :lat_min AND :lat_max
              AND s.lon BETWEEN :lon_min AND :lon_max
              AND s.lat IS NOT NULL AND s.lon IS NOT NULL
            ORDER BY s.name
        """)
        uni_rows = (await db.execute(uni_stmt, {
            "lat_min": centroid_lat - DEGREE_15KM, "lat_max": centroid_lat + DEGREE_15KM,
            "lon_min": centroid_lon - DEGREE_15KM, "lon_max": centroid_lon + DEGREE_15KM,
        })).all()
        for uname, utype, ulat, ulon in uni_rows:
            dist_km = _haversine_km(centroid_lat, centroid_lon, ulat, ulon)
            if dist_km <= 15:
                unis.append({
                    "name": uname,
                    "school_type": utype,
                    "dist_km": round(dist_km, 1),
                    "in_suburb": dist_km <= 2.0,
                })
        unis.sort(key=lambda x: x["dist_km"])

        # Public & private hospitals within ~15km
        DEGREE_15KM_H = 0.135
        hosp_stmt2 = text("""
            SELECT h.name, h.facility_type, h.lat, h.lon
            FROM health_facilities h
            WHERE h.facility_type IN ('public_hospital','private_hospital')
              AND h.is_operational = 1
              AND h.lat BETWEEN :lat_min AND :lat_max
              AND h.lon BETWEEN :lon_min AND :lon_max
              AND h.lat IS NOT NULL AND h.lon IS NOT NULL
            ORDER BY h.name
        """)
        hosp_rows2 = (await db.execute(hosp_stmt2, {
            "lat_min": centroid_lat - DEGREE_15KM_H, "lat_max": centroid_lat + DEGREE_15KM_H,
            "lon_min": centroid_lon - DEGREE_15KM_H, "lon_max": centroid_lon + DEGREE_15KM_H,
        })).all()
        for hname, htype, hlat, hlon in hosp_rows2:
            dist_km = _haversine_km(centroid_lat, centroid_lon, hlat, hlon)
            if dist_km <= 15:
                hospitals_nearby.append({
                    "name": hname,
                    "type": "Public Hospital" if htype == "public_hospital" else "Private Hospital",
                    "dist_km": round(dist_km, 1),
                    "in_suburb": dist_km <= 2.0,
                    "impact_score": 1.0 if dist_km <= 2.0 else 0.5,
                })
        hospitals_nearby.sort(key=lambda x: x["dist_km"])

    # ── Percentile rank ───────────────────────────────────────────────────
    # National rank: how does this suburb compare to all 2,300 aggregates?
    inv = agg.investment_score or 0
    nat_rank_stmt = text("""
        SELECT COUNT(*) FROM suburb_aggregates
        WHERE investment_score IS NOT NULL AND investment_score > :score
    """)
    nat_above = (await db.execute(nat_rank_stmt, {"score": inv})).scalar() or 0
    nat_total_stmt = text("SELECT COUNT(*) FROM suburb_aggregates WHERE investment_score IS NOT NULL")
    nat_total = (await db.execute(nat_total_stmt)).scalar() or 1
    nat_rank  = nat_above + 1
    nat_pct   = round((1 - nat_above / nat_total) * 100, 1)  # percentile (100 = best)

    # State rank
    state_rank_stmt = text("""
        SELECT COUNT(*) FROM suburb_aggregates
        WHERE state = :state AND investment_score IS NOT NULL AND investment_score > :score
    """)
    state_above = (await db.execute(state_rank_stmt, {"state": agg.state, "score": inv})).scalar() or 0
    state_total_stmt = text("SELECT COUNT(*) FROM suburb_aggregates WHERE state = :state AND investment_score IS NOT NULL")
    state_total = (await db.execute(state_total_stmt, {"state": agg.state})).scalar() or 1
    state_rank  = state_above + 1

    # ── Peer suburbs ──────────────────────────────────────────────────────
    # 5 suburbs with similar investment score in the same state (±1 point, exclude self)
    score_band_lo = max(0, inv - 1.0)
    score_band_hi = min(10, inv + 1.0)
    peers_stmt = text("""
        SELECT suburb_id, suburb_name, state, population, investment_score,
               liveability_score, growth_score, education_score
        FROM suburb_aggregates
        WHERE state = :state
          AND suburb_id != :self_id
          AND investment_score BETWEEN :lo AND :hi
          AND investment_score IS NOT NULL
        ORDER BY ABS(investment_score - :score)
        LIMIT 5
    """)
    peer_rows = (await db.execute(peers_stmt, {
        "state": agg.state, "self_id": suburb_id,
        "lo": score_band_lo, "hi": score_band_hi, "score": inv,
    })).fetchall()
    peers = [
        {
            "suburb_id":       r[0],
            "suburb_name":     r[1],
            "state":           r[2],
            "population":      r[3],
            "investment_score": _r(r[4]),
            "liveability_score": _r(r[5]),
            "growth_score":    _r(r[6]),
            "education_score": _r(r[7]),
        }
        for r in peer_rows
    ]

    scores_agg = {
        "investment_score":     _r(agg.investment_score),
        "liveability_score":    _r(agg.liveability_score),
        "education_score":      _r(agg.education_score),
        "growth_score":         _r(agg.growth_score),
        "demographic_score":    _r(agg.demographic_score),
        "housing_score":        _r(agg.housing_score),
        "infrastructure_score": _r(agg.infrastructure_score),
        "gentrification_index": _r(agg.gentrification_index),
    }

    return {
        "suburb_id":   suburb_id,
        "suburb_name": agg.suburb_name,
        "state":       agg.state,
        "sa2_count":   agg.sa2_count,
        "sa2_codes":   agg.sa2_codes,
        "sa2_names":   agg.sa2_names,
        "population":  agg.population,
        "is_aggregate": agg.sa2_count > 1,

        "scores":      scores_agg,
        "sa2_breakdown": sa2_breakdown,

        # Weighted averages for top-level facts panel
        "facts": {
            "median_income":      _r(agg.median_income),
            "median_age":         _r(agg.median_age),
            "unemployment_pct":   _r(agg.unemployment_pct),
            "uni_degree_pct":     _r(agg.uni_degree_pct),
            "pop_growth_proj_pct": _r(agg.pop_growth_proj_pct),
            # Granular facts (single SA2 only, null for multi)
            **top_facts_detail,
        },
        "intermediates": top_intermediates,

        "rank": {
            "national_rank":  nat_rank,
            "national_total": nat_total,
            "national_pct":   nat_pct,
            "state_rank":     state_rank,
            "state_total":    state_total,
        },
        "peer_suburbs": peers,

        # Key nearby facilities
        "universities_nearby": unis,
        "hospitals_nearby":    hospitals_nearby,

        "schools_in_suburb":  schools_in,
        "schools_adjacent":   schools_adj[:8],  # cap adjacent list
        "adjacent_has_train": adjacent_has_train,
        "adjacent_train_suburbs": adjacent_train_suburbs,

        "risk_flags":    agg.risk_flags or [],
        "tags":          _generate_tags(agg),
        "insight":       _generate_insight(agg),
        "score_version": agg.score_version,
        "note": f"Scores are population-weighted averages across {agg.sa2_count} ABS statistical areas." if agg.sa2_count > 1 else None,
    }


def _r(v: float | None) -> float | None:
    return round(v, 2) if v is not None else None


# ---------------------------------------------------------------------------
# /places endpoint — on-demand Foursquare place counts
# ---------------------------------------------------------------------------

@router.get("/{suburb_id}/places")
async def suburb_places(
    suburb_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Return Foursquare place counts for a suburb, fetched on-demand and cached 30 days.

    Requires FOURSQUARE_API_KEY in backend/.env.
    Returns {"source": "foursquare_v3", "radius_m": ..., "counts": {...}, "cached": bool}
    """
    agg = await db.get(SuburbAggregate, suburb_id)
    if agg is None:
        raise HTTPException(status_code=404, detail=f"Suburb '{suburb_id}' not found.")

    api_key = os.getenv("FOURSQUARE_API_KEY", "").strip()
    if not api_key:
        return {
            "suburb_id": suburb_id,
            "source": None,
            "counts": None,
            "status": "no_api_key",
            "message": "Add FOURSQUARE_API_KEY to backend/.env to enable live place counts.",
        }

    # Compute centroid from first SA2's geometry
    sa2_codes = agg.sa2_codes or []
    if not sa2_codes:
        raise HTTPException(status_code=503, detail="No SA2 codes for this suburb.")

    lat, lon = await _get_centroid(db, sa2_codes[0])
    if lat is None:
        raise HTTPException(status_code=503, detail="No geometry for this suburb.")

    # Radius: approximate based on population density
    pop = agg.population or 5000
    # Urban ≥ 10k pop → 1.5km, semi-urban 5-10k → 2km, rural < 5k → 3km
    if pop >= 10000:  radius_m = 1500
    elif pop >= 5000: radius_m = 2000
    else:             radius_m = 3000

    # Run in sync thread pool (requests is synchronous)
    import asyncio
    from app.ingestion.foursquare_places import get_or_fetch
    from app.db.session import get_sync_session

    def _sync_fetch():
        sync_db = get_sync_session()
        try:
            return get_or_fetch(suburb_id, lat, lon, radius_m, api_key, sync_db)
        finally:
            sync_db.close()

    loop = asyncio.get_event_loop()
    counts = await loop.run_in_executor(None, _sync_fetch)

    # Check if result was cached
    from app.db.models import SuburbPlaceCache
    from datetime import timedelta
    cached_row = await db.get(SuburbPlaceCache, suburb_id)
    was_cached = cached_row is not None

    return {
        "suburb_id":  suburb_id,
        "suburb_name": agg.suburb_name,
        "state":      agg.state,
        "source":     "foursquare_v3",
        "radius_m":   radius_m,
        "lat":        lat,
        "lon":        lon,
        "counts":     counts,
        "cached":     was_cached,
        "status":     "ok" if counts else "fetch_failed",
    }


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Approximate distance in km between two WGS84 points."""
    import math
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


async def _get_centroid(db: AsyncSession, sa2_code: str) -> tuple[float | None, float | None]:
    """Compute centroid lat/lon from SA2 geometry."""
    import json as json_mod
    row = await db.get(SA2Region, sa2_code)
    if not row or not row.geometry_geojson:
        return None, None
    try:
        geom = json_mod.loads(row.geometry_geojson)
        coords_flat: list = []

        def _collect(rings):
            for ring in rings:
                if ring and isinstance(ring[0], (int, float)):
                    return
                for pt in ring:
                    if isinstance(pt, (list, tuple)) and len(pt) >= 2:
                        coords_flat.append((float(pt[0]), float(pt[1])))

        if geom["type"] == "Polygon":
            _collect(geom["coordinates"])
        elif geom["type"] == "MultiPolygon":
            for poly in geom["coordinates"]:
                _collect(poly)

        if coords_flat:
            lon = sum(c[0] for c in coords_flat) / len(coords_flat)
            lat = sum(c[1] for c in coords_flat) / len(coords_flat)
            return lat, lon
    except Exception:
        pass
    return None, None


def _generate_tags(agg: SuburbAggregate) -> list[str]:
    tags: list[str] = []
    inv = agg.investment_score or 0
    if inv >= 7.5:   tags.append("Premium Investment")
    elif inv >= 6.5: tags.append("Strong Investment")
    elif inv >= 5.5: tags.append("Moderate Growth")
    else:            tags.append("Emerging Opportunity")
    if (agg.gentrification_index or 0) >= 7.0: tags.append("Gentrifying")
    if (agg.growth_score or 0) >= 7.5:         tags.append("High Growth")
    if (agg.liveability_score or 0) >= 7.5:    tags.append("High Liveability")
    if (agg.education_score or 0) >= 7.5:      tags.append("Strong Schools")
    if (agg.infrastructure_score or 0) >= 7.5: tags.append("Infrastructure Pipeline")
    return tags


def _generate_insight(agg: SuburbAggregate) -> str:
    name = agg.suburb_name
    inv  = agg.investment_score or 0
    if inv >= 7.5:   lead = f"{name} is a premium investment prospect"
    elif inv >= 6.5: lead = f"{name} presents a strong investment case"
    elif inv >= 5.5: lead = f"{name} shows moderate investment potential"
    else:            lead = f"{name} is an emerging opportunity"

    dims = {
        "liveability": agg.liveability_score or 0,
        "growth":      agg.growth_score or 0,
        "education":   agg.education_score or 0,
        "demographic": agg.demographic_score or 0,
        "housing":     agg.housing_score or 0,
        "infrastructure": agg.infrastructure_score or 0,
    }
    labels = {
        "liveability": "liveability and amenity access",
        "growth": "growth and gentrification signals",
        "education": "education quality",
        "demographic": "demographic fundamentals",
        "housing": "housing market conditions",
        "infrastructure": "government infrastructure pipeline",
    }
    best  = max(dims, key=dims.get)
    worst = min(dims, key=dims.get)
    middle = f", driven by strong {labels[best]}." if dims[best] >= 7.0 else "."

    facts = []
    if (agg.pop_growth_proj_pct or 0) >= 15:
        facts.append(f"ABS projects {agg.pop_growth_proj_pct:.0f}% population growth to 2031")
    if (agg.gentrification_index or 0) >= 7.5:
        facts.append("strong gentrification signals suggest above-average capital growth")
    if dims[worst] < 4.0:
        facts.append(f"{labels[worst]} is the primary drag on the overall score")
    third = f" {facts[0].capitalize()}." if facts else ""
    multi = f" Covers {agg.sa2_count} ABS statistical areas." if agg.sa2_count > 1 else ""
    return lead + middle + third + multi
