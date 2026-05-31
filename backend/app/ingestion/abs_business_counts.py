"""ABS Business Counts loader — SA2 level business counts by ANZSIC industry.

Source: ABS 8165.0 — Counts of Australian Businesses, including Entries and Exits
File:   Data cube 8: Businesses by industry division by Statistical Area Level 2
URL:    https://www.abs.gov.au/statistics/economy/business-indicators/
        counts-australian-businesses-including-entries-and-exits/latest-release

This gives us the number of REGISTERED businesses per SA2 per ANZSIC industry
division — far more accurate than OSM/Overture for business counts.

Key industry divisions for suburb investment analysis:
    H: Accommodation and Food Services  → cafes, restaurants, takeaways
    G: Retail Trade                     → shops
    Q: Health Care and Social Assistance → GPs, pharmacies, allied health
    E: Construction                     → builders, tradies
    M: Professional Services            → offices, knowledge workers
    P: Education and Training           → tutoring, training centres
    K: Financial and Insurance Services → banks, accountants
    R: Arts and Recreation Services     → gyms, sport clubs
    S: Other Services                   → mechanics, hair salons, laundry

Columns written to abs_census_metrics:
    biz_food_services, biz_retail_trade, biz_health_social,
    biz_construction, biz_professional, biz_education, biz_finance,
    biz_arts_recreation, biz_other_services, biz_total

Usage (CLI):
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.abs_business_counts
    python -m app.ingestion.abs_business_counts --file ../data/datapacks/abs_business_counts_sa2.xlsx
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics

logger = logging.getLogger(__name__)

_DEFAULT_FILE = Path("../data/datapacks/abs_business_counts_sa2.xlsx")
_DOWNLOAD_URL = (
    "https://www.abs.gov.au/statistics/economy/business-indicators/"
    "counts-australian-businesses-including-entries-and-exits/"
    "jul2021-jun2025/8165DC08.xlsx"
)

# ANZSIC division code → ABSCEntensMetrics column name
_DIVISION_MAP: dict[str, str] = {
    "H": "biz_food_services",
    "G": "biz_retail_trade",
    "Q": "biz_health_social",
    "E": "biz_construction",
    "M": "biz_professional",
    "P": "biz_education",
    "K": "biz_finance",
    "R": "biz_arts_recreation",
    "S": "biz_other_services",
}


@dataclass
class BusinessCountReport:
    sa2s_updated: int = 0
    sa2s_skipped: int = 0

    def __str__(self) -> str:
        return f"SA2s updated: {self.sa2s_updated} | Skipped: {self.sa2s_skipped}"


def load_business_counts(
    file: Path,
    db: Session,
    *,
    year: int = 2021,
) -> BusinessCountReport:
    report = BusinessCountReport()

    logger.info("Loading ABS business counts from %s ...", file)
    df = _read_table1(file)
    logger.info("Loaded %d rows (%d SA2s)", len(df), df["sa2_code"].nunique())

    # Pivot: one row per SA2, one column per industry code
    pivot = (
        df[df["industry_code"].isin(list(_DIVISION_MAP.keys()) + ["_TOTAL"])]
        .pivot_table(index="sa2_code", columns="industry_code", values="total", aggfunc="sum", fill_value=0)
    )

    # Total = sum across all industry divisions per SA2
    total_per_sa2 = df.groupby("sa2_code")["total"].sum()

    for sa2_code, row in pivot.iterrows():
        metrics = db.get(ABSCEntensMetrics, (str(sa2_code), year))
        if metrics is None:
            report.sa2s_skipped += 1
            continue

        for div_code, col_name in _DIVISION_MAP.items():
            val = row.get(div_code, 0)
            setattr(metrics, col_name, int(val) if val > 0 else 0)

        metrics.biz_total = int(total_per_sa2.get(sa2_code, 0))
        report.sa2s_updated += 1

    db.commit()
    return report


def _read_table1(file: Path) -> pd.DataFrame:
    """Parse Table 1 from the ABS CABEE SA2 data cube."""
    raw = pd.read_excel(
        file,
        sheet_name="Table 1",
        skiprows=4,
        header=0,
        dtype=str,
    )
    raw.columns = [
        "industry_code", "industry_label",
        "sa2_code", "sa2_name",
        "non_employing", "emp_1_4", "emp_5_19", "emp_20_199", "emp_200plus", "total",
    ]
    # Keep only rows with valid 9-digit SA2 codes
    raw = raw[raw["sa2_code"].str.match(r"^\d{9}$", na=False)].copy()
    raw["total"] = pd.to_numeric(raw["total"], errors="coerce").fillna(0).astype(int)
    # Trim whitespace on industry code
    raw["industry_code"] = raw["industry_code"].str.strip()
    return raw


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    parser = argparse.ArgumentParser(description="Load ABS business counts by SA2")
    parser.add_argument("--file", type=Path, default=_DEFAULT_FILE)
    parser.add_argument("--year", type=int, default=2021)
    parser.add_argument("--download", action="store_true", help="Re-download from ABS")
    args = parser.parse_args()

    if args.download or not args.file.exists():
        import urllib3, requests
        urllib3.disable_warnings()
        logger.info("Downloading from ABS ...")
        r = requests.get(_DOWNLOAD_URL, verify=False, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        args.file.parent.mkdir(parents=True, exist_ok=True)
        args.file.write_bytes(r.content)
        logger.info("Saved %.1f MB to %s", len(r.content) / 1e6, args.file)

    if not args.file.exists():
        print(f"Error: file not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        report = load_business_counts(args.file, db, year=args.year)
        print(f"Done: {report}")
    except Exception:
        logger.exception("Load failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
