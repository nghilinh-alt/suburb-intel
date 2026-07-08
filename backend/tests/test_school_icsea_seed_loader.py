"""Tests for the committed ICSEA seed CSV loader (fallback for a fresh clone
without the gated raw ACARA file)."""

from __future__ import annotations

import csv

import pytest

from app.db.models import ABSCEntensMetrics
from app.db.session import AsyncSessionLocal
from app.ingestion.school_icsea_seed_loader import load_school_icsea_seed


def _write_seed_csv(tmp_path, rows):
    path = tmp_path / "seed.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["sa2_code", "sa2_name", "state", "avg_school_icsea", "num_schools"])
        for row in rows:
            w.writerow(row)
    return path


@pytest.mark.asyncio
async def test_seed_loader_updates_existing_census_rows(tmp_path):
    sa2 = "50000001"
    async with AsyncSessionLocal() as session:
        session.add(ABSCEntensMetrics(sa2_code=sa2, year=2021, avg_school_icsea=None, num_schools=None))
        await session.commit()

        seed_path = _write_seed_csv(tmp_path, [(sa2, "Test Suburb", "QLD", "1050.5", "3")])

        # load_school_icsea_seed takes a sync Session; get_sync_session() binds
        # to the same DATABASE_URL as the async test DB, so it's the same file.
        from app.db.session import get_sync_session

        db = get_sync_session()
        report = load_school_icsea_seed(db, seed_path)
        db.close()

    assert report.updated == 1
    assert report.skipped_no_row == 0

    async with AsyncSessionLocal() as session:
        metrics = await session.get(ABSCEntensMetrics, (sa2, 2021))
    assert metrics.avg_school_icsea == 1050.5
    assert metrics.num_schools == 3


def test_seed_loader_skips_sa2_without_census_row(tmp_path):
    from app.db.session import get_sync_session

    seed_path = _write_seed_csv(tmp_path, [("99999999", "Nowhere", "QLD", "1000.0", "1")])
    db = get_sync_session()
    report = load_school_icsea_seed(db, seed_path)
    db.close()

    assert report.updated == 0
    assert report.skipped_no_row == 1
