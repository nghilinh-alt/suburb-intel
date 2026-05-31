"""Backfill job: compute and store SuburbScore for every SA2 with census data.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.jobs.backfill_scores [--year 2021]
"""

from __future__ import annotations

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text

logger = logging.getLogger(__name__)


# ===========================================================================
# Data loading — SQL queries that produce per-SA2 intermediates
# ===========================================================================

_CENSUS_SQL = """
SELECT
    m.sa2_code,
    r.sa2_name,
    r.state,
    -- Demographics
    m.population, m.median_age, m.median_income,
    m.overseas_born_pct, m.families_with_children_pct,
    m.renters_pct, m.owners_pct, m.social_housing_pct,
    m.avg_household_size,
    -- Property
    m.separate_house_pct, m.flat_apartment_pct,
    m.flat_low_rise_pct, m.flat_mid_rise_pct, m.flat_high_rise_pct,
    m.high_mortgage_stress_pct, m.high_rent_stress_pct,
    -- Growth
    m.moved_in_1yr_pct, m.moved_in_5yr_pct,
    m.uni_degree_pct, m.professionals_managers_pct,
    -- Transport
    m.pt_stop_train, m.pt_stop_tram, m.pt_stop_bus, m.pt_stop_ferry,
    -- Amenities (Overture)
    m.osm_cafes, m.osm_restaurants, m.osm_supermarkets, m.osm_parks,
    m.osm_gyms, m.osm_hospitals, m.osm_medical_centers, m.osm_pharmacies,
    m.osm_shopping_centres, m.amenity_score,
    -- Service businesses (Overture)
    m.osm_petrol_stations, m.osm_hardware_stores, m.osm_post_offices, m.osm_vets,
    -- ABS Business Register counts (accurate, used in v1.1 scoring)
    m.biz_food_services, m.biz_health_social, m.biz_arts_recreation,
    m.biz_retail_trade, m.biz_construction, m.biz_professional,
    m.biz_education, m.biz_finance, m.biz_other_services, m.biz_total,
    -- Rent/mortgage levels
    m.median_rent_weekly, m.median_mortgage_monthly,
    -- Risk
    m.one_bedroom_pct, m.unemployment_pct,
    -- SEIFA
    m.seifa_irsd_score, m.seifa_irsd_decile,
    m.seifa_irsad_score, m.seifa_irsad_decile,
    m.seifa_ieo_score, m.seifa_ieo_decile,
    -- Building & population
    m.building_approvals_1yr,
    m.pop_proj_2026, m.pop_proj_2031, m.pop_growth_proj_pct,
    -- Commute
    m.pt_commute_pct, m.car_commute_pct, m.work_from_home_pct,
    m.zero_car_dwellings_pct
FROM abs_census_metrics m
JOIN sa2_regions r ON r.sa2_code = m.sa2_code
WHERE m.year = :year
"""

_EDUCATION_SQL = """
SELECT
    l.sa2_code,
    SUM(
        CASE WHEN s.icsea IS NOT NULL AND s.total_enrolments IS NOT NULL
             THEN s.icsea * s.total_enrolments * l.impact_score
             ELSE 0 END
    ) / NULLIF(SUM(
        CASE WHEN s.icsea IS NOT NULL AND s.total_enrolments IS NOT NULL
             THEN s.total_enrolments * l.impact_score
             ELSE 0 END
    ), 0) AS edu_avg_icsea,
    COUNT(CASE WHEN s.icsea >= 1100 AND l.impact_score >= 0.5 THEN 1 END) AS edu_top_school_count,
    COUNT(CASE WHEN s.school_type = 'Primary' AND l.impact_score >= 0.5 THEN 1 END) AS edu_primary_count,
    COUNT(CASE WHEN s.school_type IN ('Secondary','Combined') AND l.impact_score >= 0.5 THEN 1 END) AS edu_secondary_count,
    COUNT(CASE WHEN s.school_type IN ('University','TAFE') AND l.impact_score >= 0.5 THEN 1 END) AS edu_tertiary_count
FROM sa2_school_link l
JOIN schools s ON s.acara_id = l.acara_id
GROUP BY l.sa2_code
"""

_HEALTH_SQL = """
SELECT
    l.sa2_code,
    SUM(CASE WHEN h.facility_type = 'public_hospital'
             THEN l.impact_score ELSE 0 END) AS health_hospital_score,
    SUM(CASE WHEN h.facility_type IN ('aged_care','nursing_home') AND l.impact_score = 1.0
             THEN 1 ELSE 0 END) AS health_aged_care_count
FROM sa2_health_link l
JOIN health_facilities h ON h.facility_id = l.facility_id
WHERE h.is_operational = 1
GROUP BY l.sa2_code
"""

_INFRA_SQL = """
SELECT
    l.sa2_code,
    SUM(COALESCE(p.agc_aud, p.value_aud, 0) * l.impact_score) AS infra_committed_aud,
    COUNT(*) AS infra_project_count
FROM sa2_project_link l
JOIN infrastructure_projects p ON p.project_id = l.project_id
WHERE p.status IN ('in_planning', 'under_construction')
GROUP BY l.sa2_code
"""

_PDA_SQL = """
SELECT sa2_code, MAX(overlap_pct) AS infra_pda_overlap
FROM sa2_planning_link
GROUP BY sa2_code
"""

_ZONING_SQL = """
SELECT sa2_code,
    zone_pct_high_density_res, zone_pct_medium_density_res, zone_pct_low_density_res,
    zone_pct_mixed_use, zone_pct_commercial, zone_pct_industrial,
    zone_pct_residential_total, zone_pct_urban_development
FROM sa2_zoning
"""


def _load_all_features(db: Session, year: int = 2021) -> pd.DataFrame:
    """Load all SA2 features from DB into a single wide DataFrame."""
    logger.info("Loading census metrics ...")
    census = pd.read_sql(text(_CENSUS_SQL), db.bind, params={"year": year})
    logger.info("  %d SA2s loaded", len(census))

    logger.info("Loading education intermediates ...")
    edu = pd.read_sql(text(_EDUCATION_SQL), db.bind)

    logger.info("Loading health intermediates ...")
    health = pd.read_sql(text(_HEALTH_SQL), db.bind)

    logger.info("Loading infrastructure intermediates ...")
    infra = pd.read_sql(text(_INFRA_SQL), db.bind)

    logger.info("Loading PDA planning intermediates ...")
    pda = pd.read_sql(text(_PDA_SQL), db.bind)

    logger.info("Loading NSW zoning data ...")
    zoning = pd.read_sql(text(_ZONING_SQL), db.bind)

    # Merge all into one wide DataFrame on sa2_code
    df = census.copy()
    for other in [edu, health, infra, pda, zoning]:
        df = df.merge(other, on="sa2_code", how="left")

    # health_gp_count is already in census (osm_medical_centers)
    df["health_gp_count"] = df.get("osm_medical_centers", pd.Series(0, index=df.index)).fillna(0).astype(int)

    logger.info("Feature DataFrame: %d rows × %d columns", len(df), len(df.columns))
    return df


# ===========================================================================
# Write results
# ===========================================================================

def _write_scores(df: pd.DataFrame, db: Session) -> tuple[int, int]:
    """Upsert scored rows into suburb_scores. Returns (inserted, updated)."""
    from app.db.models import SuburbScore, Base
    from app.db.session import sync_engine
    Base.metadata.create_all(bind=sync_engine)

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    score_cols = [
        "investment_score", "liveability_score", "education_score",
        "growth_score", "demographic_score", "housing_score",
        "infrastructure_score", "gentrification_index",
        "edu_avg_icsea", "edu_top_school_count", "edu_secondary_count",
        "edu_tertiary_count", "health_hospital_score", "health_gp_count",
        "infra_committed_aud", "infra_project_count", "transit_score_raw",
        "risk_flags", "score_version",
    ]

    inserted = updated = 0
    for _, row in df.iterrows():
        sa2 = row["sa2_code"]
        existing = db.get(SuburbScore, sa2)

        kwargs = {"sa2_code": sa2, "updated_at": now}
        for col in score_cols:
            val = row.get(col)
            if isinstance(val, float) and pd.isna(val):
                val = None
            kwargs[col] = val

        if existing is None:
            db.add(SuburbScore(**kwargs))
            inserted += 1
        else:
            for k, v in kwargs.items():
                setattr(existing, k, v)
            updated += 1

    db.commit()
    return inserted, updated


# ===========================================================================
# Main entry point
# ===========================================================================

def run_backfill(db: Session, *, year: int = 2021) -> str:
    from app.core.scoring_engine import run_scoring_pipeline

    logger.info("=== Suburb Score Backfill (year=%d) ===", year)

    df = _load_all_features(db, year)

    logger.info("Running scoring pipeline ...")
    df = run_scoring_pipeline(df)

    logger.info("Writing scores to suburb_scores ...")
    inserted, updated = _write_scores(df, db)

    summary = (
        f"SA2s scored: {len(df)} | "
        f"Inserted: {inserted} | Updated: {updated} | "
        f"Version: {df['score_version'].iloc[0] if len(df) else 'n/a'}"
    )
    logger.info(summary)
    return summary


# ===========================================================================
# CLI
# ===========================================================================

if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    p = argparse.ArgumentParser(description="Backfill suburb_scores table")
    p.add_argument("--year", type=int, default=2021)
    args = p.parse_args()

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        result = run_backfill(db, year=args.year)
        print(f"Done: {result}")
    except Exception:
        logger.exception("Backfill failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
