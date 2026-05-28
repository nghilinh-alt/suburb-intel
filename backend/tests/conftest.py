"""Shared pytest fixtures for the suburb-intel backend tests.

The fixtures install a temporary SQLite DB BEFORE the application modules
import their global engine, seed a small canned dataset, and expose a
synchronous ``TestClient``.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path
from typing import Iterator

import pytest

# ---------------------------------------------------------------------------
# Path + env setup. Run BEFORE any `app.*` imports because session.py reads the
# DATABASE_URL env var at module-load time to build its global engine.
# ---------------------------------------------------------------------------

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

_TEST_DB_PATH = Path(tempfile.gettempdir()) / "suburb_intel_test.db"
if _TEST_DB_PATH.exists():
    _TEST_DB_PATH.unlink()

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{_TEST_DB_PATH.as_posix()}"

# Now safe to import the app + DB modules.
from fastapi.testclient import TestClient  # noqa: E402

from app.db.models import (  # noqa: E402
    ABSCEntensMetrics,
    InfrastructureProject,
    SA2ProjectLink,
    SA2Region,
    SuburbScore,
)
from app.db.session import AsyncSessionLocal, init_models  # noqa: E402
from app.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

async def _seed() -> None:
    await init_models()
    async with AsyncSessionLocal() as session:
        session.add_all(
            [
                SA2Region(sa2_code="47002", sa2_name="Chermside QLD", state="QLD"),
                SA2Region(sa2_code="22625", sa2_name="Cronulla NSW", state="NSW"),
                SA2Region(sa2_code="30150", sa2_name="Altona Gardens VIC", state="VIC"),
            ]
        )
        session.add_all(
            [
                ABSCEntensMetrics(
                    sa2_code="47002",
                    year=2021,
                    population=28900,
                    median_income=102000,
                    median_age=31.5,
                    renters_pct=31.5,
                    owners_pct=48.9,
                    industry_profile={
                        "tech": 0.18,
                        "finance": 0.22,
                        "retail": 0.20,
                        "education": 0.16,
                    },
                ),
                ABSCEntensMetrics(
                    sa2_code="22625",
                    year=2021,
                    population=18750,
                    median_income=91000,
                    median_age=38.9,
                    renters_pct=38.9,
                    owners_pct=44.1,
                    industry_profile={
                        "healthcare": 0.16,
                        "retail": 0.25,
                        "finance": 0.17,
                        "tech": 0.12,
                    },
                ),
            ]
        )
        session.add_all(
            [
                InfrastructureProject(
                    project_id="INFRA-002",
                    name="Chermside Hospital Upgrade",
                    type="health",
                    value_aud=450_000_000,
                    status="approved",
                ),
            ]
        )
        session.add(
            SA2ProjectLink(sa2_code="47002", project_id="INFRA-002", impact_score=92.0)
        )
        session.add_all(
            [
                SuburbScore(
                    sa2_code="47002",
                    investment_score=82.5,
                    demographic_score=78.0,
                    economic_score=85.0,
                    housing_pressure_score=60.0,
                    resilience_score=75.0,
                    gov_investment_score=90.0,
                ),
                SuburbScore(
                    sa2_code="22625",
                    investment_score=71.0,
                    demographic_score=68.0,
                    economic_score=72.0,
                    housing_pressure_score=55.0,
                    resilience_score=70.0,
                    gov_investment_score=50.0,
                ),
            ]
        )
        await session.commit()


@pytest.fixture(scope="session", autouse=True)
def _bootstrap_db() -> Iterator[None]:
    """Create tables and seed once for the test session."""
    asyncio.run(_seed())
    yield
    if _TEST_DB_PATH.exists():
        try:
            _TEST_DB_PATH.unlink()
        except OSError:
            pass


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
