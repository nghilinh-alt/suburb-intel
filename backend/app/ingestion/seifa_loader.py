"""ABS SEIFA 2021 loader.

Reads the SA2-level SEIFA indexes Excel file and upserts all four index
scores and deciles onto existing ABSCEntensMetrics rows.

Source file: "Statistical Area Level 2, Indexes, SEIFA 2021.xlsx"
Download:    https://www.abs.gov.au/statistics/people/people-and-communities/
             socio-economic-indexes-areas-seifa-australia/2021/

Table 1 (used here) — SEIFA Summary, one row per SA2:
    col 0  SA2_CODE_2021
    col 1  SA2_NAME
    col 2  IRSD Score    col 3  IRSD Decile
    col 4  IRSAD Score   col 5  IRSAD Decile
    col 6  IER Score     col 7  IER Decile
    col 8  IEO Score     col 9  IEO Decile
    col 10 Usual Resident Population

Usage (CLI):
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.seifa --file "../data/datapacks/SEIFA_2021_SA2.xlsx"
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics

logger = logging.getLogger(__name__)

# Row index of the true header in Table 1 (0-based)
_HEADER_ROW = 5


@dataclass
class SeifaLoadReport:
    updated: int = 0
    skipped_no_row: int = 0
    skipped_no_score: int = 0

    def __str__(self) -> str:
        return (
            f"Updated: {self.updated} | "
            f"Skipped (no census row): {self.skipped_no_row} | "
            f"Skipped (null score): {self.skipped_no_score}"
        )


def load_seifa(
    seifa_file: Path,
    db: Session,
    *,
    year: int = 2021,
) -> SeifaLoadReport:
    """Upsert SEIFA 2021 indexes onto ABSCEntensMetrics rows for the given year.

    Args:
        seifa_file: Path to "Statistical Area Level 2, Indexes, SEIFA 2021.xlsx".
        db:         Synchronous SQLAlchemy session.
        year:       Census year whose metrics rows are updated (default 2021).
    """
    report = SeifaLoadReport()

    df = _load_table1(seifa_file)
    logger.info("Loaded %d SA2 rows from SEIFA Table 1", len(df))

    for _, row in df.iterrows():
        sa2_code = str(int(row["sa2_code"])).zfill(9)

        # Skip rows with no usable score (excluded areas, offshore, etc.)
        if pd.isna(row["irsd_score"]):
            report.skipped_no_score += 1
            continue

        metrics = db.get(ABSCEntensMetrics, (sa2_code, year))
        if metrics is None:
            report.skipped_no_row += 1
            logger.debug("No census row for SA2 %s — skipping", sa2_code)
            continue

        metrics.seifa_irsd_score   = float(row["irsd_score"])
        metrics.seifa_irsd_decile  = _int_or_none(row["irsd_decile"])
        metrics.seifa_irsad_score  = _float_or_none(row["irsad_score"])
        metrics.seifa_irsad_decile = _int_or_none(row["irsad_decile"])
        metrics.seifa_ier_score    = _float_or_none(row["ier_score"])
        metrics.seifa_ier_decile   = _int_or_none(row["ier_decile"])
        metrics.seifa_ieo_score    = _float_or_none(row["ieo_score"])
        metrics.seifa_ieo_decile   = _int_or_none(row["ieo_decile"])
        report.updated += 1

    db.commit()
    return report


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_table1(path: Path) -> pd.DataFrame:
    """Read Table 1 from the SEIFA Excel file and return a clean DataFrame."""
    raw = pd.read_excel(
        path,
        sheet_name="Table 1",
        header=_HEADER_ROW,
        dtype={0: str},   # keep SA2 code as string to preserve leading zeros
        na_values=["-"],
    )
    # Rename positional columns to something readable
    raw.columns = [
        "sa2_code", "sa2_name",
        "irsd_score", "irsd_decile",
        "irsad_score", "irsad_decile",
        "ier_score", "ier_decile",
        "ieo_score", "ieo_decile",
        "population",
    ]
    # Drop any trailing footer rows (non-numeric SA2 codes)
    raw = raw[raw["sa2_code"].str.match(r"^\d{9}$", na=False)].copy()
    return raw


def _float_or_none(val) -> float | None:
    if pd.isna(val) or str(val).strip() in ("-", ""):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _int_or_none(val) -> int | None:
    f = _float_or_none(val)
    return int(f) if f is not None else None
