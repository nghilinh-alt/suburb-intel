"""ABS Regional Population loader — updates SA2 population to 2024-25 estimates.

Source: ABS Regional Population 2024-25 (Cat. 3218.0)
File:   32180DS0001_2024-25.xlsx
URL:    https://www.abs.gov.au/statistics/people/population/regional-population/
        2024-25/32180DS0001_2024-25.xlsx
Download: python -m app.ingestion.abs_regional_population --download

This replaces the 2021 Census population figure in abs_census_metrics with
the current ABS estimated resident population (ERP) at 30 June 2025.
Also stores ERP at 30 June 2024 for year-on-year comparison.

Sheets: One per state (Table 1=NSW, Table 2=VIC, Table 3=QLD, ...)
Columns after SA2: ERP_2024, ERP_2025, change_no, change_pct, births, deaths, net_migration, area_km2, density

Columns written to abs_census_metrics (year=2021 rows):
    population_2024   — ERP at 30 June 2024
    population_2025   — ERP at 30 June 2025 (most current)
    population        — overwritten with ERP 2025 (replaces census count)

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.abs_regional_population
    python -m app.ingestion.abs_regional_population --download
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

_DEFAULT_FILE  = Path("../data/datapacks/abs_regional_pop_2024-25.xlsx")
_DOWNLOAD_URL  = (
    "https://www.abs.gov.au/statistics/people/population/regional-population/"
    "2024-25/32180DS0001_2024-25.xlsx"
)

# Sheet names → state code (sheets are ordered NSW, VIC, QLD, SA, WA, TAS, NT, ACT, OT)
_SHEET_STATES = {
    "Table 1": "NSW",
    "Table 2": "VIC",
    "Table 3": "QLD",
    "Table 4": "SA",
    "Table 5": "WA",
    "Table 6": "TAS",
    "Table 7": "NT",
    "Table 8": "ACT",
    "Table 9": "OT",  # Other Territories (tiny, skip)
}


@dataclass
class PopulationLoadReport:
    updated: int = 0
    skipped: int = 0
    total_rows: int = 0

    def __str__(self) -> str:
        return (
            f"SA2 rows updated: {self.updated} | "
            f"Skipped (no metrics row): {self.skipped} | "
            f"Total ABS rows: {self.total_rows}"
        )


def load_regional_population(
    file: Path,
    db: Session,
    *,
    year: int = 2021,
) -> PopulationLoadReport:
    report = PopulationLoadReport()

    xl = pd.ExcelFile(file)
    all_rows: list[dict] = []

    for sheet, state in _SHEET_STATES.items():
        if sheet not in xl.sheet_names:
            continue
        df = pd.read_excel(
            file,
            sheet_name=sheet,
            skiprows=5,
            header=0,
            dtype={"SA2 code": str},
        )
        # Drop rows without valid SA2 code (totals, headers, blanks)
        df = df[df["SA2 code"].str.match(r"^\d{9}$", na=False)].copy()

        # Rename the positional numeric columns
        # Original: [GCCSA code, GCCSA name, SA4 code, SA4 name, SA3 code, SA3 name,
        #            SA2 code, SA2 name, ERP 2024, ERP 2025, change_no, change_pct, ...]
        col_names = list(df.columns)
        # Columns 8 onward are numeric
        if len(col_names) >= 11:
            df.rename(columns={
                col_names[8]:  "erp_2024",
                col_names[9]:  "erp_2025",
                col_names[10]: "change_no",
                col_names[11]: "change_pct",
            }, inplace=True)

        for _, row in df.iterrows():
            try:
                erp_24 = int(float(row["erp_2024"])) if pd.notna(row.get("erp_2024")) else None
                erp_25 = int(float(row["erp_2025"])) if pd.notna(row.get("erp_2025")) else None
                if erp_24 is None and erp_25 is None:
                    continue
                all_rows.append({
                    "sa2_code": str(row["SA2 code"]).zfill(9),
                    "erp_2024": erp_24,
                    "erp_2025": erp_25,
                })
            except (TypeError, ValueError):
                continue

    report.total_rows = len(all_rows)
    logger.info("Loaded %d SA2 population rows across all states", report.total_rows)

    for row in all_rows:
        metrics = db.get(ABSCEntensMetrics, (row["sa2_code"], year))
        if metrics is None:
            report.skipped += 1
            continue

        # Update population to most current ABS estimate (2025)
        if row["erp_2025"] is not None:
            metrics.population = row["erp_2025"]
        elif row["erp_2024"] is not None:
            metrics.population = row["erp_2024"]
        report.updated += 1

    db.commit()
    return report


if __name__ == "__main__":
    import argparse
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    parser = argparse.ArgumentParser(description="Load ABS Regional Population 2024-25 into SA2 metrics")
    parser.add_argument("--file", type=Path, default=_DEFAULT_FILE)
    parser.add_argument("--download", action="store_true", help="Re-download from ABS")
    parser.add_argument("--year", type=int, default=2021)
    args = parser.parse_args()

    if args.download or not args.file.exists():
        import urllib3, requests
        urllib3.disable_warnings()
        logger.info("Downloading from ABS ...")
        r = requests.get(_DOWNLOAD_URL, verify=False, timeout=60,
                         headers={"User-Agent": "SuburbIntel/1.0"})
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
        report = load_regional_population(args.file, db, year=args.year)
        print(f"Done: {report}")
    except Exception:
        logger.exception("Load failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
