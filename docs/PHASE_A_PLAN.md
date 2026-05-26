# Phase A — Real ABS data, Postgres, precomputed scores

**Goal:** Replace the three hand-seeded SA2 rows with the real Australian Bureau of Statistics Census 2021 data for all ~2,500 SA2 regions, served from a local Postgres database, with `suburb_scores` precomputed for every region.

**Owner:** Claude Code in `C:\Users\nghil\Projects\Hermes\suburb-intel`.
**Predecessor work:** PRs #2 (endpoint + frontend bug fixes) and #3 (suburb endpoint join + score clamp + frontend wiring) — already merged to master.
**Status at start of Phase A:** master is at the merge of PR #3. `GET /suburb/{id}` works for the three seeded rows. `SuburbPage.tsx` renders live API data.

---

## 0. Pre-flight: validate data-source assumptions (do this first)

Before writing any code, confirm two things by hand. Spend 30 minutes, no more.

### 0.1 Confirm the ABS Census 2021 DataPack format

The existing `backend/app/api/data_sources/abs.py` hits `https://api.abs.gov.au/v1/data/Census2021`. This URL is **not validated** — it was inherited from the original repo and may not exist. The current ABS public data API lives at `https://api.data.abs.gov.au/` and uses SDMX-JSON, which has a totally different response shape.

For Phase A we are not using the API at all — we are using bulk **DataPacks**. Download one and inspect:

1. Go to https://www.abs.gov.au/census/find-census-data/datapacks
2. Pick **Census 2021 General Community Profile (GCP)**, format = CSV, geography = SA2, area = a single state (e.g. Victoria) to keep the download small for a first pass.
3. Unzip. You should see:
   - `2021Census_geog_desc_1st_2nd_3rd_release.xlsx` (or similar) — the SA2 lookup table
   - `2021Census_G01_*_SA2.csv` through `G59` — the actual metrics, one CSV per "table"
   - Each CSV has one row per SA2 code and columns named with cryptic codes like `Tot_P_M`, `Median_age_persons`, etc.
4. The full metadata mapping is in the `Metadata` folder of the same DataPack — open `Metadata_2021_GCP_DataPack.xlsx` to map column codes to human descriptions.

Confirm you can:
- Read `G01` (selected medians) and find the columns we need (population, median age, median income, dwelling/tenure breakdown).
- Read `G17a/b/c` (income by age/sex) for the household income column.
- Read `G33` (dwelling structure) for renter/owner percentages.
- Read `G09a/b/c` (country of birth) — not needed yet but useful later.
- Read `G44a-d` (industry of employment) for ANZSIC code aggregation.

If the column codes don't match what's described above, **stop and update this plan** before writing the loader.

### 0.2 Confirm Postgres is available locally

```powershell
# Either: existing Postgres install
psql --version

# Or: spin one up via Docker
docker run --name suburb-intel-pg -e POSTGRES_PASSWORD=census -e POSTGRES_USER=sa2 -e POSTGRES_DB=suburb_intel -p 5432:5432 -d postgres:16
```

Connection string for `.env`:

```
DATABASE_URL=postgresql+asyncpg://sa2:census@localhost:5432/suburb_intel
```

---

## 1. Schema deltas

Current `abs_census_metrics` table doesn't store everything the scoring engine reads. Two fields are hardcoded TODOs in `backend/app/api/suburb.py::_build_features`:

```python
pop_growth = 35.0          # TODO
young_population_pct = 32.0 # TODO
```

These need real columns. Also add SA3 + SA4 codes for future hierarchical aggregation.

### Migration in `backend/app/db/models.py`

Add to `ABSCEntensMetrics`:

```python
pop_growth_5yr = Column(Float, nullable=True, comment="Population growth % between 2016 and 2021 Census")
young_population_pct = Column(Float, nullable=True, comment="% of population aged 15-34")
```

Add to `SA2Region`:

```python
sa3_code = Column(Text, nullable=True)
sa3_name = Column(Text, nullable=True)
sa4_code = Column(Text, nullable=True)
sa4_name = Column(Text, nullable=True)
gcc_code = Column(Text, nullable=True)  # Greater Capital City Statistical Area
gcc_name = Column(Text, nullable=True)
area_sqkm = Column(Float, nullable=True)
```

### Indexes worth adding

```python
# In SA2Region
__table_args__ = (Index("ix_sa2_regions_name", "sa2_name"),)

# In SuburbScore
__table_args__ = (Index("ix_suburb_scores_investment_desc", "investment_score"),)
```

### Migration approach

For Phase A, skip Alembic. Drop and recreate the schema via `Base.metadata.create_all()` since we're nuking and reloading anyway. **Add Alembic in Phase B** when we care about non-destructive migrations.

---

## 2. SQLite → Postgres migration

`backend/app/db/session.py` already supports both via URL scheme detection. Steps:

1. Update `backend/.env` to the Postgres URL (above).
2. Install missing deps if needed: `asyncpg` is already in `requirements.txt`.
3. Run the bootstrap:
   ```python
   # backend/scripts/init_pg.py
   import asyncio
   from app.db.session import init_models
   asyncio.run(init_models())
   ```
4. Verify connection:
   ```powershell
   cd backend
   .\.venv\Scripts\Activate.ps1
   python -m scripts.init_pg
   ```
5. Confirm tables exist:
   ```powershell
   psql -U sa2 -d suburb_intel -c "\dt"
   ```

**Backwards compat:** tests should continue to use SQLite in-memory via conftest (already configured). Production / dev use Postgres. The same code path serves both.

---

## 3. DataPack loader

New file: `backend/app/ingestion/abs_datapack_loader.py`. The existing `abs_loader.py` is API-shaped (carryover from earlier code) — leave it for reference but don't try to extend it. Write fresh.

### Contract

```python
def load_datapack(
    datapack_zip: Path,
    db: Session,
    *,
    year: int = 2021,
    states: list[str] | None = None,  # filter to specific states, default all
    truncate_first: bool = False,
) -> LoadReport:
    """Read a Census 2021 GCP DataPack zip and upsert SA2Region + ABSCEntensMetrics rows.

    Returns counts of: regions_inserted, regions_updated, metrics_inserted,
    metrics_updated, rows_skipped (with reasons).
    """
```

Reasonable to run via a CLI entrypoint:

```python
# backend/app/ingestion/__main__.py
if __name__ == "__main__":
    import argparse, asyncio
    p = argparse.ArgumentParser()
    p.add_argument("zip", type=Path)
    p.add_argument("--year", type=int, default=2021)
    args = p.parse_args()
    asyncio.run(load_datapack(args.zip, ...))
```

So you can run:

```powershell
python -m app.ingestion C:\path\to\2021_GCP_AllGeographies_for_AUS_short-header.zip
```

### Pseudocode

```python
def load_datapack(zip_path: Path, db: Session, *, year: int = 2021):
    with zipfile.ZipFile(zip_path) as zf:
        # 1. Read the SA2 geography lookup
        geog_csv = next(n for n in zf.namelist() if "SA2_2021_AUST" in n and n.endswith(".csv"))
        regions = pd.read_csv(zf.open(geog_csv), dtype={"SA2_CODE_2021": str, "SA3_CODE_2021": str, ...})

        # 2. Upsert SA2Region rows
        for row in regions.itertuples():
            db.merge(SA2Region(
                sa2_code=row.SA2_CODE_2021,
                sa2_name=row.SA2_NAME_2021,
                state=row.STATE_NAME_2021_SHORT,
                sa3_code=row.SA3_CODE_2021,
                ...
            ))

        # 3. Load Census metrics from each relevant table
        g01 = pd.read_csv(zf.open(<G01 path>), dtype={"SA2_CODE_2021": str})
        g17 = pd.read_csv(zf.open(<G17 path>), dtype={"SA2_CODE_2021": str})
        g33 = pd.read_csv(zf.open(<G33 path>), dtype={"SA2_CODE_2021": str})
        g44 = pd.read_csv(zf.open(<G44 path>), dtype={"SA2_CODE_2021": str})

        # 4. For each SA2, build the metrics row
        for sa2_code in g01["SA2_CODE_2021"].unique():
            metrics = ABSCEntensMetrics(
                sa2_code=sa2_code,
                year=year,
                population=int(g01.loc[g01.SA2_CODE_2021 == sa2_code, "Tot_P_P"].iloc[0]),
                median_age=float(g01.loc[..., "Median_age_persons"].iloc[0]),
                median_income=int(g17.loc[..., <correct column>].iloc[0]),
                renters_pct=_compute_renters_pct(g33, sa2_code),
                owners_pct=_compute_owners_pct(g33, sa2_code),
                young_population_pct=_compute_young_pct(g01, sa2_code),
                industry_profile=_compute_industry_profile(g44, sa2_code),
                # pop_growth_5yr filled in by a second pass after 2016 data is loaded
            )
            db.merge(metrics)
        db.commit()
```

### Helper functions to write

- `_compute_young_pct(g01_df, sa2_code) -> float` — sum age bands 15-19, 20-24, 25-29, 30-34 from G01, divide by total population. Cap at 100.
- `_compute_renters_pct(g33_df, sa2_code) -> float` — sum "rented" tenure codes / total occupied dwellings * 100.
- `_compute_owners_pct(g33_df, sa2_code) -> float` — sum "owned outright" + "owned with mortgage" / total.
- `_compute_industry_profile(g44_df, sa2_code) -> dict[str, float]` — group ANZSIC 1-digit codes into your existing buckets (`tech`, `finance`, `retail`, `healthcare`, `education`, `manufacturing`, `construction`, `services`) and return as proportion of total employed (sums to ≤ 1.0). Map:
  - A (Agriculture) → `agriculture`
  - C (Manufacturing) → `manufacturing`
  - E (Construction) → `construction`
  - G/H (Retail/Accommodation) → `retail`
  - J (Information Media) + M (Professional Services) → `tech`
  - K (Financial Services) → `finance`
  - P (Education) → `education`
  - Q (Healthcare) → `healthcare`
  - Other → `services`

### Optional: pop_growth from Census 2016

If you have a 2016 DataPack handy:
1. Load it with `year=2016` (rows go into the same `abs_census_metrics` table, distinguished by year PK).
2. After both 2016 and 2021 are loaded, run a second pass that for each SA2 computes `(pop_2021 - pop_2016) / pop_2016 * 100` and writes it to the 2021 row's `pop_growth_5yr`.

If 2016 isn't loaded, leave `pop_growth_5yr` NULL and have `suburb.py::_build_features` fall back to a sensible default (or 0).

---

## 4. Score backfill job

New file: `backend/app/jobs/backfill_scores.py`. Computes and stores `SuburbScore` rows for every SA2 with census data, so `/rankings/` and other ranked queries don't recompute on-request.

```python
async def backfill_scores(db: AsyncSession, *, year: int = 2021) -> BackfillReport:
    """For every SA2Region with a matching ABSCEntensMetrics row for `year`,
    compute the investment score and upsert SuburbScore."""
    stmt = (
        select(SA2Region, ABSCEntensMetrics)
        .join(ABSCEntensMetrics, ...)
        .where(ABSCEntensMetrics.year == year)
    )
    rows = (await db.execute(stmt)).all()

    for region, census in rows:
        projects = await _fetch_linked_projects(db, region.sa2_code)
        features = _build_features(census, projects)  # reuse from suburb.py
        scores = calculate_investment_score(features)
        await db.merge(SuburbScore(
            sa2_code=region.sa2_code,
            **scores,
            updated_at=datetime.now(timezone.utc),
        ))
    await db.commit()
```

Run via:

```powershell
python -m app.jobs.backfill_scores
```

Extract `_build_features` and `_fetch_linked_projects` from `backend/app/api/suburb.py` into a shared module (`backend/app/core/features.py` or `app/services/scoring_service.py`) so both the endpoint and the backfill job call the same code.

---

## 5. Endpoint wiring updates

### `rankings.py` — drop the mock data

Current code uses `random.choice` to fabricate 20 fake suburbs. Replace with a real query against `suburb_scores`:

```python
@router.get("/")
async def get_rankings(
    limit: int = Query(25, ge=10, le=200),
    score_type: str = Query("investment_score"),
    db: AsyncSession = Depends(get_db),
):
    valid = {"investment_score", "demographic_score", "economic_score",
             "housing_pressure_score", "resilience_score", "gov_investment_score"}
    if score_type not in valid:
        raise HTTPException(400, f"score_type must be one of {valid}")

    order_col = getattr(SuburbScore, score_type)
    stmt = (
        select(SuburbScore, SA2Region.sa2_name, SA2Region.state)
        .join(SA2Region, SA2Region.sa2_code == SuburbScore.sa2_code)
        .order_by(order_col.desc().nulls_last())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return {
        "score_type": score_type,
        "count": len(rows),
        "rankings": [
            {
                "rank": i + 1,
                "sa2_code": s.sa2_code,
                "sa2_name": name,
                "state": state,
                **{c: getattr(s, c) for c in valid},
            }
            for i, (s, name, state) in enumerate(rows)
        ],
    }
```

### `search.py::get_top_suburbs` — same treatment

Currently uses `random.uniform`. Replace with a query against `suburb_scores` ordered by `by` column.

---

## 6. Tests to add

In `backend/tests/`:

### `test_datapack_loader.py`
Build a minimal synthetic DataPack zip in a fixture (a couple of dummy SA2 rows in each CSV) and assert:
- All expected SA2 regions inserted.
- All metrics rows inserted with correct values.
- Repeated runs are idempotent (no duplicates).
- Industry-profile fractions sum to ~1.0.
- young_population_pct is 0-100.

### `test_backfill_scores.py`
- Seed 5 SA2s with census data.
- Run backfill.
- Assert every seeded SA2 has a `SuburbScore` row.
- Assert every sub-score is within 0-100.
- Re-run backfill, assert `updated_at` advanced.

### `test_rankings_endpoint.py`
- Seed 10 SA2s with varying `investment_score` values.
- Call `/rankings/?limit=5`.
- Assert returned ranks are in descending order.
- Assert the top score in the response matches the max in the seed.
- Call with `score_type=demographic_score` — assert ordering changes appropriately.
- Call with `score_type=bogus` — assert 400.

### Update existing tests
- `conftest.py` should seed at least one `SuburbScore` row so the new rankings tests have data.

---

## 7. Success criteria

Phase A is done when **all** of these are true:

- [ ] `python -m app.ingestion <real_datapack.zip>` runs to completion against the real ABS Census 2021 GCP DataPack, populating ~2,500+ SA2 rows in Postgres.
- [ ] `python -m app.jobs.backfill_scores` populates every SA2 with a `SuburbScore` row in <2 minutes.
- [ ] `GET /suburb/47002` returns Chermside data sourced from real Census, not seeded fixtures. `pop_growth_5yr` is non-null if 2016 was loaded.
- [ ] `GET /rankings/?limit=10` returns the actual 10 highest-investment-score suburbs from the full population, ordered correctly.
- [ ] `GET /search/?query=Bondi` returns the real Bondi Beach SA2 (and any other "Bondi" matches), not from the 3 seeded rows.
- [ ] `pytest -q` reports **all green**, including the new loader/backfill/rankings tests.
- [ ] Backend boots cleanly against the Postgres URL.
- [ ] No score outside the 0-100 contract for any SA2 in Postgres (`SELECT * FROM suburb_scores WHERE NOT (investment_score BETWEEN 0 AND 100)` returns no rows).

---

## 8. Explicitly out of scope for Phase A

- Frontend `SearchPage` / `RankingsPage` wiring (Phase B).
- OSM Overpass live integration / amenity scoring (Phase C).
- Infrastructure Australia bulk load (Phase C).
- Alembic migration tooling (Phase B).
- Rate limiter rewrite (Phase C).
- Stripe paywall (Phase C).
- Auth (Phase D).
- Deployment (Docker compose, CI/CD) (Phase D).
- Renaming `ABSCEntensMetrics` class typo (cosmetic, do whenever).
- Refactoring the unused `services/suburb_service.py` (its own task).

---

## 9. Suggested commit / PR structure

Three smaller PRs rather than one giant one. Each independently mergeable, each on top of the previous.

1. **PR A1 — Postgres + schema migration**
   - Update `.env` to Postgres URL (commented; keep SQLite as default for tests)
   - Add new columns to `ABSCEntensMetrics` and `SA2Region` (`pop_growth_5yr`, `young_population_pct`, `sa3_*`, etc.)
   - Add indexes
   - Add `backend/scripts/init_pg.py`
   - Update README with Postgres setup steps
   - Tests: nothing functional yet, just confirm `init_models()` runs against both backends

2. **PR A2 — DataPack loader + ingestion CLI**
   - New `backend/app/ingestion/abs_datapack_loader.py`
   - CLI entrypoint via `backend/app/ingestion/__main__.py`
   - Helper functions for industry/age/tenure
   - Test fixture: a tiny synthetic DataPack zip
   - `test_datapack_loader.py`
   - Update docs with run instructions

3. **PR A3 — Backfill + rankings rewrite**
   - New `backend/app/jobs/backfill_scores.py` + CLI
   - Extract shared `_build_features` / `_fetch_linked_projects` into a service module
   - Rewrite `rankings.py` and `search.py::get_top_suburbs` to query real data
   - `test_backfill_scores.py`, `test_rankings_endpoint.py`
   - Update `conftest.py` to seed a `SuburbScore` row

---

## 10. Resources

- ABS DataPacks landing: https://www.abs.gov.au/census/find-census-data/datapacks
- ABS DataPack metadata explainer: https://www.abs.gov.au/census/guide-census-data/about-census-tools/datapacks
- SA2 geography (ASGS Edition 3): https://www.abs.gov.au/statistics/standards/australian-statistical-geography-standard-asgs-edition-3
- ANZSIC industry codes: https://www.abs.gov.au/ausstats/abs@.nsf/mf/1292.0
- Postgres Docker image: https://hub.docker.com/_/postgres
- pandas chunked CSV reading: https://pandas.pydata.org/docs/user_guide/io.html#io-chunking
- SQLAlchemy 2.x async patterns: https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html

---

## 11. Handoff notes

- Working tree: `C:\Users\nghil\Projects\Hermes\suburb-intel`. Use Claude Code, not Cowork.
- Branch convention: `feat/phase-a-N-description` (e.g. `feat/phase-a-1-postgres-schema`).
- Python venv: `backend/.venv` (Python 3.11, project-local). Activate before running any Python: `.\backend\.venv\Scripts\Activate.ps1`.
- Memory file: `Frontier/memory.md` in this OneDrive folder. Update it at the start and end of each Code session per Rogue Night protocol.
- When a PR is ready, the same flow applies: open the PR on GitHub, Linh reviews, merge. No client-facing output goes out without Linh's review.
- Previous PRs to read for context: #2 (`Fix endpoint bugs + frontend TS errors`) and #3 (`Fix suburb endpoint, clamp economic score, wire SuburbPage to API`).
