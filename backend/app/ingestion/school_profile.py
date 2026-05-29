"""CLI entry point for the ACARA School Profile + Location loader.

Downloads (if needed) or uses local copies of ACARA Excel files, then
upserts into the schools table, creates SA2 links, and updates
abs_census_metrics (avg_school_icsea, num_schools).

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.school_profile
    python -m app.ingestion.school_profile \\
        --profile ../data/school_profile_2025.xlsx \\
        --location ../data/school_location_2025.xlsx
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

_PROFILE_URL  = "https://dataandreporting.blob.core.windows.net/anrdataportal/Data-Access-Program/School%20Profile%202025.xlsx"
_LOCATION_URL = "https://dataandreporting.blob.core.windows.net/anrdataportal/Data-Access-Program/School%20Location%202025.xlsx"
_DEFAULT_PROFILE  = Path("../data/school_profile_2025.xlsx")
_DEFAULT_LOCATION = Path("../data/school_location_2025.xlsx")


def _download(url: str, dest: Path) -> None:
    import requests
    logger.info("Downloading %s -> %s", url, dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, verify=False, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    logger.info("Saved %.1f MB", len(r.content) / 1_048_576)


def main() -> None:
    parser = argparse.ArgumentParser(description="Load ACARA school profile + location data")
    parser.add_argument("--profile",  type=Path, default=_DEFAULT_PROFILE,  help="Path to School Profile 2025.xlsx")
    parser.add_argument("--location", type=Path, default=_DEFAULT_LOCATION, help="Path to School Location 2025.xlsx")
    parser.add_argument("--download", action="store_true", help="Re-download files even if they already exist")
    parser.add_argument("--year", type=int, default=2021, help="Census year for abs_census_metrics update (default: 2021)")
    args = parser.parse_args()

    if args.download or not args.profile.exists():
        _download(_PROFILE_URL, args.profile)
    if args.download or not args.location.exists():
        _download(_LOCATION_URL, args.location)

    for label, path in [("--profile", args.profile), ("--location", args.location)]:
        if not path.exists():
            print(f"Error: file not found: {path} ({label})", file=sys.stderr)
            sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.school_profile_loader import load_school_profile

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        logger.info("Loading school profile (census_year=%d) ...", args.year)
        report = load_school_profile(args.profile, args.location, db, census_year=args.year)
        print(f"Done: {report}")
    except Exception as exc:
        logger.exception("Load failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
