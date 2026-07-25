# Suburb Intel — Implementation Plan (for Claude Code)

**Audience:** Claude Code, working directly in this repo.
**Author:** Rogue Night consulting, 2026-07-10. Backed by `docs/research/WS1_propradar_enrichment_research.md` and `docs/research/WS2_competitive_research.md` — read those two first for the *why* behind each task.
**Mission reminder:** the product's one job is to help buyers agents **find the next hotspot before it's obvious.** Prioritise signal (momentum, supply/demand pressure, what's for sale) over encyclopedic breadth.

---

## Guardrails — read before writing any code

1. **Do NOT upgrade the PropRadar plan and do NOT call gated endpoints.** Our key is on the Hobby tier and these return `403`: `market_cycle`, `price_history`, `heat_history`, `/suburbs/rankings`, `/regions`, `/properties/{id}/investment_analysis`, `/properties/recently-modified`, `bulk`. **Only these are available:** `GET /v1/suburbs/{state}/{suburb}`, `GET /v1/suburbs/{state}/{suburb}/sold`, and `GET /v1/suburbs/{state}/{suburb}/listings` (new — ungated). Everything "momentum" must be **derived in-house** from Hobby-tier data.
2. **Do NOT delete sections, endpoints, or DB columns.** The census-lifecycle work is **hide reversibly via config**, never `DROP`/delete. Hidden data must come back by flipping one setting.
3. **Preserve the `(sa2_code, year)` keying** on `abs_census_metrics`. Swapping in 2025 Census later must stay mechanical — no schema changes that break year-keying.
4. **Two sections are Linh's call, not yours: "Community & Socio-Economic Profile" (SEIFA) and "Government Investment" (iPAMS).** Provisional decision, evidence-backed (see WS2 §5): **keep both, reframe both, delete neither.** Do not remove them. If a task seems to require removal, stop and flag it.
5. **Match the surrounding code.** Backend loaders follow the `<name>_loader.py` (logic) + `<name>.py` (CLI `__main__`) pattern in `backend/app/ingestion/`, use `httpx`, `X-API-Key`, `load_dotenv()` first, and reuse `_split_suburb_parts` / `_STATE_MAP` from `propradar_sold_loader.py`. Frontend pages use **inline `style={{}}` + `src/lib/theme.ts` tokens** (Tailwind v4 is installed but current pages don't use it — match the file you're in).
6. **Definition of done per phase:** `cd backend && pytest` passes, and `cd frontend && npm run build` passes. Add/extend tests for every new loader and derivation (`backend/tests/`).

---

## Repo orientation

| Layer | Location | Notes |
|-------|----------|-------|
| Ingestion loaders | `backend/app/ingestion/` | `propradar_sold_loader.py`, `suburb_market_stats_loader.py` are the PropRadar patterns to copy |
| Models | `backend/app/db/models.py` | `PropertySale`, `SuburbMarketStats`, `ABSCensusMetrics`, `InfrastructureProject` |
| API | `backend/app/api/` | `suburb.py` (report assembly; `census_year` hardcoded `2021` here), `rankings.py`, `search.py` |
| Core logic | `backend/app/core/` | `scoring.py` (composite score) |
| Frontend pages | `frontend/src/pages/` | `SearchPage.tsx`, `RankingsPage.tsx`, `SuburbPage.tsx` (flagship, ~1,400 lines; has the `Section` component) |
| Frontend charts | `frontend/src/components/Charts.tsx` | hand-rolled SVG bar/donut/line — extend here |
| Theme | `frontend/src/lib/theme.ts` | colour + spacing tokens |

Data already in the dev DB: `suburb_market_stats` (1,554 rows, one monthly snapshot), `property_sales` (13,209 sold rows), `infrastructure_projects` (1,182 iPAMS), plus `abs_census_metrics` incl. `building_approvals_1yr` and SEIFA deciles.

---

## Phase 1 — Free PropRadar-derived data (backend). *Highest priority.*

This phase creates the raw material for the momentum signal. No plan upgrade, no gated calls.

### Task 1.1 — Ingest current for-sale listings (`/listings`)
- **Why:** "what's for sale" is in the brief; endpoint is ungated and untapped (WS1 §2, §4.1).
- **Build:** `backend/app/ingestion/current_listings_loader.py` + CLI `current_listings.py`, copying `propradar_sold_loader.py` structure (offset/limit pagination via `pagination.next_offset`, `_split_suburb_parts`, `_STATE_MAP`, monthly-freshness id keying, `--state/--suburb/--sa2-codes/--max-pages/--force`). New model `CurrentListing` (fields: id, sa2_code, address, bedrooms, bathrooms, parking, property_type, asking_price, listed_date, days_on_market, fetched period). Endpoint: `GET /v1/suburbs/{state}/{suburb}/listings`.
- **Acceptance:** loader fetches and upserts for a pilot suburb (e.g. `--state QLD --suburb Cleveland`); `pytest` covers response parsing with a fixture; no calls to gated endpoints.

### Task 1.2 — Sale velocity (momentum proxy)
- **Why:** WS1 §4.3 — sales/month/suburb from our own `property_sales.sold_date` is a classic early-heat signal, now a **primary** momentum input (not a fallback), since Pro is off the table.
- **Build:** `backend/app/core/momentum.py` with a function computing monthly sales counts per SA2 from `sold_date`, plus a rolling trend (e.g. last-3-months vs prior-3-months % change). Expose in the suburb report (`suburb.py`) and make available to rankings.
- **Acceptance:** unit test on a synthetic set of sales rows; values surface in the `/suburb` API response.

### Task 1.3 — Own growth backfill
- **Why:** WS1 §4.4 — PropRadar growth fields are null for 40–59% of suburbs.
- **Build:** in `core/momentum.py` (or `core/growth.py`), compute suburb median-price growth from raw `property_sales` over time; use as a fallback wherever `SuburbMarketStats.growth_*` is null, clearly labelled as "derived" in the API payload so the UI can distinguish it.
- **Acceptance:** suburbs with null PropRadar growth now return a derived growth value where enough sold data exists; test covers the null-fallback branch.

### Task 1.4 — Supply-scarcity metric
- **Why:** WS2 §2 — supply scarcity is the "non-negotiable" filter professionals use.
- **Build:** combine `SuburbMarketStats.stock_on_market_pct` + `inventory_months` (Hobby-tier, already stored) with `ABSCensusMetrics.building_approvals_1yr` into a 0–100 scarcity score (lower supply → higher score). Add to `core/scoring.py` or `core/momentum.py`; expose in suburb + rankings.
- **Acceptance:** score computed for suburbs with the inputs; documented weighting; test.

### Task 1.5 — In-house momentum/timing composite (the headline gap)
- **Why:** WS2 §2 — every serious competitor leads with a timing signal (HtAG GRC, DSR MCT) and Suburb Intel has none. This is the single biggest content gap. We build a simplified version from 1.2 + 1.3 + scarcity + the stored `heat_score` snapshot.
- **Build:** a "Momentum" read in `core/momentum.py` that classifies each suburb as accelerating / steady / cooling from: growth-rate trend (1.3), sale-velocity trend (1.2), supply-scarcity (1.4), and `heat_score_house/unit`. Keep it explainable (return the component contributions, not just a label). Expose as a first-class field on suburb + rankings responses.
- **Acceptance:** returns a phase/label + component breakdown per suburb; test covers accelerating vs cooling fixtures.
- **Note:** the self-accumulating monthly `suburb_market_stats` series is our substitute for `price_history`/`heat_history`. Ensure the monthly refresh (`python -m app.ingestion.suburb_market_stats`) is documented as a recurring job so history compounds — flag to Linh for scheduling; do not build a scheduler here.

---

## Phase 2 — Surface momentum in the product (frontend + rankings)

### Task 2.1 — Rankings page reframed around pressure
- Add momentum (1.5) and supply-scarcity (1.4) as sortable columns/sorts in `RankingsPage.tsx` + `rankings.py`. Reframe the existing composite around supply/demand pressure + acceleration rather than static desirability. Show an acceleration indicator (▲/▼) per row.

### Task 2.2 — "Momentum & Timing" section on the Suburb page
- New `Section` near the top of `SuburbPage.tsx` (above the census sections): momentum label + component breakdown (1.5), sale-velocity sparkline (1.2), growth-acceleration, scarcity score (1.4), heat snapshot. Sparklines read from the accumulating monthly snapshots.

### Task 2.3 — "What's for sale" in Housing Market
- Surface current listings (1.1) in the existing Housing Market section: count on market, asking-price distribution, live days-on-market, list-vs-sold spread.

---

## Phase 3 — UI/UX: "data-dense but guided" (all three pages)

Research-backed target (WS2 §4): denser and more scannable than today, but every dense block led by a one-line plain-English read, definitions on hover. Not a raw terminal; not a consumer brochure.

### Task 3.1 — Shared primitives + Context Ruler
- Extend `Charts.tsx` with a **Context Ruler** (a stat's value placed on a scale vs the national average — DSR's signature device; WS2 §3) and a **Sparkline**. Add reusable `Stat`, `SectionSummary` (plain-English line), and `MetricWithInfo` (hover definition) components. Extend `theme.ts` with monospace-numeric + density tokens.

### Task 3.2 — Plain-English-first + hover definitions
- Each `Section` gains a one-line auto-generated interpretation at the top (e.g. "Supply is tight and demand is accelerating"). Extend the existing info-tooltip pattern (the `title=` tooltip around `SuburbPage.tsx:350`) to every metric with a short definition.

### Task 3.3 — Density pass across pages
- Apply monospace numerics, tighter grid, and more-metrics-visible-without-clicks to `SearchPage.tsx`, `RankingsPage.tsx`, `SuburbPage.tsx`. Keep the inline-style + theme approach unless you deliberately introduce a token layer (if so, do it once in `theme.ts` and apply consistently).

### Task 3.4 — Funnel framing for Search & Rankings
- Frame the three pages as the analyst funnel (WS2 §2): Search = macro filter (add momentum + scarcity filters), Rankings = shortlist (momentum/scarcity columns from 2.1), Suburb = deep-dive. Light copy + affordances, not a rebuild.

---

## Phase 4 — Data lifecycle: hide stale 2021 Census (reversible)

### Task 4.1 — Config-gated hiding of census-sourced sections
- **Add a single config flag** (e.g. `SHOW_CENSUS_SECTIONS` / a `LATEST_CENSUS_YEAR` constant) read by `suburb.py` and passed to the frontend. When census data is stale (2021 and flag off), **hide** these census-sourced sections/fields, don't delete: **Demographics, Economy, Housing**, the census parts of **Investment Outlook** (`pop_growth_5yr`), **Transport** (commute-mode / zero-car), and the **regional comparison** census stats. Keep the non-census parts of those sections visible (e.g. Transport's live GTFS stop counts stay).
- The model is already `(sa2_code, year)`-keyed and `census_year` is hardcoded `2021` in `suburb.py` — wire the flag there so flipping to 2025 later just changes the constant.
- **Acceptance:** flag off → census sections hidden across the Suburb page; flag on → everything returns unchanged. No data deleted.

### Task 4.2 — SEIFA "Community & Socio-Economic Profile" — KEEP + reframe (do not delete)
- Provisional decision (Linh to confirm): **keep visible.** Reframe from a "nice neighbourhood" score to a **growth-stability filter** (WS2 §5): lead with the IRSAD decile framed as demand stability, note the mid-decile (5–7) sweet spot, optionally pair with owner-occupier % (from PropRadar). **Note:** SEIFA 2021 is the *current* SEIFA release (SEIFA only publishes each census cycle), so it is not "stale" like the demographic snapshots — do not hide it under the 4.1 flag.

### Task 4.3 — Government Investment (iPAMS) — KEEP + reframe (do not delete)
- Provisional decision (Linh to confirm): **keep visible.** Infrastructure pipeline is a Step-1 macro hotspot filter for buyers agents (WS2 §5). Reframe the section toward a forward signal: proximity + dollar value + status + timing, not a generic project list. Data is live/free (1,182 iPAMS projects) — not census, not affected by 4.1.

---

## Suggested order & sequencing

Phase 1 → Phase 2 → Phase 4 → Phase 3. Rationale: Phase 1 unlocks the signal, Phase 2 makes it visible (the mission-critical win), Phase 4 is low-risk config work that declutters, and Phase 3 (the largest, most subjective) comes last once the new data exists to design around. Phases 1 and 4 are independent and can run in parallel.

**Before starting each phase:** confirm with Linh if it touches Task 4.2 or 4.3 (her call), or if any step appears to need a plan upgrade or a deletion (it shouldn't — re-read Guardrails).
