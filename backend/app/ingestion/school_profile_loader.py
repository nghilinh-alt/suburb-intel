"""ACARA School Profile + Location loader.

Joins two ACARA Excel files (downloaded from acara.edu.au/contact-us/acara-data-access):
  - School Profile 2025.xlsx  — ICSEA, enrolments, year range, sector/type
  - School Location 2025.xlsx — lat/lon, SA2 code (direct), remoteness

Both files are joined on ACARA SML ID.

Tables written
──────────────
schools          — one row per school (upsert on acara_id)
sa2_school_link  — containing SA2 (score=1.0) + border-adjacent SA2s (score=0.5)

Also updates abs_census_metrics (avg_school_icsea, num_schools) per SA2 using
the direct SA2 code from the location file, replacing the earlier postcode-based
approximation written by school_icsea_loader.

Usage (CLI):
    python -m app.ingestion.school_profile \\
        --profile ../data/school_profile_2025.xlsx \\
        --location ../data/school_location_2025.xlsx
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics, SA2Region, School, SA2SchoolLink
from app.ingestion.infrastructure_loader import (
    _load_sa2_geodataframe,
    _find_sa2s_for_project,
)

logger = logging.getLogger(__name__)

_SOURCE_YEAR = 2025


@dataclass
class SchoolLoadReport:
    schools_upserted: int = 0
    sa2_links: int = 0
    census_rows_updated: int = 0
    schools_no_sa2: int = 0

    def __str__(self) -> str:
        return (
            f"Schools upserted: {self.schools_upserted} | "
            f"SA2 links: {self.sa2_links} | "
            f"Census rows updated: {self.census_rows_updated} | "
            f"Schools with no SA2: {self.schools_no_sa2}"
        )


def load_school_profile(
    profile_file: Path,
    location_file: Path,
    db: Session,
    *,
    census_year: int = 2021,
) -> SchoolLoadReport:
    report = SchoolLoadReport()

    logger.info("Reading School Profile file ...")
    profile = _read_profile(profile_file)

    logger.info("Reading School Location file ...")
    location = _read_location(location_file)

    logger.info("Joining on ACARA SML ID (%d profile, %d location rows) ...", len(profile), len(location))
    df = location.merge(profile, on="acara_id", how="left")
    logger.info("Merged: %d schools", len(df))

    logger.info("Loading SA2 geometries for adjacency links ...")
    sa2_gdf = _load_sa2_geodataframe(db)
    logger.info("Loaded %d SA2 polygons", len(sa2_gdf))

    # Valid SA2 codes in DB
    valid_sa2s = {
        row[0]
        for row in db.query(SA2Region.sa2_code).all()
    }

    # Clear existing SA2 school links (full reload)
    db.query(SA2SchoolLink).delete(synchronize_session=False)

    for _, row in df.iterrows():
        acara_id = str(row["acara_id"])
        sa2_code = row.get("sa2_code")
        sa2_code = str(int(sa2_code)) if pd.notna(sa2_code) else None
        # Pad to 9 digits to match ABS SA2 codes
        if sa2_code and len(sa2_code) < 9:
            sa2_code = sa2_code.zfill(9)
        if sa2_code and sa2_code not in valid_sa2s:
            sa2_code = None

        lat = row.get("lat")
        lon = row.get("lon")
        lat = float(lat) if pd.notna(lat) else None
        lon = float(lon) if pd.notna(lon) else None

        school = db.get(School, acara_id)
        fields = dict(
            name=str(row.get("name") or ""),
            suburb=_str(row.get("suburb")),
            state=_str(row.get("state")),
            postcode=_str(row.get("postcode")),
            sector=_str(row.get("sector")),
            school_type=_str(row.get("school_type")),
            is_special=int(row.get("is_special", 0) or 0),
            lat=lat,
            lon=lon,
            sa2_code=sa2_code,
            remoteness=_str(row.get("remoteness")),
            year_range=_str(row.get("year_range")),
            icsea=_float(row.get("icsea")),
            icsea_percentile=_float(row.get("icsea_percentile")),
            total_enrolments=_int(row.get("total_enrolments")),
            indigenous_pct=_float(row.get("indigenous_pct")),
            source_year=_SOURCE_YEAR,
            acara_location_age_id=_str(row.get("location_age_id")),
        )

        if school:
            for k, v in fields.items():
                setattr(school, k, v)
        else:
            db.add(School(acara_id=acara_id, **fields))
        report.schools_upserted += 1

        # SA2 links via geometry (containment + adjacency)
        if lat is not None and lon is not None:
            for link_sa2, score in _find_sa2s_for_project(lat, lon, sa2_gdf):
                db.add(SA2SchoolLink(
                    sa2_code=link_sa2,
                    acara_id=acara_id,
                    impact_score=score,
                ))
                report.sa2_links += 1
        elif sa2_code:
            # Fallback: containment only from location file SA2 code
            db.add(SA2SchoolLink(sa2_code=sa2_code, acara_id=acara_id, impact_score=1.0))
            report.sa2_links += 1
            report.schools_no_sa2 += 1

    db.flush()

    # Update abs_census_metrics: avg_school_icsea + num_schools per SA2
    logger.info("Aggregating school ICSEA to SA2 for census metrics ...")
    _update_census_metrics(df, db, census_year, report)

    db.commit()
    return report


def _update_census_metrics(
    df: pd.DataFrame,
    db: Session,
    census_year: int,
    report: SchoolLoadReport,
) -> None:
    valid = df.dropna(subset=["sa2_code", "icsea", "total_enrolments"]).copy()
    valid["sa2_code_str"] = valid["sa2_code"].apply(
        lambda x: str(int(x)).zfill(9) if pd.notna(x) else None
    )
    valid = valid.dropna(subset=["sa2_code_str"])

    for sa2_code, group in valid.groupby("sa2_code_str"):
        metrics = db.get(ABSCEntensMetrics, (sa2_code, census_year))
        if metrics is None:
            continue
        total_enrol = group["total_enrolments"].sum()
        if total_enrol > 0:
            avg_icsea = (group["icsea"] * group["total_enrolments"]).sum() / total_enrol
        else:
            avg_icsea = group["icsea"].mean()
        metrics.avg_school_icsea = round(float(avg_icsea), 1)
        metrics.num_schools = len(group)
        report.census_rows_updated += 1


# ---------------------------------------------------------------------------
# File readers
# ---------------------------------------------------------------------------

def _read_profile(path: Path) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name="SchoolProfile 2025",
        usecols=[
            "ACARA SML ID",
            "Year Range", "Geolocation", "ICSEA", "ICSEA Percentile",
            "Total Enrolments", "Indigenous Enrolments (%)",
        ],
        dtype={"ACARA SML ID": str},
    )
    df = df.rename(columns={
        "ACARA SML ID": "acara_id",
        "Year Range": "year_range",
        "Geolocation": "geolocation",
        "ICSEA": "icsea",
        "ICSEA Percentile": "icsea_percentile",
        "Total Enrolments": "total_enrolments",
        "Indigenous Enrolments (%)": "indigenous_pct",
    })
    return df


def _read_location(path: Path) -> pd.DataFrame:
    df = pd.read_excel(
        path,
        sheet_name="SchoolLocations 2025",
        usecols=[
            "ACARA SML ID", "Location AGE ID", "School Name", "Suburb",
            "State", "Postcode", "School Sector", "School Type",
            "Special school", "Latitude", "Longitude",
            "ABS Remoteness Area Name", "Statistical Area 2",
        ],
        dtype={"ACARA SML ID": str, "Statistical Area 2": str},
    )
    df = df.rename(columns={
        "ACARA SML ID": "acara_id",
        "Location AGE ID": "location_age_id",
        "School Name": "name",
        "Suburb": "suburb",
        "State": "state",
        "Postcode": "postcode",
        "School Sector": "sector",
        "School Type": "school_type",
        "Special school": "is_special",
        "Latitude": "lat",
        "Longitude": "lon",
        "ABS Remoteness Area Name": "remoteness",
        "Statistical Area 2": "sa2_code",
    })
    return df


# ---------------------------------------------------------------------------
# Type coercion helpers
# ---------------------------------------------------------------------------

def _str(v) -> str | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return str(v).strip() or None


def _float(v) -> float | None:
    try:
        f = float(v)
        return None if pd.isna(f) else f
    except (TypeError, ValueError):
        return None


def _int(v) -> int | None:
    try:
        f = float(v)
        return None if pd.isna(f) else int(f)
    except (TypeError, ValueError):
        return None
