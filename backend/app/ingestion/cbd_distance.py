"""CLI entry point for the distance-to-CBD loader.

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.ingestion.cbd_distance [--state VIC] [--force]
"""

from __future__ import annotations

import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> None:
    parser = argparse.ArgumentParser(description="Compute distance_to_cbd_km for SA2 regions")
    parser.add_argument(
        "--state",
        type=str,
        default=None,
        help="Restrict to SA2s in this state (e.g. VIC). Default: all states.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recompute even for SA2s that already have a distance_to_cbd_km value.",
    )
    args = parser.parse_args()

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    from app.ingestion.cbd_distance_loader import load_cbd_distances

    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        state_label = f" (state={args.state})" if args.state else ""
        print(f"Computing distance-to-CBD{state_label} ...")
        report = load_cbd_distances(db, state_filter=args.state, force=args.force)
        print(f"Done: {report}")
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
