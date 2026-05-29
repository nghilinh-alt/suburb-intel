"""ABS Building Approvals loader.

Reads the ABS "Building Approvals by Statistical Area (SA2)" CSV and stores
the total new residential dwellings approved per SA2 for the most recent
financial year.

Data source
───────────
ABS Building Approvals, Australia — SA2 small area data.
Latest release: https://www.abs.gov.au/statistics/industry/building-and-construction/building-approvals-australia/latest-release
File: Statistical Area 2_Australia_<year>.zip  (free, no login)

Column written to abs_census_metrics
─────────────────────────────────────
building_approvals_1yr  — total new residential dwellings approved in the
                           financial year covered by the downloaded file.

Filters applied to raw data
───────────────────────────
  type_work  = 1  → New (excludes alterations/additions)
  type_bld   = 100 → Total Residential (houses + multi-res)
  own_sector = 9  → All sectors (private + public)
  sa2_code length = 9 → Actual SA2 rows only (excludes state/national rollups)

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.building_approvals --zip "../data/building_approvals/sa2_2024-25.zip"
"""

from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics

logger = logging.getLogger(__name__)

# CSV filter values
_TYPE_WORK_NEW      = "1"    # New buildings only
_TYPE_BLD_TOTAL_RES = "100"  # Total Residential
_OWN_SECTOR_ALL     = "9"    # All sectors


@dataclass
class BuildingApprovalsReport:
    sa2s_in_file:  int = 0
    sa2s_updated:  int = 0
    sa2s_no_row:   int = 0
    total_dwellings: int = 0

    def __str__(self) -> str:
        return (
            f"SA2s in file: {self.sa2s_in_file} | "
            f"Updated: {self.sa2s_updated} | "
            f"No metrics row: {self.sa2s_no_row} | "
            f"Total dwellings: {self.total_dwellings:,}"
        )


def load_building_approvals(
    approvals_zip: Path,
    db: Session,
    *,
    year: int = 2021,
) -> BuildingApprovalsReport:
    """Read ABS building approvals zip and upsert onto abs_census_metrics.

    Args:
        approvals_zip: Path to the ABS SA2 building approvals zip file.
        db:            Synchronous SQLAlchemy session.
        year:          Census year row to update (default 2021).
    """
    report = BuildingApprovalsReport()

    logger.info("Reading building approvals from %s ...", approvals_zip.name)
    df = _read_csv_from_zip(approvals_zip)
    logger.info("Loaded %d raw rows", len(df))

    # --- Filter to new residential, all sectors, actual SA2 codes ----------
    df = df[
        (df["type_work"] == _TYPE_WORK_NEW) &
        (df["type_bld"]  == _TYPE_BLD_TOTAL_RES) &
        (df["own_sector"] == _OWN_SECTOR_ALL) &
        (df["sa2_code"].str.len() == 9)
    ].copy()

    df["dwl"] = pd.to_numeric(df["dwl"], errors="coerce").fillna(0).astype(int)

    # --- Aggregate across all months → total for the financial year ---------
    totals = df.groupby("sa2_code")["dwl"].sum().reset_index()
    totals.columns = ["sa2_code", "total_dwl"]
    report.sa2s_in_file = len(totals)
    report.total_dwellings = int(totals["total_dwl"].sum())
    logger.info("Aggregated: %d SA2s, %d total dwellings",
                report.sa2s_in_file, report.total_dwellings)

    # --- Upsert -------------------------------------------------------------
    for _, row in totals.iterrows():
        metrics = db.get(ABSCEntensMetrics, (str(row["sa2_code"]), year))
        if metrics is None:
            report.sa2s_no_row += 1
            continue
        metrics.building_approvals_1yr = int(row["total_dwl"])
        report.sa2s_updated += 1

    db.commit()
    return report


def _read_csv_from_zip(zip_path: Path) -> pd.DataFrame:
    """Extract the first CSV from the zip and return as DataFrame."""
    with zipfile.ZipFile(zip_path) as zf:
        csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not csv_names:
            raise ValueError(f"No CSV found in {zip_path}")
        with zf.open(csv_names[0]) as fh:
            return pd.read_csv(fh, dtype=str, low_memory=False)
