"""Distance-to-CBD loader.

Computes each SA2's centroid from its stored `geometry_geojson` and the
haversine distance from that centroid to its state capital's CBD (hardcoded
coordinates in `app.core.geo`). Writes the result onto `sa2_regions.distance_to_cbd_km`.

No external API — pure geometry computation, so there's no rate limit to
respect; batching/committing periodically is just to keep the transaction
size sane and make a re-run resumable.

Columns written to sa2_regions
───────────────────────────────
    distance_to_cbd_km

Usage (CLI):
    cd backend
    .venv\\Scripts\\Activate.ps1
    python -m app.ingestion.cbd_distance
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.geo import centroid_from_geojson, distance_to_cbd_km as _distance_to_cbd_km
from app.db.models import SA2Region

logger = logging.getLogger(__name__)

_COMMIT_EVERY = 100


@dataclass
class CBDDistanceReport:
    sa2s_processed: int = 0
    sa2s_updated: int = 0
    sa2s_no_geom: int = 0
    sa2s_unknown_state: int = 0

    def __str__(self) -> str:
        return (
            f"Processed: {self.sa2s_processed} | "
            f"Updated: {self.sa2s_updated} | "
            f"No geometry: {self.sa2s_no_geom} | "
            f"Unknown state: {self.sa2s_unknown_state}"
        )


def load_cbd_distances(
    db: Session,
    *,
    state_filter: str | None = None,
    force: bool = False,
) -> CBDDistanceReport:
    """Compute and store distance_to_cbd_km for all (or filtered) SA2 regions.

    Args:
        db:            Synchronous SQLAlchemy session.
        state_filter:  If set (e.g. "VIC"), only process SA2s in that state.
        force:         If True, recompute even for SA2s that already have a value
                        (bypasses resume logic).
    """
    report = CBDDistanceReport()

    q = db.query(SA2Region.sa2_code, SA2Region.state, SA2Region.geometry_geojson, SA2Region.distance_to_cbd_km)
    if state_filter:
        q = q.filter(SA2Region.state == state_filter)
    sa2_rows = q.all()

    total = len(sa2_rows)
    logger.info("Processing %d SA2s ...", total)

    for i, (sa2_code, state, geojson_str, existing) in enumerate(sa2_rows, 1):
        report.sa2s_processed += 1

        if not force and existing is not None:
            continue

        centroid = centroid_from_geojson(geojson_str)
        if centroid is None:
            report.sa2s_no_geom += 1
            continue

        distance = _distance_to_cbd_km(centroid, state)
        if distance is None:
            report.sa2s_unknown_state += 1
            continue

        region = db.get(SA2Region, sa2_code)
        region.distance_to_cbd_km = distance
        report.sa2s_updated += 1

        if i % _COMMIT_EVERY == 0:
            logger.info("  Progress: %d / %d SA2s", i, total)
            db.commit()

    db.commit()
    return report
