"""Bootstrap Postgres schema for suburb-intel.

Run once against a fresh Postgres instance:
    cd backend
    .\.venv\Scripts\Activate.ps1
    python -m scripts.init_pg

The DATABASE_URL environment variable (or backend/.env) must point to the
Postgres instance. SQLite in-memory is also supported for testing.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ensure the backend package root is on the path when run as a script.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import DATABASE_URL, init_models


async def main() -> None:
    print(f"Initialising schema at: {DATABASE_URL}")
    await init_models()
    print("Done — all tables created (or already exist).")


if __name__ == "__main__":
    asyncio.run(main())
