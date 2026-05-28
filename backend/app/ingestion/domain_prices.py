"""CLI entry point for the Domain API property price loader.

Reads DOMAIN_API_KEY from the environment (or --api-key flag), then fetches
suburb performance statistics from the Domain Group API and stores them onto
abs_census_metrics rows.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1
    # Set key in .env  →  DOMAIN_API_KEY=key_...
    python -m app.ingestion.domain_prices \\
        --mb  "../data/datapacks/MB_2021_AUST.xlsx" \\
        --poa "../data/datapacks/POA_2021_AUST.xlsx" \\
        --state VIC

    # Or pass the key explicitly (not recommended for scripts):
    python -m app.ingestion.domain_prices \\
        --mb  "../data/datapacks/MB_2021_AUST.xlsx" \\
        --poa "../data/datapacks/POA_2021_AUST.xlsx" \\
        --api-key key_...
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch Domain suburb price stats and store onto abs_census_metrics"
    )
    parser.add_argument(
        "--mb",
        type=Path,
        required=True,
        help="Path to MB_2021_AUST.xlsx (Mesh Block → SA2 allocation)",
    )
    parser.add_argument(
        "--poa",
        type=Path,
        required=True,
        help="Path to POA_2021_AUST.xlsx (Mesh Block → POA/postcode allocation)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="Domain API key (key_...). Defaults to DOMAIN_API_KEY env var.",
    )
    parser.add_argument(
        "--state",
        type=str,
        default=None,
        help="Restrict to SA2s in this state (e.g. VIC). Recommended for large DBs.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2021,
        help="Census year whose metrics rows to update (default: 2021).",
    )
    args = parser.parse_args()

    # Resolve API key
    api_key = args.api_key or os.environ.get("DOMAIN_API_KEY", "")
    if not api_key:
        print(
            "Error: no API key provided. Set DOMAIN_API_KEY in .env or pass --api-key.",
            file=sys.stderr,
        )
        sys.exit(1)
    if not api_key.startswith("key_"):
        print(
            f"Warning: API key does not start with 'key_' — got '{api_key[:8]}...'",
            file=sys.stderr,
        )

    for flag, path in [("--mb", args.mb), ("--poa", args.poa)]:
        if not path.exists():
            print(f"Error: file not found for {flag}: {path}", file=sys.stderr)
            sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.domain_prices_loader import load_domain_prices

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        state_label = f" (state={args.state})" if args.state else ""
        print(f"Fetching Domain property prices{state_label} ...")
        report = load_domain_prices(
            args.mb, args.poa, db, api_key,
            year=args.year,
            state_filter=args.state,
        )
        print(f"Done: {report}")
    except RuntimeError as exc:
        # API auth errors — show clearly, don't rollback
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
