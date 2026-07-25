"""CLI entry point for the PropRadar current-listings loader.

Reads PROPRADAR_API_KEY from the environment, then fetches currently-for-sale
listings for SA2s in the given scope and stores them in current_listings.

Usage:
    cd backend
    .venv\\Scripts\\Activate.ps1
    # Set key in .env  ->  PROPRADAR_API_KEY=pr_live_...
    python -m app.ingestion.current_listings --state QLD --suburb Cleveland

    # Full state — mind your plan's call quota first (see current_listings_loader.py):
    python -m app.ingestion.current_listings --state QLD
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch PropRadar current for-sale listings and store onto current_listings"
    )
    parser.add_argument("--state", type=str, default=None, help="Restrict to this state, e.g. QLD")
    parser.add_argument(
        "--suburb",
        type=str,
        default=None,
        help="Restrict to SA2s whose name matches this suburb (pilot runs).",
    )
    parser.add_argument(
        "--sa2-codes",
        type=str,
        default=None,
        help="Comma-separated SA2 codes to process exactly (can span multiple states).",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=3,
        help="Safety cap on pages fetched per suburb (default: 3, 50 listings/page).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-fetch even if this SA2 already has data fetched this calendar month.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log the raw JSON of each suburb's first page (for verifying the response shape).",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="PropRadar API key. Defaults to PROPRADAR_API_KEY env var.",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Same env-loading gotcha as propradar_sold.py: load .env explicitly
    # before reading os.environ, rather than relying on it as a side effect
    # of importing app.db.session below.
    from dotenv import load_dotenv

    load_dotenv()

    api_key = args.api_key or os.environ.get("PROPRADAR_API_KEY", "")
    if not api_key:
        print(
            "Error: no API key provided. Set PROPRADAR_API_KEY in .env or pass --api-key.",
            file=sys.stderr,
        )
        sys.exit(1)

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.current_listings_loader import load_current_listings

    Base.metadata.create_all(bind=sync_engine)

    sa2_codes = [c.strip() for c in args.sa2_codes.split(",")] if args.sa2_codes else None

    db = get_sync_session()
    try:
        print("Fetching PropRadar current listings "
              f"(state={args.state or 'any'}, suburb={args.suburb or '-'}, "
              f"sa2_codes={sa2_codes or '-'}) ...")
        report = load_current_listings(
            db, api_key,
            state=args.state,
            suburb=args.suburb,
            sa2_codes=sa2_codes,
            max_pages=args.max_pages,
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
