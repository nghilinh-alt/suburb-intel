"""Loads the committed ICSEA seed CSV (data/seeds/school_icsea_by_sa2.csv).

This is a fallback for a fresh clone: `school_icsea_loader.py` needs the raw
ACARA "School ICSEA Scores" file, which is gated behind commercial-use terms
and isn't in this repo. Rather than lose the aggregate result entirely on a
fresh checkout, we commit a small derived CSV — SA2-level averages only
(sa2_code, avg_school_icsea, num_schools), not the raw per-school list ACARA's
terms are actually about. If you have the real ACARA file, prefer running
school_icsea_loader.py directly instead — it's more accurate and this seed
won't be refreshed as often.

Usage (CLI):
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.school_icsea_seed
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models import ABSCEntensMetrics

logger = logging.getLogger(__name__)

_DEFAULT_SEED = Path("../data/seeds/school_icsea_by_sa2.csv")


@dataclass
class SeedLoadReport:
    updated: int = 0
    skipped_no_row: int = 0

    def __str__(self) -> str:
        return f"Updated: {self.updated} | Skipped (no census row): {self.skipped_no_row}"


def load_school_icsea_seed(db: Session, seed_path: Path = _DEFAULT_SEED, *, year: int = 2021) -> SeedLoadReport:
    report = SeedLoadReport()

    with open(seed_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            sa2_code = row["sa2_code"]
            metrics = db.get(ABSCEntensMetrics, (sa2_code, year))
            if metrics is None:
                report.skipped_no_row += 1
                continue
            metrics.avg_school_icsea = float(row["avg_school_icsea"])
            metrics.num_schools = int(row["num_schools"])
            report.updated += 1

    db.commit()
    return report
