"""School ICSEA loader.

Reads the ACARA School Profile Excel file (ICSEA scores) and upserts
avg_school_icsea and num_schools onto existing ABSCEntensMetrics rows.

Join path:
    school postcode  →  ABS POA_2021_AUST.xlsx  →  MB_CODE
    MB_CODE          →  ABS MB_2021_AUST.xlsx   →  SA2_CODE_2021

For each SA2, computes enrolment-weighted average ICSEA across all schools
whose postcode's dominant SA2 is that SA2.

Usage (CLI):
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.school_icsea \\
        --icsea  ../data/datapacks/"School ICSEA Scores 2025.xlsx" \\
        --mb     ../data/datapacks/MB_2021_AUST.xlsx \\
        --poa    ../data/datapacks/POA_2021_AUST.xlsx
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics

logger = logging.getLogger(__name__)


@dataclass
class IcseaLoadReport:
    sa2_updated: int = 0
    sa2_skipped_no_row: int = 0
    schools_matched: int = 0
    schools_unmatched: int = 0

    def __str__(self) -> str:
        return (
            f"SA2 rows updated: {self.sa2_updated} | "
            f"Skipped (no census row): {self.sa2_skipped_no_row} | "
            f"Schools matched: {self.schools_matched} | "
            f"Schools unmatched (postcode not in ABS): {self.schools_unmatched}"
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def load_school_icsea(
    icsea_file: Path,
    mb_file: Path,
    poa_file: Path,
    db: Session,
    *,
    year: int = 2021,
) -> IcseaLoadReport:
    """Aggregate school ICSEA scores to SA2 and upsert onto census metrics rows.

    Args:
        icsea_file: Path to the ACARA 'School ICSEA Scores 2025.xlsx'.
        mb_file:    Path to ABS MB_2021_AUST.xlsx (mesh block → SA2 mapping).
        poa_file:   Path to ABS POA_2021_AUST.xlsx (mesh block → POA mapping).
        db:         Synchronous SQLAlchemy session.
        year:       Census year whose metrics rows are updated (default 2021).
    """
    report = IcseaLoadReport()

    logger.info("Building postcode → SA2 lookup from mesh block files …")
    postcode_to_sa2 = _build_postcode_sa2_lookup(mb_file, poa_file)
    logger.info("Lookup covers %d postcodes", len(postcode_to_sa2))

    logger.info("Loading ICSEA school data …")
    schools = _load_schools(icsea_file)

    # Map each school to its SA2 via postcode
    schools["sa2_code"] = schools["postcode_str"].map(postcode_to_sa2)

    matched = schools["sa2_code"].notna().sum()
    report.schools_matched = int(matched)
    report.schools_unmatched = len(schools) - matched

    # Aggregate per SA2: enrolment-weighted ICSEA average
    valid = schools.dropna(subset=["sa2_code", "icsea", "enrolments"])
    sa2_stats = (
        valid.groupby("sa2_code")
        .apply(_weighted_icsea_agg, include_groups=False)
        .reset_index()
    )

    logger.info("Upserting ICSEA stats for %d SA2 rows …", len(sa2_stats))
    for _, row in sa2_stats.iterrows():
        sa2_code = row["sa2_code"]
        metrics = db.get(ABSCEntensMetrics, (sa2_code, year))
        if metrics is None:
            report.sa2_skipped_no_row += 1
            logger.debug("No census row for SA2 %s (year %d) — skipping", sa2_code, year)
            continue
        metrics.avg_school_icsea = round(float(row["avg_icsea"]), 1)
        metrics.num_schools = int(row["num_schools"])
        report.sa2_updated += 1

    db.commit()
    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_postcode_sa2_lookup(mb_file: Path, poa_file: Path) -> dict[str, str]:
    """Return {postcode_str: sa2_code} mapping dominant SA2 for each postcode.

    Strategy: join MB→SA2 and MB→POA on mesh block code; for each postcode
    pick the SA2 that contributes the most mesh blocks.
    """
    logger.info("Reading MB allocation file …")
    mb = pd.read_excel(
        mb_file,
        usecols=["MB_CODE_2021", "SA2_CODE_2021"],
        dtype=str,
    )
    logger.info("Reading POA allocation file …")
    poa = pd.read_excel(
        poa_file,
        usecols=["MB_CODE_2021", "POA_CODE_2021"],
        dtype=str,
    )

    merged = mb.merge(poa, on="MB_CODE_2021", how="inner")

    # Count mesh blocks per (POA, SA2) pair, pick the SA2 with the most
    counts = (
        merged.groupby(["POA_CODE_2021", "SA2_CODE_2021"])
        .size()
        .reset_index(name="mb_count")
    )
    dominant = (
        counts.sort_values("mb_count", ascending=False)
        .drop_duplicates("POA_CODE_2021")
    )
    return dict(zip(dominant["POA_CODE_2021"], dominant["SA2_CODE_2021"]))


def _load_schools(icsea_file: Path) -> pd.DataFrame:
    """Load the relevant columns from the ICSEA Excel file."""
    df = pd.read_excel(
        icsea_file,
        sheet_name="SchoolProfile 2025",
        usecols=["Postcode", "ICSEA", "Total Enrolments"],
        dtype={"Postcode": "Int64"},
    )
    df = df.rename(columns={
        "ICSEA": "icsea",
        "Total Enrolments": "enrolments",
    })
    # Zero-pad postcode to 4 chars to match ABS POA codes (e.g. ACT 800 → "0800")
    df["postcode_str"] = df["Postcode"].apply(
        lambda p: str(int(p)).zfill(4) if pd.notna(p) else None
    )
    return df


def _weighted_icsea_agg(group: pd.DataFrame) -> pd.Series:
    """Enrolment-weighted average ICSEA and school count for one SA2 group."""
    total_enrolments = group["enrolments"].sum()
    if total_enrolments == 0:
        avg = group["icsea"].mean()
    else:
        avg = (group["icsea"] * group["enrolments"]).sum() / total_enrolments
    return pd.Series({"avg_icsea": avg, "num_schools": len(group)})
