"""School ICSEA loader.

Reads the ACARA School Profile Excel file (ICSEA scores) and upserts
avg_school_icsea and num_schools onto existing ABSCEntensMetrics rows.

SA2 matching, in priority order:
    1. The ACARA file's own "Suburb"+"State" columns, matched directly
       against SA2Region names (splitting combined SA2 names like
       "Rochedale - Burbank" the same way propradar_sold_loader.py does).
       This is exact where the suburb name is unambiguous.
    2. Postcode → dominant SA2 (via ABS mesh-block allocation), used only
       as a fallback for suburb names that don't match any SA2, or that
       match more than one (e.g. a large suburb ABS split across several
       SA2s by compass direction — "Bathurst" spans 3 SA2s, so which one
       an individual school belongs to can't be resolved by name alone).

    Postcode-only matching used to be the sole method, and it has a real
    failure mode: every school in a postcode gets attributed to whichever
    SA2 has the most mesh blocks for that postcode, even if the specific
    school sits in a *different*, non-dominant SA2 that happens to share
    the postcode (e.g. Algester's own schools were being silently
    attributed to neighbouring Parkinson - Drewvale, the postcode's
    dominant SA2, because they share postcode 4115 — Algester itself
    never got any of its own postcode's mesh-block "votes"). Suburb-name
    matching fixes this whenever the name resolves unambiguously.

    Postcode join path (fallback only):
        school postcode  →  ABS POA_2021_AUST.xlsx  →  MB_CODE
        MB_CODE          →  ABS MB_2021_AUST.xlsx   →  SA2_CODE_2021

For each SA2, computes enrolment-weighted average ICSEA across all schools
resolved to that SA2 by the above.

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
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics, SA2Region
from app.ingestion.propradar_sold_loader import _split_suburb_parts

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
            f"Schools unmatched (no suburb-name or postcode SA2 match): {self.schools_unmatched}"
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

    logger.info("Building suburb name → SA2 lookup from sa2_regions …")
    suburb_to_sa2 = build_suburb_sa2_lookup(db)
    logger.info("Lookup covers %d unambiguous (state, suburb) names", len(suburb_to_sa2))

    logger.info("Building postcode → SA2 lookup from mesh block files …")
    postcode_to_sa2 = _build_postcode_sa2_lookup(mb_file, poa_file)
    logger.info("Lookup covers %d postcodes", len(postcode_to_sa2))

    logger.info("Loading ICSEA school data …")
    schools = _load_schools(icsea_file)

    schools["sa2_code"] = schools.apply(
        lambda row: resolve_school_sa2(row["suburb"], row["state"], row["postcode_str"], suburb_to_sa2, postcode_to_sa2),
        axis=1,
    )

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

def build_suburb_sa2_lookup(db: Session) -> dict[tuple[str, str], str]:
    """Return {(state, suburb_name_lower): sa2_code} for suburb names that
    map to exactly one SA2. Combined SA2 names (e.g. "Rochedale - Burbank")
    are split into their real-suburb parts the same way propradar_sold_loader
    does. Names that resolve to more than one SA2 (a suburb ABS split across
    several SA2s by compass direction, e.g. "Bathurst") are deliberately
    excluded — ambiguous by name alone, so callers should fall back to
    postcode-dominant-SA2 for those.
    """
    rows = db.execute(select(SA2Region.sa2_code, SA2Region.sa2_name, SA2Region.state)).all()

    candidates: dict[tuple[str, str], set[str]] = {}
    for sa2_code, sa2_name, state in rows:
        for part in _split_suburb_parts(sa2_name):
            key = (state, part.lower())
            candidates.setdefault(key, set()).add(sa2_code)

    return {key: next(iter(sa2_codes)) for key, sa2_codes in candidates.items() if len(sa2_codes) == 1}


def resolve_school_sa2(
    suburb: str | None,
    state: str | None,
    postcode_str: str | None,
    suburb_to_sa2: dict[tuple[str, str], str],
    postcode_to_sa2: dict[str, str],
) -> str | None:
    """Resolve one school's SA2: prefer an unambiguous suburb-name match,
    fall back to postcode-dominant-SA2 when the name doesn't match or is
    ambiguous."""
    if isinstance(suburb, str) and isinstance(state, str):
        sa2_code = suburb_to_sa2.get((state, suburb.strip().lower()))
        if sa2_code is not None:
            return sa2_code
    return postcode_to_sa2.get(postcode_str)


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
        usecols=["Suburb", "State", "Postcode", "ICSEA", "Total Enrolments"],
        dtype={"Postcode": "Int64"},
    )
    df = df.rename(columns={
        "Suburb": "suburb",
        "State": "state",
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
