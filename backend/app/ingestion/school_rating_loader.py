"""Per-school rating loader — sector (public/private) + ICSEA + ACARA's own
ICSEA percentile, one row per school (unlike school_icsea_loader.py, which
only keeps the SA2-level enrolment-weighted average).

Same SA2-matching strategy as school_icsea_loader.py (suburb name first,
postcode-dominant-SA2 as fallback for ambiguous/unmatched names — see that
module's docstring for why postcode-only matching silently misattributes
schools whose suburb isn't the postcode's dominant one, e.g. Algester's own
schools were landing under neighbouring Parkinson - Drewvale) — reused
directly, not reimplemented. That loader's SA2-level aggregate stays useful
on its own (state-percentile ranking of a whole suburb's schools); this one
adds the individual-school detail for display.

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.school_rating \\
        --icsea "../data/datapacks/School ICSEA Scores 2025.xlsx" \\
        --mb    ../data/datapacks/MB_2021_AUST.xlsx \\
        --poa   ../data/datapacks/POA_2021_AUST.xlsx
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import SchoolRating
from app.ingestion.school_icsea_loader import (
    _build_postcode_sa2_lookup,
    build_suburb_sa2_lookup,
    resolve_school_sa2,
)

logger = logging.getLogger(__name__)

_SECTOR_IS_PUBLIC = {"Government": 1, "Catholic": 0, "Independent": 0}


@dataclass
class SchoolRatingLoadReport:
    schools_loaded: int = 0
    schools_matched_sa2: int = 0
    schools_upserted: int = 0

    def __str__(self) -> str:
        return (
            f"Schools loaded: {self.schools_loaded} | "
            f"Matched to an SA2: {self.schools_matched_sa2} | "
            f"Upserted: {self.schools_upserted}"
        )


def load_school_ratings(icsea_file: Path, mb_file: Path, poa_file: Path, db: Session) -> SchoolRatingLoadReport:
    report = SchoolRatingLoadReport()

    logger.info("Building suburb name -> SA2 lookup from sa2_regions ...")
    suburb_to_sa2 = build_suburb_sa2_lookup(db)

    logger.info("Building postcode -> SA2 lookup from mesh block files ...")
    postcode_to_sa2 = _build_postcode_sa2_lookup(mb_file, poa_file)

    logger.info("Loading per-school ICSEA data ...")
    df = pd.read_excel(
        icsea_file,
        sheet_name="SchoolProfile 2025",
        usecols=[
            "School AGE ID", "School Name", "Suburb", "State", "Postcode",
            "School Sector", "School Type", "ICSEA", "ICSEA Percentile", "Total Enrolments",
        ],
        dtype={"Postcode": "Int64"},
    )
    report.schools_loaded = len(df)

    df["postcode_str"] = df["Postcode"].apply(lambda p: str(int(p)).zfill(4) if pd.notna(p) else None)
    df["sa2_code"] = df.apply(
        lambda row: resolve_school_sa2(row["Suburb"], row["State"], row["postcode_str"], suburb_to_sa2, postcode_to_sa2),
        axis=1,
    )
    report.schools_matched_sa2 = int(df["sa2_code"].notna().sum())

    def _clean_str(v):
        return v if isinstance(v, str) else None

    def _clean_float(v):
        return float(v) if pd.notna(v) else None

    for _, row in df.iterrows():
        if pd.isna(row["School AGE ID"]):
            continue
        sector = _clean_str(row["School Sector"])
        icsea = _clean_float(row["ICSEA"])
        enrolments = _clean_float(row["Total Enrolments"])
        db.merge(
            SchoolRating(
                id=str(int(row["School AGE ID"])),
                name=row["School Name"],
                suburb=_clean_str(row["Suburb"]),
                state=_clean_str(row["State"]),
                sector=sector,
                is_public=_SECTOR_IS_PUBLIC.get(sector) if sector else None,
                school_type=_clean_str(row["School Type"]),
                icsea=icsea,
                icsea_percentile=_clean_float(row["ICSEA Percentile"]),
                total_enrolments=int(enrolments) if enrolments is not None else None,
                sa2_code=row["sa2_code"] if pd.notna(row["sa2_code"]) else None,
            )
        )
        report.schools_upserted += 1

    db.commit()
    return report
