"""CLI entry point for the PropRadar suburb-level market stats loader.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.suburb_market_stats                              # full national refresh (~3,642 calls)
    python -m app.ingestion.suburb_market_stats --sa2-codes 301021007,303031064
    python -m app.ingestion.suburb_market_stats --state QLD --suburb Cleveland
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch PropRadar suburb-level market stats")
    parser.add_argument("--state", type=str, default=None, help="Restrict to this state, e.g. QLD")
    parser.add_argument("--suburb", type=str, default=None, help="Restrict to SA2s whose name matches this suburb")
    parser.add_argument("--sa2-codes", type=str, default=None, help="Comma-separated SA2 codes (can span states)")
    parser.add_argument("--force", action="store_true", help="Re-fetch even if already fetched this calendar month")
    parser.add_argument("--api-key", type=str, default=None, help="Defaults to PROPRADAR_API_KEY env var")
    args = parser.parse_args()

    from dotenv import load_dotenv

    load_dotenv()

    api_key = args.api_key or os.environ.get("PROPRADAR_API_KEY", "")
    if not api_key:
        print("Error: no API key provided. Set PROPRADAR_API_KEY in .env or pass --api-key.", file=sys.stderr)
        sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.suburb_market_stats_loader import load_suburb_market_stats

    Base.metadata.create_all(bind=sync_engine)

    sa2_codes = [c.strip() for c in args.sa2_codes.split(",")] if args.sa2_codes else None

    db = get_sync_session()
    try:
        print(f"Fetching PropRadar suburb stats (state={args.state or 'any'}, "
              f"suburb={args.suburb or '-'}, sa2_codes={sa2_codes or '-'}) ...")
        report = load_suburb_market_stats(
            db, api_key,
            state=args.state,
            suburb=args.suburb,
            sa2_codes=sa2_codes,
            force=args.force,
        )
        print(f"Done: {report}")
    except RuntimeError as exc:
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
