"""SEIFA 2016 loader + gentrification change signal.

Reads the ABS SEIFA 2016 SA2-level Excel file, upserts the 2016 raw scores
onto abs_census_metrics, then computes 2021-minus-2016 delta columns as the
primary gentrification direction-of-change signal.

Source file:  SEIFA_2016_SA2.xls
Download:     https://www.abs.gov.au/AUSSTATS/abs@.nsf/DetailsPage/2033.0.55.0012016
              → "Statistical Area Level 2, Indexes" XLS

Note on SA2 boundaries: 2016 SA2 codes differ slightly from 2021 (~138 SA2s
were split/merged). Unmatched codes are skipped; 2021 code coverage is ~93%.

Columns written to abs_census_metrics (census year 2021)
─────────────────────────────────────────────────────────
seifa_irsd_score_2016   — raw 2016 IRSD score
seifa_irsad_score_2016  — raw 2016 IRSAD score
seifa_ieo_score_2016    — raw 2016 IEO score

seifa_irsd_change   — IRSD 2021 − 2016  (positive = less disadvantaged)
seifa_irsad_change  — IRSAD 2021 − 2016
seifa_ieo_change    — IEO 2021 − 2016   (positive = more educated/professional influx)

Usage (CLI):
    python -m app.ingestion.seifa_change \\
        --file ../data/datapacks/SEIFA_2016_SA2.xls
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
class SeifaChangeReport:
    updated: int = 0
    skipped_no_row: int = 0
    skipped_no_score: int = 0
    skipped_no_2021: int = 0

    def __str__(self) -> str:
        return (
            f"Updated: {self.updated} | "
            f"Skipped (no census row): {self.skipped_no_row} | "
            f"Skipped (null 2016 score): {self.skipped_no_score} | "
            f"Skipped (null 2021 score, no delta): {self.skipped_no_2021}"
        )


def load_seifa_change(
    seifa_2016_file: Path,
    db: Session,
    *,
    year: int = 2021,
) -> SeifaChangeReport:
    report = SeifaChangeReport()

    logger.info("Loading SEIFA 2016 data from %s ...", seifa_2016_file)
    df = _load_table1(seifa_2016_file)
    logger.info("Loaded %d SA2 rows from 2016 SEIFA", len(df))

    for _, row in df.iterrows():
        sa2_code = str(row["sa2_code"]).zfill(9)

        if pd.isna(row["irsd_score"]):
            report.skipped_no_score += 1
            continue

        metrics = db.get(ABSCEntensMetrics, (sa2_code, year))
        if metrics is None:
            report.skipped_no_row += 1
            continue

        # Store 2016 raw scores
        irsd_16   = _float(row["irsd_score"])
        irsad_16  = _float(row["irsad_score"])
        ieo_16    = _float(row["ieo_score"])

        metrics.seifa_irsd_score_2016  = irsd_16
        metrics.seifa_irsad_score_2016 = irsad_16
        metrics.seifa_ieo_score_2016   = ieo_16

        # Compute deltas: 2021 minus 2016
        if metrics.seifa_irsd_score is not None and irsd_16 is not None:
            metrics.seifa_irsd_change = round(metrics.seifa_irsd_score - irsd_16, 1)
        if metrics.seifa_irsad_score is not None and irsad_16 is not None:
            metrics.seifa_irsad_change = round(metrics.seifa_irsad_score - irsad_16, 1)
        if metrics.seifa_ieo_score is not None and ieo_16 is not None:
            metrics.seifa_ieo_change = round(metrics.seifa_ieo_score - ieo_16, 1)

        if metrics.seifa_irsd_score is None:
            report.skipped_no_2021 += 1

        report.updated += 1

    db.commit()
    return report


def _load_table1(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(
        path,
        sheet_name="Table 1",
        skiprows=5,
        header=0,
        dtype={0: str},
        na_values=["-"],
    )
    raw.columns = [
        "sa2_code", "sa2_name",
        "irsd_score", "irsd_decile",
        "irsad_score", "irsad_decile",
        "ier_score", "ier_decile",
        "ieo_score", "ieo_decile",
        "population",
    ]
    # Strip decimal from SA2 code (e.g. "101021007.0" → "101021007")
    raw["sa2_code"] = raw["sa2_code"].str.split(".").str[0].str.zfill(9)
    raw = raw[raw["sa2_code"].str.match(r"^\d{9}$", na=False)].copy()
    return raw


def _float(val) -> float | None:
    if pd.isna(val):
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None
