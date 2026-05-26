"""ABS Census 2021 GCP DataPack loader.

Reads a Census 2021 General Community Profile (GCP) DataPack zip and upserts
SA2Region + ABSCEntensMetrics rows into the configured database.

Supported DataPack format: CSV short-header, SA2 geography.
Download from: https://www.abs.gov.au/census/find-census-data/datapacks

Usage (CLI):
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion path/to/2021_GCP_SA2_for_VIC_short-header.zip
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics, SA2Region

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State code mapping (first digit of SA2 code → short code, full name)
# ---------------------------------------------------------------------------
_STATE_MAP: dict[str, tuple[str, str]] = {
    "1": ("NSW", "New South Wales"),
    "2": ("VIC", "Victoria"),
    "3": ("QLD", "Queensland"),
    "4": ("SA", "South Australia"),
    "5": ("WA", "Western Australia"),
    "6": ("TAS", "Tasmania"),
    "7": ("NT", "Northern Territory"),
    "8": ("ACT", "Australian Capital Territory"),
    "9": ("OT", "Other Territories"),
}

# ---------------------------------------------------------------------------
# Industry bucket mapping (DataPack short column name → scoring bucket)
# ---------------------------------------------------------------------------
# Columns from G53B (P_ persons totals for first 15 industries)
# Columns from G53C (P_ persons totals for last 4 industries + grand total)
_INDUSTRY_COLS_G53B: list[tuple[str, str]] = [
    ("P_AgriForestFish_ToT", "agriculture"),
    ("P_Min_ToT", "services"),          # Mining → services (no dedicated bucket)
    ("P_Mnfg_ToT", "manufacturing"),
    ("P_EGW_WS_ToT", "services"),       # Electricity/Gas/Water → services
    ("P_Cnstn_ToT", "construction"),
    ("P_WTrade_ToT", "retail"),          # Wholesale trade → retail bucket
    ("P_RTrade_ToT", "retail"),
    ("P_AccomFoodS_ToT", "retail"),      # Accommodation/Food → retail
    ("P_TransPostWhse_ToT", "services"),
    ("P_InfoMedTelecom_ToT", "tech"),
    ("P_FinInsurS_ToT", "finance"),
    ("P_RentHirREserv_ToT", "services"),
    ("P_ProScieTechServ_ToT", "tech"),   # Professional/Scientific/Technical → tech
    ("P_AdminSupServ_ToT", "services"),
    ("P_PubAdmiSafety_ToT", "services"),
]

_INDUSTRY_COLS_G53C: list[tuple[str, str]] = [
    ("P_EducTrain_ToT", "education"),
    ("P_HealthCareSocA_ToT", "healthcare"),
    ("P_ArtRecServ_ToT", "services"),
    ("P_OthServ_ToT", "services"),
]

_INDUSTRY_TOTAL_COL = "P_ToT_ToT"  # Grand total from G53C


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class LoadReport:
    regions_inserted: int = 0
    regions_updated: int = 0
    metrics_inserted: int = 0
    metrics_updated: int = 0
    rows_skipped: int = 0
    skipped_reasons: list[str] = field(default_factory=list)

    def __str__(self) -> str:
        return (
            f"Regions: {self.regions_inserted} inserted, {self.regions_updated} updated | "
            f"Metrics: {self.metrics_inserted} inserted, {self.metrics_updated} updated | "
            f"Skipped: {self.rows_skipped}"
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_datapack(
    datapack_zip: Path,
    db: Session,
    *,
    year: int = 2021,
    states: Optional[list[str]] = None,
    truncate_first: bool = False,
) -> LoadReport:
    """Read a Census 2021 GCP DataPack zip and upsert SA2Region + ABSCEntensMetrics.

    Args:
        datapack_zip: Path to the short-header SA2 GCP DataPack zip.
        db: Synchronous SQLAlchemy session.
        year: Census year (default 2021).
        states: Optional list of state short codes to restrict loading (e.g. ["VIC"]).
                None means load all states in the DataPack.
        truncate_first: If True, delete existing rows for the given year before loading.
    Returns:
        LoadReport with insert/update/skip counts.
    """
    report = LoadReport()

    with zipfile.ZipFile(datapack_zip) as zf:
        names = zf.namelist()

        # ----------------------------------------------------------------
        # Build geography lookups from the Metadata Excel
        # ----------------------------------------------------------------
        geog_df = _load_geography(zf, names)
        sa2_lookup: dict[str, dict] = _build_sa2_lookup(geog_df)
        sa3_names: dict[str, str] = dict(
            zip(
                geog_df.loc[geog_df["ASGS_Structure"] == "SA3", "Census_Code_2021"],
                geog_df.loc[geog_df["ASGS_Structure"] == "SA3", "Census_Name_2021"],
            )
        )
        sa4_names: dict[str, str] = dict(
            zip(
                geog_df.loc[geog_df["ASGS_Structure"] == "SA4", "Census_Code_2021"],
                geog_df.loc[geog_df["ASGS_Structure"] == "SA4", "Census_Name_2021"],
            )
        )

        # ----------------------------------------------------------------
        # Load the four key CSVs
        # ----------------------------------------------------------------
        g01 = _read_csv(zf, names, "G01")
        g02 = _read_csv(zf, names, "G02")
        g37 = _read_csv(zf, names, "G37")
        g53b = _read_csv(zf, names, "G53B")
        g53c = _read_csv(zf, names, "G53C")

    # Build a combined industry frame (merge G53B + G53C on SA2 code)
    industry_cols_b = ["SA2_CODE_2021"] + [c for c, _ in _INDUSTRY_COLS_G53B if c in g53b.columns]
    industry_cols_c = ["SA2_CODE_2021"] + [c for c, _ in _INDUSTRY_COLS_G53C if c in g53c.columns] + [_INDUSTRY_TOTAL_COL]
    g53 = g53b[industry_cols_b].merge(g53c[industry_cols_c], on="SA2_CODE_2021", how="outer")

    # Work from G01 SA2 code list as the canonical universe
    all_codes = set(g01["SA2_CODE_2021"].dropna().astype(str))

    if truncate_first:
        db.query(ABSCEntensMetrics).filter(ABSCEntensMetrics.year == year).delete()
        db.commit()

    for sa2_code in sorted(all_codes):
        state_digit = sa2_code[0] if sa2_code else ""
        state_short, _state_long = _STATE_MAP.get(state_digit, ("XX", "Unknown"))

        if states is not None and state_short not in states:
            continue

        info = sa2_lookup.get(sa2_code, {})
        sa2_name = info.get("name", sa2_code)
        area_sqkm = info.get("area_sqkm")

        sa3_code = sa2_code[:5]
        sa4_code = sa2_code[:3]
        sa3_name = sa3_names.get(sa3_code)
        sa4_name = sa4_names.get(sa4_code)

        # ----------------------------------------------------------------
        # Upsert SA2Region
        # ----------------------------------------------------------------
        existing_region = db.get(SA2Region, sa2_code)
        region_obj = SA2Region(
            sa2_code=sa2_code,
            sa2_name=sa2_name,
            state=state_short,
            sa3_code=sa3_code,
            sa3_name=sa3_name,
            sa4_code=sa4_code,
            sa4_name=sa4_name,
            gcc_code=None,
            gcc_name=None,
            area_sqkm=area_sqkm,
        )
        if existing_region is None:
            db.add(region_obj)
            report.regions_inserted += 1
        else:
            db.merge(region_obj)
            report.regions_updated += 1

        # ----------------------------------------------------------------
        # Build census metrics
        # ----------------------------------------------------------------
        try:
            metrics = _build_metrics(sa2_code, year, g01, g02, g37, g53)
        except Exception as exc:
            report.rows_skipped += 1
            report.skipped_reasons.append(f"{sa2_code}: {exc}")
            logger.warning("Skipping metrics for %s: %s", sa2_code, exc)
            continue

        existing_metrics = db.get(ABSCEntensMetrics, (sa2_code, year))
        if existing_metrics is None:
            db.add(metrics)
            report.metrics_inserted += 1
        else:
            db.merge(metrics)
            report.metrics_updated += 1

    db.commit()
    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_geography(zf: zipfile.ZipFile, names: list[str]) -> pd.DataFrame:
    """Read the SA2/SA3/SA4 geography description Excel from the Metadata folder."""
    excel_name = next(
        (n for n in names if "geog_desc" in n.lower() and n.endswith(".xlsx")),
        None,
    )
    if excel_name is None:
        raise FileNotFoundError("Could not find geog_desc Excel in DataPack Metadata/")
    with zf.open(excel_name) as f:
        df = pd.read_excel(io.BytesIO(f.read()), sheet_name=0, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    return df


def _build_sa2_lookup(geog_df: pd.DataFrame) -> dict[str, dict]:
    sa2_rows = geog_df[geog_df["ASGS_Structure"] == "SA2"]
    result: dict[str, dict] = {}
    for _, row in sa2_rows.iterrows():
        code = str(row["Census_Code_2021"]).strip()
        area_raw = row.get("Area sqkm")
        try:
            area = float(area_raw) if pd.notna(area_raw) else None
        except (ValueError, TypeError):
            area = None
        result[code] = {"name": row["Census_Name_2021"], "area_sqkm": area}
    return result


def _read_csv(zf: zipfile.ZipFile, names: list[str], table_id: str) -> pd.DataFrame:
    """Find and read a Census table CSV from the zip by table ID (e.g. 'G01')."""
    pattern = f"_{table_id}_"
    csv_name = next(
        (n for n in names if pattern in n and n.endswith(".csv") and "SA2" in n),
        None,
    )
    if csv_name is None:
        raise FileNotFoundError(f"Could not find table {table_id} in DataPack")
    with zf.open(csv_name) as f:
        return pd.read_csv(f, dtype={"SA2_CODE_2021": str})


def _scalar(df: pd.DataFrame, sa2_code: str, col: str) -> float | None:
    """Extract a single numeric value from a DataFrame for a given SA2 code."""
    rows = df.loc[df["SA2_CODE_2021"] == sa2_code, col]
    if rows.empty:
        return None
    val = rows.iloc[0]
    if pd.isna(val):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _compute_young_pct(g01: pd.DataFrame, sa2_code: str) -> float | None:
    """% of population aged 15–34, capped at 100."""
    total = _scalar(g01, sa2_code, "Tot_P_P")
    if not total:
        return None
    young = sum(
        _scalar(g01, sa2_code, col) or 0.0
        for col in ("Age_15_19_yr_P", "Age_20_24_yr_P", "Age_25_34_yr_P")
    )
    return min(young / total * 100.0, 100.0)


def _compute_renters_pct(g37: pd.DataFrame, sa2_code: str) -> float | None:
    """% of occupied dwellings that are rented."""
    total = _scalar(g37, sa2_code, "Total_Total")
    if not total:
        return None
    rented = _scalar(g37, sa2_code, "R_Tot_Total") or 0.0
    return min(rented / total * 100.0, 100.0)


def _compute_owners_pct(g37: pd.DataFrame, sa2_code: str) -> float | None:
    """% of occupied dwellings that are owned (outright or with mortgage)."""
    total = _scalar(g37, sa2_code, "Total_Total")
    if not total:
        return None
    owned = (
        (_scalar(g37, sa2_code, "O_OR_Total") or 0.0)
        + (_scalar(g37, sa2_code, "O_MTG_Total") or 0.0)
    )
    return min(owned / total * 100.0, 100.0)


def _compute_industry_profile(g53: pd.DataFrame, sa2_code: str) -> dict[str, float]:
    """ANZSIC industry proportions keyed by scoring bucket, summing to ≤ 1.0."""
    total = _scalar(g53, sa2_code, _INDUSTRY_TOTAL_COL)
    if not total or total <= 0:
        return {}

    buckets: dict[str, float] = {}
    all_col_mappings = _INDUSTRY_COLS_G53B + _INDUSTRY_COLS_G53C
    for col, bucket in all_col_mappings:
        if col not in g53.columns:
            continue
        count = _scalar(g53, sa2_code, col) or 0.0
        buckets[bucket] = buckets.get(bucket, 0.0) + count / total

    return {k: round(v, 4) for k, v in buckets.items()}


def _build_metrics(
    sa2_code: str,
    year: int,
    g01: pd.DataFrame,
    g02: pd.DataFrame,
    g37: pd.DataFrame,
    g53: pd.DataFrame,
) -> ABSCEntensMetrics:
    """Assemble an ABSCEntensMetrics row from the four source DataFrames."""
    population_raw = _scalar(g01, sa2_code, "Tot_P_P")
    population = int(population_raw) if population_raw is not None else None

    median_age = _scalar(g02, sa2_code, "Median_age_persons")

    # Weekly personal income × 52 → annual
    weekly_income = _scalar(g02, sa2_code, "Median_tot_prsnl_inc_weekly")
    median_income = int(weekly_income * 52) if weekly_income is not None else None

    return ABSCEntensMetrics(
        sa2_code=sa2_code,
        year=year,
        population=population,
        median_income=median_income,
        median_age=median_age,
        renters_pct=_compute_renters_pct(g37, sa2_code),
        owners_pct=_compute_owners_pct(g37, sa2_code),
        young_population_pct=_compute_young_pct(g01, sa2_code),
        industry_profile=_compute_industry_profile(g53, sa2_code),
        pop_growth_5yr=None,  # Requires 2016 DataPack; populated by a second pass
    )
