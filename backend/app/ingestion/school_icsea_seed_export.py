"""Exports the current per-SA2 ICSEA averages to data/seeds/school_icsea_by_sa2.csv
for commit to the repo — see school_icsea_seed_loader.py for why this exists
(ACARA's raw file is gated, so we keep a small derived fallback in git).

Run this after a real school_icsea_loader.py run against a fresh ACARA file,
to refresh the committed seed.

Usage (CLI):
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.school_icsea_seed_export
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

_DEFAULT_OUTPUT = Path("../data/seeds/school_icsea_by_sa2.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export per-SA2 ICSEA averages to a committable seed CSV")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()

    from app.db.models import ABSCEntensMetrics, SA2Region
    from app.db.session import get_sync_session

    db = get_sync_session()
    rows = (
        db.query(
            SA2Region.sa2_code,
            SA2Region.sa2_name,
            SA2Region.state,
            ABSCEntensMetrics.avg_school_icsea,
            ABSCEntensMetrics.num_schools,
        )
        .join(ABSCEntensMetrics, ABSCEntensMetrics.sa2_code == SA2Region.sa2_code)
        .filter(ABSCEntensMetrics.year == 2021, ABSCEntensMetrics.avg_school_icsea.isnot(None))
        .order_by(SA2Region.sa2_code)
        .all()
    )
    db.close()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sa2_code", "sa2_name", "state", "avg_school_icsea", "num_schools"])
        w.writerows(rows)

    print(f"Exported {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
