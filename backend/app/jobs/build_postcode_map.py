"""Build postcode → SA2 mapping from ABS 2021 mesh block correspondence files.

One postcode can span multiple SA2s (e.g. 4115 covers both Algester and
Parkinson-Drewvale). All relationships are stored, with is_dominant=1
flagging the SA2 that contains the majority of mesh blocks for each postcode.

Source files (already in data/datapacks/):
    MB_2021_AUST.xlsx   — mesh block → SA2 mapping
    POA_2021_AUST.xlsx  — mesh block → postcode (POA) mapping

Usage:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m app.jobs.build_postcode_map
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_MB_FILE  = Path("../data/datapacks/MB_2021_AUST.xlsx")
_POA_FILE = Path("../data/datapacks/POA_2021_AUST.xlsx")


def run_build(db) -> str:
    import pandas as pd
    from app.db.models import PostcodeSA2Map, Base
    from app.db.session import sync_engine
    Base.metadata.create_all(bind=sync_engine)

    logger.info("Loading mesh block files ...")
    mb  = pd.read_excel(_MB_FILE,  usecols=["MB_CODE_2021", "SA2_CODE_2021"], dtype=str)
    poa = pd.read_excel(_POA_FILE, usecols=["MB_CODE_2021", "POA_CODE_2021"], dtype=str)

    merged = mb.merge(poa, on="MB_CODE_2021", how="inner")
    logger.info("Merged %d mesh block rows", len(merged))

    # Count mesh blocks per (postcode, SA2) pair
    counts = (
        merged.groupby(["POA_CODE_2021", "SA2_CODE_2021"])
        .size()
        .reset_index(name="mb_count")
    )

    # Mark dominant SA2 per postcode
    dominant_sa2 = (
        counts.sort_values("mb_count", ascending=False)
        .drop_duplicates("POA_CODE_2021")
        .set_index("POA_CODE_2021")["SA2_CODE_2021"]
    )
    counts["is_dominant"] = counts.apply(
        lambda r: 1 if dominant_sa2.get(r["POA_CODE_2021"]) == r["SA2_CODE_2021"] else 0,
        axis=1,
    )

    # Only keep postcodes with valid SA2 codes in our DB
    from sqlalchemy import text
    valid_sa2s = {
        row[0] for row in db.execute(text("SELECT sa2_code FROM sa2_regions"))
    }
    counts = counts[counts["SA2_CODE_2021"].isin(valid_sa2s)]

    logger.info("Writing %d postcode→SA2 relationships ...", len(counts))

    db.query(PostcodeSA2Map).delete(synchronize_session=False)
    for _, row in counts.iterrows():
        db.add(PostcodeSA2Map(
            postcode    = row["POA_CODE_2021"],
            sa2_code    = row["SA2_CODE_2021"],
            mb_count    = int(row["mb_count"]),
            is_dominant = int(row["is_dominant"]),
        ))

    db.commit()
    unique_postcodes = counts["POA_CODE_2021"].nunique()
    return f"Postcodes loaded: {unique_postcodes} | SA2 relationships: {len(counts)}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    from app.db.models import Base
    from app.db.session import get_sync_session, sync_engine
    Base.metadata.create_all(bind=sync_engine)

    db = get_sync_session()
    try:
        result = run_build(db)
        print(f"Done: {result}")
    except Exception:
        logger.exception("Build failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()
