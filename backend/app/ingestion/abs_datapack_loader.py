"""ABS Census 2021 GCP DataPack loader.

Reads a Census 2021 General Community Profile (GCP) DataPack zip and upserts
SA2Region + ABSCEntensMetrics rows into the configured database.

Supported DataPack format: CSV short-header, SA2 geography.
Download from: https://www.abs.gov.au/census/find-census-data/datapacks

Tables consumed (all others are ignored):
    Demographics        : G02, G09 (parts F-H, Persons only), G29, G37
    Property            : G35, G36, G38, G40
    Growth/Gentrification: G44, G45, G49B, G60B
    Lifestyle           : G34, G62
    Risk                : G37 (shared), G41, G46B

Usage (CLI):
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion path/to/2021_GCP_SA2_for_VIC_short-header.zip
"""

from __future__ import annotations

import io
import logging
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics, SA2Region

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State code mapping  (first digit of SA2 code → short code, full name)
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
        # Geography lookups
        # ----------------------------------------------------------------
        geog_df = _load_geography(zf, names)
        sa2_lookup = _build_sa2_lookup(geog_df)
        sa3_names: dict[str, str] = dict(zip(
            geog_df.loc[geog_df["ASGS_Structure"] == "SA3", "Census_Code_2021"],
            geog_df.loc[geog_df["ASGS_Structure"] == "SA3", "Census_Name_2021"],
        ))
        sa4_names: dict[str, str] = dict(zip(
            geog_df.loc[geog_df["ASGS_Structure"] == "SA4", "Census_Code_2021"],
            geog_df.loc[geog_df["ASGS_Structure"] == "SA4", "Census_Name_2021"],
        ))

        # ----------------------------------------------------------------
        # Load target tables
        # ----------------------------------------------------------------
        # Demographics
        g02  = _read_csv(zf, names, "G02")
        g09p = _read_csv_parts(zf, names, r"_G09[FGH]_")  # Persons-only parts (F–H)
        g29  = _read_csv(zf, names, "G29")
        g37  = _read_csv(zf, names, "G37")

        # Property
        g35  = _read_csv(zf, names, "G35")
        g36  = _read_csv(zf, names, "G36")
        g38  = _read_csv(zf, names, "G38")
        g40  = _read_csv(zf, names, "G40")

        # Growth / Gentrification
        g44  = _read_csv(zf, names, "G44")
        g45  = _read_csv(zf, names, "G45")
        g49b = _read_csv(zf, names, "G49B")
        g60b = _read_csv_optional(zf, names, "G60B")

        # Lifestyle
        g34  = _read_csv(zf, names, "G34")
        g62  = _read_csv(zf, names, "G62")

        # Risk  (G37 already loaded above)
        g41  = _read_csv(zf, names, "G41")
        g46b = _read_csv(zf, names, "G46B")

    # Canonical SA2 universe: G44 covers all usual-resident persons (1 yr+)
    all_codes = set(g44["SA2_CODE_2021"].dropna().astype(str))

    if truncate_first:
        db.query(ABSCEntensMetrics).filter(ABSCEntensMetrics.year == year).delete()
        db.commit()

    for sa2_code in sorted(all_codes):
        state_digit = sa2_code[0] if sa2_code else ""
        state_short, _ = _STATE_MAP.get(state_digit, ("XX", "Unknown"))

        if states is not None and state_short not in states:
            continue

        info = sa2_lookup.get(sa2_code, {})
        sa2_name = info.get("name", sa2_code)
        area_sqkm = info.get("area_sqkm")
        sa3_code = sa2_code[:5]
        sa4_code = sa2_code[:3]

        # ----------------------------------------------------------------
        # Upsert SA2Region
        # ----------------------------------------------------------------
        existing_region = db.get(SA2Region, sa2_code)
        region_obj = SA2Region(
            sa2_code=sa2_code,
            sa2_name=sa2_name,
            state=state_short,
            sa3_code=sa3_code,
            sa3_name=sa3_names.get(sa3_code),
            sa4_code=sa4_code,
            sa4_name=sa4_names.get(sa4_code),
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
        # Build and upsert census metrics
        # ----------------------------------------------------------------
        try:
            metrics = _build_metrics(
                sa2_code, year,
                g02=g02, g09p=g09p, g29=g29, g34=g34,
                g35=g35, g36=g36, g37=g37, g38=g38,
                g40=g40, g41=g41, g44=g44, g45=g45,
                g46b=g46b, g49b=g49b, g60b=g60b, g62=g62,
            )
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
# Internal helpers — I/O
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
    """Find and read a Census table CSV (exact table_id match, e.g. 'G02', 'G46B')."""
    pattern = f"_{table_id}_"
    csv_name = next(
        (n for n in names if pattern in n and n.endswith(".csv") and "SA2" in n),
        None,
    )
    if csv_name is None:
        raise FileNotFoundError(f"Could not find table {table_id} in DataPack")
    with zf.open(csv_name) as f:
        return pd.read_csv(f, dtype={"SA2_CODE_2021": str})


def _read_csv_optional(
    zf: zipfile.ZipFile, names: list[str], table_id: str
) -> pd.DataFrame | None:
    """Like _read_csv but returns None (and logs a warning) if the table is absent."""
    try:
        return _read_csv(zf, names, table_id)
    except FileNotFoundError:
        logger.warning(
            "Optional table %s not found in DataPack — related metrics will be NULL",
            table_id,
        )
        return None


def _read_csv_parts(
    zf: zipfile.ZipFile, names: list[str], pattern: str
) -> pd.DataFrame | None:
    """Load and column-wise merge all CSV parts whose path matches the regex pattern."""
    matches = sorted(
        n for n in names if re.search(pattern, n) and n.endswith(".csv") and "SA2" in n
    )
    if not matches:
        logger.warning(
            "No CSV parts matched pattern %r — related metrics will be NULL", pattern
        )
        return None
    frames = []
    for csv_name in matches:
        with zf.open(csv_name) as f:
            frames.append(pd.read_csv(f, dtype={"SA2_CODE_2021": str}))
    result = frames[0]
    for df in frames[1:]:
        new_cols = ["SA2_CODE_2021"] + [c for c in df.columns if c not in result.columns]
        result = result.merge(df[new_cols], on="SA2_CODE_2021", how="outer")
    return result


# ---------------------------------------------------------------------------
# Internal helpers — scalar extraction
# ---------------------------------------------------------------------------

def _scalar(df: pd.DataFrame | None, sa2_code: str, col: str) -> float | None:
    """Extract a single numeric value; returns None if df is None, col is missing, or value is NaN."""
    if df is None or col not in df.columns:
        return None
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


def _pct(numerator: float | None, denominator: float | None, *, cap: float = 100.0) -> float | None:
    """Safe percentage: (numerator / denominator) × 100, capped at cap. Returns None on bad input."""
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return min(numerator / denominator * 100.0, cap)


# ---------------------------------------------------------------------------
# Per-metric computation helpers
# ---------------------------------------------------------------------------

def _compute_overseas_born_pct(g09p: pd.DataFrame | None, sa2_code: str) -> float | None:
    """% of population born overseas (G09H P_Tot_Tot minus Australia-born and not-stated)."""
    if g09p is None:
        return None
    total      = _scalar(g09p, sa2_code, "P_Tot_Tot")
    australia  = _scalar(g09p, sa2_code, "P_Australia_Tot") or 0.0
    not_stated = _scalar(g09p, sa2_code, "P_COB_NS_Tot")    or 0.0
    if total is None or total <= 0:
        return None
    return _pct(total - australia - not_stated, total)


def _compute_families_with_children_pct(g29: pd.DataFrame, sa2_code: str) -> float | None:
    """% of family units that include at least one child under 15."""
    cf_kids  = _scalar(g29, sa2_code, "CF_ChU15_a_Total_F")
    opf_kids = _scalar(g29, sa2_code, "OPF_ChU15_a_Total_F")
    total    = _scalar(g29, sa2_code, "Total_F")
    if cf_kids is None and opf_kids is None:
        return None
    return _pct((cf_kids or 0.0) + (opf_kids or 0.0), total)


def _compute_zero_car_dwellings_pct(g34: pd.DataFrame, sa2_code: str) -> float | None:
    """% of dwellings with no registered motor vehicles."""
    return _pct(
        _scalar(g34, sa2_code, "Num_MVs_per_dweling_0_MVs"),
        _scalar(g34, sa2_code, "Total_dwelings"),
    )


def _compute_avg_household_size(g35: pd.DataFrame, sa2_code: str) -> float | None:
    """Weighted average persons per dwelling (6+ band counted as 6)."""
    total = _scalar(g35, sa2_code, "Total_Total")
    if not total:
        return None
    persons_sum = sum(
        (_scalar(g35, sa2_code, f"Num_Psns_UR_{n}_Total") or 0.0) * n
        for n in range(1, 6)
    ) + (_scalar(g35, sa2_code, "Num_Psns_UR_6mo_Total") or 0.0) * 6
    return round(persons_sum / total, 2)


def _compute_dwelling_structure(
    g36: pd.DataFrame, sa2_code: str
) -> tuple[float | None, float | None]:
    """(separate_house_pct, flat_apartment_pct) as % of occupied private dwellings."""
    total = _scalar(g36, sa2_code, "OPDs_Tot_OPDs_Dwellings")
    return (
        _pct(_scalar(g36, sa2_code, "OPDs_Separate_house_Dwellings"), total),
        _pct(_scalar(g36, sa2_code, "OPDs_Flt_apart_Tot_Dwgs"), total),
    )


def _compute_tenure(
    g37: pd.DataFrame, sa2_code: str
) -> tuple[float | None, float | None, float | None]:
    """(renters_pct, owners_pct, social_housing_pct) from G37."""
    total   = _scalar(g37, sa2_code, "Total_Total")
    renters = _scalar(g37, sa2_code, "R_Tot_Total") or 0.0
    owned   = (
        (_scalar(g37, sa2_code, "O_OR_Total")  or 0.0)
        + (_scalar(g37, sa2_code, "O_MTG_Total") or 0.0)
    )
    social  = (
        (_scalar(g37, sa2_code, "R_ST_h_auth_Total") or 0.0)
        + (_scalar(g37, sa2_code, "R_Com_Hp_Total")  or 0.0)
    )
    return _pct(renters, total), _pct(owned, total), _pct(social, total)


def _compute_high_mortgage_stress_pct(g38: pd.DataFrame, sa2_code: str) -> float | None:
    """% of mortgaged dwellings paying ≥ $3 000/month."""
    high = (
        (_scalar(g38, sa2_code, "M_3000_3999_Tot") or 0.0)
        + (_scalar(g38, sa2_code, "M_4000_over_Tot") or 0.0)
    )
    return _pct(high, _scalar(g38, sa2_code, "Tot_Tot"))


def _compute_high_rent_stress_pct(g40: pd.DataFrame, sa2_code: str) -> float | None:
    """% of rented dwellings paying ≥ $650/week."""
    high_cols = ["R_650_749_Tot", "R_750_849_Tot", "R_850_949_Tot", "R_950_over_Tot"]
    high = sum(_scalar(g40, sa2_code, c) or 0.0 for c in high_cols)
    return _pct(high, _scalar(g40, sa2_code, "Tot_Tot"))


def _compute_one_bedroom_pct(g41: pd.DataFrame, sa2_code: str) -> float | None:
    """% of dwellings with exactly 1 bedroom."""
    return _pct(
        _scalar(g41, sa2_code, "Total_NofB_1"),
        _scalar(g41, sa2_code, "Total_Total"),
    )


def _compute_flat_storey_pcts(
    g41: pd.DataFrame, sa2_code: str
) -> tuple[float | None, float | None, float | None]:
    """(low_rise_pct, mid_rise_pct, high_rise_pct) as % of total dwellings.

    low_rise  = flats in 1-2 storey blocks
    mid_rise  = flats in 3-8 storey blocks (3-storey + 4-8 storey combined)
    high_rise = flats in 9+ storey blocks
    """
    total = _scalar(g41, sa2_code, "Total_Total")
    low   = _scalar(g41, sa2_code, "Flt_at_In_1or2_s_b_Total")
    mid3  = _scalar(g41, sa2_code, "Flt_apt_In_3_st_bl_Total")
    mid48 = _scalar(g41, sa2_code, "Flt_apt_4to8_s_b_Total")
    high  = _scalar(g41, sa2_code, "Flt_apt_9_or_m_s_b_Total")
    mid   = (mid3 or 0) + (mid48 or 0)
    return (
        _pct(low, total),
        _pct(mid, total) if (mid3 is not None or mid48 is not None) else None,
        _pct(high, total),
    )


def _compute_moved_in_1yr_pct(g44: pd.DataFrame, sa2_code: str) -> float | None:
    """% who lived in a different SA2 or overseas one year before census night."""
    from_diff_sa2 = _scalar(g44, sa2_code, "Dif_Us_ad_1_ago_Dif_SA2_Tot_P") or 0.0
    from_os       = _scalar(g44, sa2_code, "Difnt_Usl_add_1_yr_ago_OS_P")   or 0.0
    return _pct(from_diff_sa2 + from_os, _scalar(g44, sa2_code, "Tot_P"))


def _compute_moved_in_5yr_pct(g45: pd.DataFrame, sa2_code: str) -> float | None:
    """% who lived in a different SA2 or overseas five years before census night."""
    from_diff_sa2 = _scalar(g45, sa2_code, "Dif_Us_ad_5_ago_Dif_SA2_Tot_P") or 0.0
    from_os       = _scalar(g45, sa2_code, "Difnt_Usl_add_5_yr_ago_OS_P")   or 0.0
    return _pct(from_diff_sa2 + from_os, _scalar(g45, sa2_code, "Tot_P"))


def _compute_unemployment_pct(g46b: pd.DataFrame, sa2_code: str) -> float | None:
    """Unemployment rate (unemployed / total labour force)."""
    return _pct(
        _scalar(g46b, sa2_code, "P_Tot_Unemp_Tot"),
        _scalar(g46b, sa2_code, "P_Tot_LF_Tot"),
    )


def _compute_uni_degree_pct(g49b: pd.DataFrame, sa2_code: str) -> float | None:
    """% of population with a bachelor degree or higher (postgrad + grad dip + bach)."""
    pgrad    = _scalar(g49b, sa2_code, "P_PGrad_Deg_Total")              or 0.0
    grad_dip = _scalar(g49b, sa2_code, "P_GradDip_and_GradCert_Total")   or 0.0
    bach     = _scalar(g49b, sa2_code, "P_BachDeg_Total")                or 0.0
    return _pct(pgrad + grad_dip + bach, _scalar(g49b, sa2_code, "P_Tot_Total"))


def _compute_professionals_managers_pct(
    g60b: pd.DataFrame | None, sa2_code: str
) -> float | None:
    """% of employed persons who are managers or professionals."""
    if g60b is None:
        return None
    managers      = _scalar(g60b, sa2_code, "P_Tot_Managers")      or 0.0
    professionals = _scalar(g60b, sa2_code, "P_Tot_Professionals") or 0.0
    return _pct(managers + professionals, _scalar(g60b, sa2_code, "P_Tot_Tot"))


def _compute_commute(
    g62: pd.DataFrame, sa2_code: str
) -> tuple[float | None, float | None, float | None]:
    """(pt_commute_pct, car_commute_pct, work_from_home_pct) from single-mode travel."""
    total    = _scalar(g62, sa2_code, "Tot_P")
    pt_cols  = [
        "One_method_Train_P", "One_method_Bus_P",
        "One_method_Ferry_P", "One_met_Tram_or_lt_rail_P",
    ]
    car_cols = ["One_method_Car_as_driver_P", "One_method_Car_as_passenger_P"]
    pt  = sum(_scalar(g62, sa2_code, c) or 0.0 for c in pt_cols)
    car = sum(_scalar(g62, sa2_code, c) or 0.0 for c in car_cols)
    wfh = _scalar(g62, sa2_code, "Worked_home_P") or 0.0
    return _pct(pt, total), _pct(car, total), _pct(wfh, total)


# ---------------------------------------------------------------------------
# Main row builder
# ---------------------------------------------------------------------------

def _build_metrics(
    sa2_code: str,
    year: int,
    *,
    g02: pd.DataFrame,
    g09p: pd.DataFrame | None,
    g29: pd.DataFrame,
    g34: pd.DataFrame,
    g35: pd.DataFrame,
    g36: pd.DataFrame,
    g37: pd.DataFrame,
    g38: pd.DataFrame,
    g40: pd.DataFrame,
    g41: pd.DataFrame,
    g44: pd.DataFrame,
    g45: pd.DataFrame,
    g46b: pd.DataFrame,
    g49b: pd.DataFrame,
    g60b: pd.DataFrame | None,
    g62: pd.DataFrame,
) -> ABSCEntensMetrics:
    """Assemble an ABSCEntensMetrics row from the target DataFrames."""

    # Population: G44 Tot_P ≈ total usual-resident population
    population_raw = _scalar(g44, sa2_code, "Tot_P")
    population = int(population_raw) if population_raw is not None else None

    # G02 — medians
    median_age             = _scalar(g02, sa2_code, "Median_age_persons")
    weekly_income          = _scalar(g02, sa2_code, "Median_tot_prsnl_inc_weekly")
    median_income          = int(weekly_income * 52) if weekly_income is not None else None
    median_mortgage_monthly = _scalar(g02, sa2_code, "Median_mortgage_repay_monthly")
    median_rent_weekly     = _scalar(g02, sa2_code, "Median_rent_weekly")

    # G09 — overseas born
    overseas_born_pct = _compute_overseas_born_pct(g09p, sa2_code)

    # G29 — family composition
    families_with_children_pct = _compute_families_with_children_pct(g29, sa2_code)

    # G34 — car ownership
    zero_car_dwellings_pct = _compute_zero_car_dwellings_pct(g34, sa2_code)

    # G35 — household size
    avg_household_size = _compute_avg_household_size(g35, sa2_code)

    # G36 — dwelling structure
    separate_house_pct, flat_apartment_pct = _compute_dwelling_structure(g36, sa2_code)

    # G37 — tenure
    renters_pct, owners_pct, social_housing_pct = _compute_tenure(g37, sa2_code)

    # G38 — mortgage stress
    high_mortgage_stress_pct = _compute_high_mortgage_stress_pct(g38, sa2_code)

    # G40 — rent stress
    high_rent_stress_pct = _compute_high_rent_stress_pct(g40, sa2_code)

    # G41 — bedrooms + storey breakdown
    one_bedroom_pct = _compute_one_bedroom_pct(g41, sa2_code)
    flat_low_rise_pct, flat_mid_rise_pct, flat_high_rise_pct = _compute_flat_storey_pcts(g41, sa2_code)

    # G44 / G45 — residential mobility
    moved_in_1yr_pct = _compute_moved_in_1yr_pct(g44, sa2_code)
    moved_in_5yr_pct = _compute_moved_in_5yr_pct(g45, sa2_code)

    # G46B — labour force
    unemployment_pct = _compute_unemployment_pct(g46b, sa2_code)

    # G49B — education
    uni_degree_pct = _compute_uni_degree_pct(g49b, sa2_code)

    # G60B — occupation (optional table)
    professionals_managers_pct = _compute_professionals_managers_pct(g60b, sa2_code)

    # G62 — commute
    pt_commute_pct, car_commute_pct, work_from_home_pct = _compute_commute(g62, sa2_code)

    return ABSCEntensMetrics(
        sa2_code=sa2_code,
        year=year,
        # Demographics
        population=population,
        median_age=median_age,
        median_income=median_income,
        median_mortgage_monthly=median_mortgage_monthly,
        median_rent_weekly=median_rent_weekly,
        overseas_born_pct=overseas_born_pct,
        families_with_children_pct=families_with_children_pct,
        renters_pct=renters_pct,
        owners_pct=owners_pct,
        social_housing_pct=social_housing_pct,
        # Property
        avg_household_size=avg_household_size,
        separate_house_pct=separate_house_pct,
        flat_apartment_pct=flat_apartment_pct,
        flat_low_rise_pct=flat_low_rise_pct,
        flat_mid_rise_pct=flat_mid_rise_pct,
        flat_high_rise_pct=flat_high_rise_pct,
        high_mortgage_stress_pct=high_mortgage_stress_pct,
        high_rent_stress_pct=high_rent_stress_pct,
        # Growth / Gentrification
        moved_in_1yr_pct=moved_in_1yr_pct,
        moved_in_5yr_pct=moved_in_5yr_pct,
        uni_degree_pct=uni_degree_pct,
        professionals_managers_pct=professionals_managers_pct,
        # Lifestyle
        zero_car_dwellings_pct=zero_car_dwellings_pct,
        pt_commute_pct=pt_commute_pct,
        car_commute_pct=car_commute_pct,
        work_from_home_pct=work_from_home_pct,
        # Risk
        one_bedroom_pct=one_bedroom_pct,
        unemployment_pct=unemployment_pct,
        # Legacy fields — retained in schema but no longer computed here
        industry_profile=None,
        pop_growth_5yr=None,
        young_population_pct=None,
    )
