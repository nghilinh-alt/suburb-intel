"""Suburb scoring engine — v1.1

Pure functions — no database access. Takes a pandas DataFrame of per-SA2
features, returns the same DataFrame with score columns added.

v1.1 changes from v1.0:
  - Liveability: replaced unreliable Overture amenity_score/osm_medical_centers
    with ABS Business Register counts (biz_food_services, biz_health_social,
    biz_arts_recreation, biz_retail_trade) — far more accurate for AU suburbs
  - Growth: added biz_construction_pct as local development activity signal;
    replaced osm_cafes with biz_food_services in gentrification composite;
    added moved_in_5yr_pct as medium-term mobility signal
  - Demographic: added families_with_children_pct and seifa_ieo_decile
  - Housing: added renters_pct (rental demand) and median_rent_weekly (rent level);
    rebalanced weights to reflect investment perspective
  - Infrastructure: added biz_construction_pct as dev activity proxy

Pipeline:
  1. compute_transit_score     — weighted PT stop count
  2. compute_gentrification    — composite z-score (ABS biz data, census mobility)
  3. compute_infra_per_capita  — committed investment ÷ population
  4. normalise_inputs          — percentile-rank all raw inputs (0–100)
  5. score_liveability         — ABS biz access + transit + hospital + parks
  6. score_education           — school ICSEA quality + type coverage
  7. score_growth              — pop growth + infra + gentrification + construction
  8. score_demographic         — income + SEIFA + workforce + family demand
  9. score_housing             — stress + rental demand + rent level
 10. score_infrastructure      — committed govt pipeline + local dev
 11. score_composite           — weighted average of dimensions
 12. compute_risk_flags        — threshold-based flags
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SCORE_VERSION = "v1.4"

# ---------------------------------------------------------------------------
# Composite weights
# ---------------------------------------------------------------------------

_COMPOSITE_WEIGHTS = {
    "liveability_score":    0.20,
    "growth_score":         0.25,
    "education_score":      0.15,
    "demographic_score":    0.15,
    "housing_score":        0.15,
    "infrastructure_score": 0.10,
}

# ---------------------------------------------------------------------------
# Risk flag thresholds
# ---------------------------------------------------------------------------

_RISK_THRESHOLDS = {
    "high_mortgage_stress":  ("high_mortgage_stress_pct", ">",  15.0),
    "high_unemployment":     ("unemployment_pct",          ">",   8.0),
    "high_social_housing":   ("social_housing_pct",        ">",  20.0),
    "industrial_zone":       ("zone_pct_industrial",        ">",  30.0),
    "low_amenity":           ("biz_food_services",          "pct_lt", 20.0),  # bottom 20% nationally
    "no_hospital_nearby":    ("health_hospital_score",      "==",  0.0),
    "low_transit":           ("transit_score_raw",          "<",   5.0),
    "declining_population":  ("pop_growth_proj_pct",        "<",  -5.0),
    "low_income":            ("median_income",              "pct_lt", 25.0),
}


# ===========================================================================
# Main entry point
# ===========================================================================

def run_scoring_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = _compute_transit_score(df)
    df = _compute_gentrification(df)
    df = _compute_infra_per_capita(df)
    df = _compute_density_metrics(df)
    df = _normalise_inputs(df)
    df = _score_liveability(df)
    df = _score_education(df)
    df = _score_growth(df)
    df = _score_demographic(df)
    df = _score_housing(df)
    df = _score_infrastructure(df)
    df = _score_composite(df)
    df = _compute_risk_flags(df)
    df["score_version"] = SCORE_VERSION
    return df


# ===========================================================================
# Phase 1 — Derived intermediates
# ===========================================================================

def _s(df: pd.DataFrame, col: str) -> pd.Series:
    """Safe column getter — returns zeros if column missing."""
    return df.get(col, pd.Series(0, index=df.index)).fillna(0)


def _compute_transit_score(df: pd.DataFrame) -> pd.DataFrame:
    """Weighted PT stop count: train×4, tram×3, ferry×2, bus×1."""
    df["transit_score_raw"] = (
        _s(df, "pt_stop_train") * 4 +
        _s(df, "pt_stop_tram")  * 3 +
        _s(df, "pt_stop_ferry") * 2 +
        _s(df, "pt_stop_bus")   * 1
    )
    return df


def _compute_gentrification(df: pd.DataFrame) -> pd.DataFrame:
    """Composite gentrification signal — z-scores of 7 indicators (weighted average).

    v1.1: uses biz_food_services (ABS, accurate) instead of osm_cafes (Overture, unreliable);
    adds moved_in_5yr_pct as medium-term mobility signal.
    """
    pop = _s(df, "population").replace(0, np.nan)

    # Per-capita business density (businesses per 1,000 residents)
    df["biz_food_density"]  = _s(df, "biz_food_services")    / pop * 1000
    df["approval_rate"]     = _s(df, "building_approvals_1yr") / pop * 1000

    components = {
        "moved_in_1yr_pct":           2.0,   # current residential churn
        "moved_in_5yr_pct":           1.0,   # medium-term arrival (NEW)
        "uni_degree_pct":             1.5,
        "professionals_managers_pct": 1.5,
        "biz_food_density":           1.0,   # ABS food business density (was osm_cafes)
        "approval_rate":              1.0,   # construction activity
        "pop_growth_proj_pct":        1.0,
    }
    total_w = sum(components.values())

    z_parts: list[pd.Series] = []
    for col, w in components.items():
        s = df.get(col, pd.Series(np.nan, index=df.index))
        mu, sigma = s.mean(), s.std()
        z = ((s - mu) / sigma).clip(-3, 3) if sigma and sigma > 0 else pd.Series(0.0, index=df.index)
        z_parts.append(z * w)

    df["gentrification_raw"] = sum(z_parts) / total_w
    return df


def _compute_infra_per_capita(df: pd.DataFrame) -> pd.DataFrame:
    pop = _s(df, "population").replace(0, np.nan)
    df["infra_per_capita"] = _s(df, "infra_committed_aud") / pop
    return df


def _compute_density_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Population density and parks per km² — normalised for suburb size.

    Using area-normalised parks is fairer than raw park count:
    a dense 2km² suburb with 10 parks (5/km²) has far better green access
    than a 50km² outer suburb with 10 parks (0.2/km²).
    """
    area = _s(df, "area_sqkm").replace(0, np.nan)
    pop  = _s(df, "population").replace(0, np.nan)

    df["population_density"] = pop / area                           # people/km²
    df["parks_per_km2"]      = _s(df, "osm_parks") / area         # parks/km²
    df["biz_food_per_1000"]  = _s(df, "biz_food_services") / pop * 1000
    df["biz_health_per_1000"]= _s(df, "biz_health_social") / pop * 1000
    return df


# ===========================================================================
# Phase 2 — Normalise to percentile ranks (0–100)
# ===========================================================================

def _pct(s: pd.Series) -> pd.Series:
    return s.rank(pct=True, na_option="keep") * 100

def _pct_inv(s: pd.Series) -> pd.Series:
    return 100 - _pct(s)

def _fill50(s: pd.Series) -> pd.Series:
    return s.fillna(50.0)


def _normalise_inputs(df: pd.DataFrame) -> pd.DataFrame:
    # ── Liveability ──────────────────────────────────────────────────────────
    # ABS Business Register counts (accurate, replace unreliable Overture amenity_score)
    df["biz_food_pct"]    = _fill50(_pct(_s(df, "biz_food_services")))     # cafes/restaurants/takeaway
    df["biz_health_pct"]  = _fill50(_pct(_s(df, "biz_health_social")))     # GPs/pharmacies/allied health
    df["biz_arts_pct"]    = _fill50(_pct(_s(df, "biz_arts_recreation")))   # gyms/sport/entertainment
    df["biz_retail_pct"]  = _fill50(_pct(_s(df, "biz_retail_trade")))      # shops/supermarkets

    df["transit_pct"]     = _fill50(_pct(df["transit_score_raw"]))
    df["hospital_pct"]    = _fill50(_pct(_s(df, "health_hospital_score")))
    # parks_per_km² is more meaningful than raw count — normalises for suburb size
    # A dense 2km² suburb with 5 parks scores the same as a 50km² suburb with 125 parks
    df["park_pct"]        = _fill50(_pct(df["parks_per_km2"]))

    # ── Education ────────────────────────────────────────────────────────────
    # edu_best_school_pct: the ICSEA national percentile of the single best school
    # in or adjacent to the SA2. This directly measures catchment premium potential.
    # A Top 5% school (pct=95) near a suburb is worth far more than the average.
    df["best_school_pct"] = _fill50(_pct(_s(df, "edu_best_school_pct")))
    df["icsea_pct"]       = _fill50(_pct(_s(df, "edu_avg_icsea")))
    df["top_school_pct"]  = _fill50(_pct(_s(df, "edu_top_school_count")))
    df["secondary_pct"]   = _fill50(_pct(_s(df, "edu_secondary_count")))
    df["tertiary_pct"]    = _fill50(_pct(_s(df, "edu_tertiary_count")))

    # ── Growth ───────────────────────────────────────────────────────────────
    df["pop_growth_pct_rank"]    = _fill50(_pct(_s(df, "pop_growth_proj_pct")))
    df["infra_cap_pct"]          = _fill50(_pct(_s(df, "infra_per_capita")))
    df["approvals_pct"]          = _fill50(_pct(_s(df, "building_approvals_1yr")))
    df["gentrif_pct"]            = _fill50(_pct(df["gentrification_raw"]))
    df["pda_pct"]                = _fill50(_pct(_s(df, "infra_pda_overlap")))
    df["biz_construction_pct"]   = _fill50(_pct(_s(df, "biz_construction")))   # NEW

    # ── Demographic ──────────────────────────────────────────────────────────
    df["income_pct"]      = _fill50(_pct(_s(df, "median_income")))
    df["seifa_pct"]       = _fill50(_pct(_s(df, "seifa_irsad_decile")))
    df["seifa_ieo_pct"]   = _fill50(_pct(_s(df, "seifa_ieo_decile")))          # NEW
    df["degree_pct"]      = _fill50(_pct(_s(df, "uni_degree_pct")))
    df["unemp_pct"]       = _fill50(_pct_inv(_s(df, "unemployment_pct")))
    df["profess_pct"]     = _fill50(_pct(_s(df, "professionals_managers_pct")))
    df["families_pct"]    = _fill50(_pct(_s(df, "families_with_children_pct"))) # NEW

    # ── Housing ──────────────────────────────────────────────────────────────
    df["mortgage_stress_pct"]    = _fill50(_pct_inv(_s(df, "high_mortgage_stress_pct")))
    df["rent_stress_pct"]        = _fill50(_pct_inv(_s(df, "high_rent_stress_pct")))
    df["social_housing_pct_r"]   = _fill50(_pct_inv(_s(df, "social_housing_pct")))
    df["renters_pct_rank"]       = _fill50(_pct(_s(df, "renters_pct")))         # NEW — rental demand
    df["rent_level_pct"]         = _fill50(_pct(_s(df, "median_rent_weekly")))  # NEW — rent income potential
    df["hh_size_pct"]            = _fill50(_pct(_s(df, "avg_household_size")))

    # ── Infrastructure ───────────────────────────────────────────────────────
    df["infra_aud_pct"]          = _fill50(_pct(_s(df, "infra_committed_aud")))
    df["infra_count_pct"]        = _fill50(_pct(_s(df, "infra_project_count")))

    return df


# ===========================================================================
# Phase 3 — Dimension scorers (all output 0–10)
# ===========================================================================

def _dim(df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    total_w = sum(weights.values())
    result  = sum(df[col] * w for col, w in weights.items())
    return (result / total_w / 10).clip(0, 10)


def _score_liveability(df: pd.DataFrame) -> pd.DataFrame:
    """
    ABS Business Register replaces unreliable Overture counts.
    biz_food_services covers cafes + restaurants + takeaways (verified accurate).
    biz_health_social covers GPs + pharmacies + allied health (Camp Hill: 215 vs Algester: 67).
    """
    df["liveability_score"] = _dim(df, {
        "biz_food_pct":   20,   # ABS food & beverage businesses
        "biz_health_pct": 20,   # ABS health & medical businesses
        "transit_pct":    20,   # Weighted PT stop count
        "hospital_pct":   10,   # Public hospital adjacency (AIHW data)
        "biz_arts_pct":   15,   # ABS arts & recreation (gyms, sport)
        "biz_retail_pct": 10,   # ABS retail (shops, supermarkets)
        "park_pct":       5,    # OSM parks (parks are OK in Overture)
    })
    return df


def _score_education(df: pd.DataFrame) -> pd.DataFrame:
    """
    Education score measures K-12 school quality and access — the primary
    investment driver (catchment premium, family demand).

    Tertiary (university/TAFE) removed from score entirely:
    - Having no university nearby should NOT penalise a suburb
    - Most suburbs have zero tertiary, so it was an unfair drag
    - University proximity is shown as an informational bonus in the UI
      rather than impacting the investment score

    Formula:
      best_school_pct  45% — quality of single best K-12 school in/adjacent
      icsea_pct        30% — average school quality across all catchment schools
      top_school_pct   20% — breadth of high-performing school options
      secondary_pct     5% — secondary school access (families need P+S)
    """
    df["education_score"] = _dim(df, {
        "best_school_pct": 45,
        "icsea_pct":       30,
        "top_school_pct":  20,
        "secondary_pct":    5,
    })
    return df


def _score_growth(df: pd.DataFrame) -> pd.DataFrame:
    """Added biz_construction_pct — ABS construction business density
    signals local development activity beyond govt projects."""
    df["growth_score"] = _dim(df, {
        "pop_growth_pct_rank":  25,
        "infra_cap_pct":        25,
        "gentrif_pct":          20,
        "approvals_pct":        15,
        "biz_construction_pct": 5,    # NEW — local construction activity
        "pda_pct":              10,
    })
    return df


def _score_demographic(df: pd.DataFrame) -> pd.DataFrame:
    """Added families_with_children_pct (family demand) and seifa_ieo_decile
    (education & occupation SEIFA — more targeted than IRSAD alone)."""
    df["demographic_score"] = _dim(df, {
        "income_pct":   25,
        "seifa_pct":    20,
        "degree_pct":   15,
        "unemp_pct":    15,
        "profess_pct":  10,
        "families_pct": 10,   # NEW — family demand for property
        "seifa_ieo_pct": 5,   # NEW — education/occupation SEIFA
    })
    return df


def _score_housing(df: pd.DataFrame) -> pd.DataFrame:
    """Added renters_pct (rental demand signal) and rent_level_pct (rental income potential).
    Higher renters % → more investor-relevant demand.
    Higher median rent → stronger rental income base."""
    df["housing_score"] = _dim(df, {
        "mortgage_stress_pct":  25,   # lower stress = healthier market
        "rent_stress_pct":      15,   # lower rent stress = sustainable rents
        "social_housing_pct_r": 10,   # lower social housing = stable market
        "renters_pct_rank":     25,   # NEW — high renters = strong investor demand
        "rent_level_pct":       15,   # NEW — higher rent = more income potential
        "hh_size_pct":          10,   # bigger households = more family demand
    })
    return df


def _score_infrastructure(df: pd.DataFrame) -> pd.DataFrame:
    """Added biz_construction_pct — local construction activity
    supplements govt project pipeline as development signal."""
    df["infrastructure_score"] = _dim(df, {
        "infra_aud_pct":         45,
        "infra_count_pct":       30,
        "pda_pct":               15,
        "biz_construction_pct":  10,  # NEW — local dev activity proxy
    })
    return df


def _score_composite(df: pd.DataFrame) -> pd.DataFrame:
    total_w = sum(_COMPOSITE_WEIGHTS.values())
    result  = sum(df[col].fillna(5.0) * w for col, w in _COMPOSITE_WEIGHTS.items())
    df["investment_score"]    = (result / total_w).clip(0, 10)
    df["gentrification_index"] = (df["gentrif_pct"] / 10).clip(0, 10)
    return df


# ===========================================================================
# Phase 4 — Risk flags
# ===========================================================================

def _compute_risk_flags(df: pd.DataFrame) -> pd.DataFrame:
    def _flag(col: str, op: str, threshold: float) -> pd.Series:
        s = df.get(col, pd.Series(np.nan, index=df.index)).fillna(np.nan)
        if op == ">":       return s > threshold
        if op == "<":       return s < threshold
        if op == "==":      return s == threshold
        if op == "pct_lt":  return _pct(s) < threshold
        return pd.Series(False, index=df.index)

    flags_df = pd.DataFrame({
        name: _flag(col, op, thr)
        for name, (col, op, thr) in _RISK_THRESHOLDS.items()
    }, index=df.index)

    df["risk_flags"] = [
        [f for f in _RISK_THRESHOLDS if row.get(f, False)]
        for _, row in flags_df.iterrows()
    ]
    return df
