"""Suburb scoring engine.

Pure functions — no database access. Takes a pandas DataFrame of per-SA2
features (one row per SA2), returns the same DataFrame with score columns added.

Pipeline:
  1. compute_transit_score     — derive transit_score_raw from PT stop counts
  2. compute_gentrification    — composite from current census signals
  3. normalise_inputs          — percentile-rank all raw inputs (0–100)
  4. score_liveability         — amenity + transit + healthcare + parks
  5. score_education           — school quality + coverage
  6. score_growth              — pop growth + investment + gentrification
  7. score_demographic         — income + SEIFA + workforce
  8. score_housing             — mortgage/rent stress + dwelling character
  9. score_infrastructure      — committed govt investment pipeline
 10. score_composite           — weighted average of dimensions
 11. compute_risk_flags        — threshold-based flag list per SA2

Version tag: update SCORE_VERSION when weights or inputs change so
the score_version column on suburb_scores tracks which run produced a result.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

SCORE_VERSION = "v1.0"

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
    "industrial_zone":       ("zone_pct_industrial",        ">",  30.0),  # NSW only
    "low_amenity":           ("amenity_score",              "<",   2.0),
    "no_hospital_nearby":    ("health_hospital_score",      "==",  0.0),
    "low_transit":           ("transit_score_raw",          "<",   5.0),
    "declining_population":  ("pop_growth_proj_pct",        "<",  -5.0),
    "low_income":            ("median_income",              "pct_lt", 25.0),  # below 25th pct
}


# ===========================================================================
# Main entry point
# ===========================================================================

def run_scoring_pipeline(df: pd.DataFrame) -> pd.DataFrame:
    """Run the full scoring pipeline on a DataFrame of SA2 features.

    Args:
        df: One row per SA2. Must contain the columns expected by each phase
            (missing columns produce null scores gracefully rather than crashing).

    Returns:
        The same DataFrame with score/flag columns added.
    """
    df = df.copy()
    df = _compute_transit_score(df)
    df = _compute_gentrification(df)
    df = _compute_infra_per_capita(df)

    # Normalise — each metric gets a _pct column (0–100, higher = better)
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
# Phase 1 — Derived intermediates (pure computation, no DB)
# ===========================================================================

def _compute_transit_score(df: pd.DataFrame) -> pd.DataFrame:
    """Weighted PT stop count: train×4, tram×3, ferry×2, bus×1."""
    df["transit_score_raw"] = (
        df.get("pt_stop_train",  pd.Series(0, index=df.index)).fillna(0) * 4 +
        df.get("pt_stop_tram",   pd.Series(0, index=df.index)).fillna(0) * 3 +
        df.get("pt_stop_ferry",  pd.Series(0, index=df.index)).fillna(0) * 2 +
        df.get("pt_stop_bus",    pd.Series(0, index=df.index)).fillna(0) * 1
    )
    return df


def _compute_gentrification(df: pd.DataFrame) -> pd.DataFrame:
    """Composite gentrification signal from current 2021 census data.

    Z-scores six indicators then averages them (with weights).
    Produces a raw continuous value; normalised to 0–10 in the scoring phase.
    """
    components = {
        "moved_in_1yr_pct":           2.0,
        "uni_degree_pct":             1.5,
        "professionals_managers_pct": 1.5,
        "cafe_density":               1.0,  # computed below
        "approval_rate":              1.0,  # computed below
        "pop_growth_proj_pct":        1.0,
    }

    # Derived inputs
    pop = df.get("population", pd.Series(np.nan, index=df.index)).replace(0, np.nan)
    df["cafe_density"]   = df.get("osm_cafes", pd.Series(0, index=df.index)).fillna(0) / pop * 1000
    df["approval_rate"]  = df.get("building_approvals_1yr", pd.Series(0, index=df.index)).fillna(0) / pop * 1000

    # Z-score each component and compute weighted average
    z_parts: list[pd.Series] = []
    total_weight = sum(components.values())

    for col, weight in components.items():
        series = df.get(col, pd.Series(np.nan, index=df.index))
        mean   = series.mean()
        std    = series.std()
        if std and std > 0:
            z = (series - mean) / std
        else:
            z = pd.Series(0.0, index=df.index)
        z = z.clip(-3, 3)
        z_parts.append(z * weight)

    df["gentrification_raw"] = sum(z_parts) / total_weight
    return df


def _compute_infra_per_capita(df: pd.DataFrame) -> pd.DataFrame:
    """Infrastructure investment per capita ($ per resident)."""
    pop = df.get("population", pd.Series(np.nan, index=df.index)).replace(0, np.nan)
    df["infra_per_capita"] = df.get("infra_committed_aud", pd.Series(0.0, index=df.index)).fillna(0) / pop
    return df


# ===========================================================================
# Phase 2 — Normalise to percentile ranks (0–100)
# ===========================================================================

def _pct(series: pd.Series) -> pd.Series:
    """Convert a series to Australian-wide percentile rank (0–100, null-safe)."""
    return series.rank(pct=True, na_option="keep") * 100


def _pct_inv(series: pd.Series) -> pd.Series:
    """Inverted percentile rank — lower raw value → higher score."""
    return 100 - _pct(series)


def _fill50(series: pd.Series) -> pd.Series:
    """Fill nulls with 50 (median rank — neutral assumption)."""
    return series.fillna(50.0)


def _normalise_inputs(df: pd.DataFrame) -> pd.DataFrame:
    """Attach _pct columns for every metric used downstream."""

    # Liveability
    df["amenity_pct"]          = (df.get("amenity_score", pd.Series(0.0, index=df.index)).fillna(0).clip(0, 10) * 10)
    df["transit_pct"]          = _fill50(_pct(df["transit_score_raw"]))
    df["gp_pharma_pct"]        = _fill50(_pct(
        df.get("osm_medical_centers", pd.Series(0, index=df.index)).fillna(0) +
        df.get("osm_pharmacies",      pd.Series(0, index=df.index)).fillna(0)
    ))
    df["hospital_pct"]         = _fill50(_pct(df.get("health_hospital_score", pd.Series(0.0, index=df.index)).fillna(0)))
    df["park_pct"]             = _fill50(_pct(df.get("osm_parks", pd.Series(0, index=df.index)).fillna(0)))

    # Education
    df["icsea_pct"]            = _fill50(_pct(df.get("edu_avg_icsea", pd.Series(np.nan, index=df.index))))
    df["top_school_pct"]       = _fill50(_pct(df.get("edu_top_school_count", pd.Series(0, index=df.index)).fillna(0)))
    df["secondary_pct"]        = _fill50(_pct(df.get("edu_secondary_count", pd.Series(0, index=df.index)).fillna(0)))
    df["tertiary_pct"]         = _fill50(_pct(df.get("edu_tertiary_count", pd.Series(0, index=df.index)).fillna(0)))

    # Growth
    df["pop_growth_pct_rank"]  = _fill50(_pct(df.get("pop_growth_proj_pct", pd.Series(np.nan, index=df.index))))
    df["infra_cap_pct"]        = _fill50(_pct(df.get("infra_per_capita", pd.Series(0.0, index=df.index)).fillna(0)))
    df["approvals_pct"]        = _fill50(_pct(df.get("building_approvals_1yr", pd.Series(0, index=df.index)).fillna(0)))
    df["gentrif_pct"]          = _fill50(_pct(df["gentrification_raw"]))
    df["pda_pct"]              = _fill50(_pct(df.get("infra_pda_overlap", pd.Series(0.0, index=df.index)).fillna(0)))

    # Demographic
    df["income_pct"]           = _fill50(_pct(df.get("median_income", pd.Series(np.nan, index=df.index))))
    df["seifa_pct"]            = _fill50(_pct(df.get("seifa_irsad_decile", pd.Series(np.nan, index=df.index))))
    df["degree_pct"]           = _fill50(_pct(df.get("uni_degree_pct", pd.Series(np.nan, index=df.index))))
    df["unemp_pct"]            = _fill50(_pct_inv(df.get("unemployment_pct", pd.Series(np.nan, index=df.index))))
    df["profess_pct"]          = _fill50(_pct(df.get("professionals_managers_pct", pd.Series(np.nan, index=df.index))))

    # Housing
    df["mortgage_stress_pct"]  = _fill50(_pct_inv(df.get("high_mortgage_stress_pct", pd.Series(np.nan, index=df.index))))
    df["rent_stress_pct"]      = _fill50(_pct_inv(df.get("high_rent_stress_pct", pd.Series(np.nan, index=df.index))))
    df["social_housing_pct_r"] = _fill50(_pct_inv(df.get("social_housing_pct", pd.Series(np.nan, index=df.index))))
    df["hh_size_pct"]          = _fill50(_pct(df.get("avg_household_size", pd.Series(np.nan, index=df.index))))

    # Infrastructure
    df["infra_aud_pct"]        = _fill50(_pct(df.get("infra_committed_aud", pd.Series(0.0, index=df.index)).fillna(0)))
    df["infra_count_pct"]      = _fill50(_pct(df.get("infra_project_count", pd.Series(0, index=df.index)).fillna(0)))

    return df


# ===========================================================================
# Phase 3 — Dimension scorers (all output 0–10)
# ===========================================================================

def _dim(df: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Weighted average of named _pct columns, output 0–10."""
    total_w = sum(weights.values())
    result = pd.Series(0.0, index=df.index)
    for col, w in weights.items():
        result += df[col] * w
    return (result / total_w / 10).clip(0, 10)


def _score_liveability(df: pd.DataFrame) -> pd.DataFrame:
    df["liveability_score"] = _dim(df, {
        "amenity_pct":   35,
        "transit_pct":   25,
        "gp_pharma_pct": 15,
        "hospital_pct":  10,
        "park_pct":      15,
    })
    return df


def _score_education(df: pd.DataFrame) -> pd.DataFrame:
    df["education_score"] = _dim(df, {
        "icsea_pct":      50,
        "top_school_pct": 20,
        "secondary_pct":  15,
        "tertiary_pct":   15,
    })
    return df


def _score_growth(df: pd.DataFrame) -> pd.DataFrame:
    df["growth_score"] = _dim(df, {
        "pop_growth_pct_rank": 30,
        "infra_cap_pct":       25,
        "gentrif_pct":         20,
        "approvals_pct":       15,
        "pda_pct":             10,
    })
    return df


def _score_demographic(df: pd.DataFrame) -> pd.DataFrame:
    df["demographic_score"] = _dim(df, {
        "income_pct":  30,
        "seifa_pct":   25,
        "degree_pct":  20,
        "unemp_pct":   15,
        "profess_pct": 10,
    })
    return df


def _score_housing(df: pd.DataFrame) -> pd.DataFrame:
    df["housing_score"] = _dim(df, {
        "mortgage_stress_pct":  30,
        "rent_stress_pct":      20,
        "social_housing_pct_r": 15,
        "hh_size_pct":          15,
        # Note: separate_house_pct / flat_high_rise_pct omitted here —
        # they are property-type neutral (house vs apartment is a user preference,
        # not inherently better or worse). Include when Domain prices make
        # value-per-m² calculation possible.
    })
    # Rescale since weights sum to 80 not 100
    df["housing_score"] = (df["housing_score"] * (100 / 80)).clip(0, 10)
    return df


def _score_infrastructure(df: pd.DataFrame) -> pd.DataFrame:
    df["infrastructure_score"] = _dim(df, {
        "infra_aud_pct":   50,
        "infra_count_pct": 30,
        "pda_pct":         20,
    })
    return df


def _score_composite(df: pd.DataFrame) -> pd.DataFrame:
    """Weighted average of dimension scores → investment_score."""
    result = pd.Series(0.0, index=df.index)
    total_w = sum(_COMPOSITE_WEIGHTS.values())
    for col, w in _COMPOSITE_WEIGHTS.items():
        result += df[col].fillna(5.0) * w  # missing dimension = neutral 5.0
    df["investment_score"] = (result / total_w).clip(0, 10)

    # Gentrification index: rescale gentrification_raw to 0–10 via percentile
    df["gentrification_index"] = (df["gentrif_pct"] / 10).clip(0, 10)

    return df


# ===========================================================================
# Phase 4 — Risk flags
# ===========================================================================

def _compute_risk_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Evaluate threshold rules; store as JSON-serialisable list per SA2."""

    def _flag_col(condition_col: str, op: str, threshold: float, df: pd.DataFrame) -> pd.Series:
        col = df.get(condition_col, pd.Series(np.nan, index=df.index)).fillna(np.nan)
        if op == ">":
            return col > threshold
        if op == "<":
            return col < threshold
        if op == "==":
            return col == threshold
        if op == "pct_lt":
            # Below a given Australian-wide percentile
            pct_col = _pct(col)
            return pct_col < threshold
        return pd.Series(False, index=df.index)

    flags_df = pd.DataFrame(index=df.index)
    for flag_name, (col, op, thr) in _RISK_THRESHOLDS.items():
        flags_df[flag_name] = _flag_col(col, op, thr, df)

    # Build list of raised flags per row
    df["risk_flags"] = [
        [flag for flag in _RISK_THRESHOLDS if row.get(flag, False)]
        for _, row in flags_df.iterrows()
    ]
    return df
