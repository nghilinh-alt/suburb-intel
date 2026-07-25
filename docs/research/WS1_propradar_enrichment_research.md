# Workstream 1 — PropRadar Data Enrichment Research

**Prepared for:** Suburb Intel improvement plan (Rogue Night consulting)
**Date:** 2026-07-10
**Status:** Research complete — feeds the prioritised plan. **DECISION (2026-07-10, Linh): not upgrading the PropRadar API. Stay on Hobby ($39/mo).** All momentum/enrichment work must therefore come from Hobby-tier endpoints + free derivations.
**Sources:** PropRadar developer site + live docs (fetched 2026-07-10); Suburb Intel codebase (`suburb_market_stats_loader.py`, `propradar_sold_loader.py`, `db/models.py`).

---

## TL;DR

**Decision taken:** we are **not upgrading** the PropRadar plan — staying on Hobby ($39/mo). PropRadar's paid "hotspot momentum" stack (`market_cycle`, `price_history`, `heat_history`, supply/demand, auction premium, native rankings — all bundled in the Pro tier, $399/mo) is therefore **out of scope.** The momentum signal this product needs must be built from Hobby-tier data + our own derivations.

The good news: most of that signal is *derivable now, for free* from data we already hold (§4). In particular, the `/listings` (current for-sale) endpoint the brief flagged as untapped is **not gated** — available on Hobby right now — and our monthly snapshots are already accumulating a home-grown heat/price time series at zero cost. With Pro ruled out, these free derivations move from "de-risking step" to **the whole game.**

---

## 1. The developer API tier map (confirmed, with prices)

PropRadar runs a **separate developer API** product from its consumer SaaS. Pricing (monthly, AUD):

| Tier | Price | Calls/mo | What it unlocks beyond the tier below |
|------|-------|----------|----------------------------------------|
| Free | $0 | 50 | Core read endpoints |
| **Hobby (current)** | **$39** | **5,000** | Year built, sold days-on-market, higher burst |
| Starter | $99 | 20,000 | Bulk (2/req), recently-modified feed, **suburb livability signals (walk/transit, crime, schools)** |
| **Pro** | **$399** | **100,000** | **investment analysis, `market_cycle`, `price_history`, `heat_history`, supply/demand, rent trends, auction premium, valuation-agreement signal, property analytics block, native suburb rankings** |
| Growth | $799 | 300,000 | Regions macro endpoints (city/state/national), bulk 5/req |
| Scale | $1,499 | 1,000,000 | Bulk 10/req, higher concurrency |

The brief's live-tested 403s on `market_cycle` / `price_history` / `heat_history` are confirmed: all three are **Pro+**. The brief's instinct that these are "exactly the hotspot momentum signal this product needs" is correct — and they're conveniently bundled in a single tier.

## 2. Endpoint inventory — what's gated vs. available at our current tier

**Available NOW on Hobby (no upgrade needed):**

- `/v1/suburbs/{state}/{suburb}` — in use (medians, growth, yields, market_dynamics, demographics). *Pro+ would add supply/demand, rent trends, auction premium blocks to this same call.*
- `/v1/suburbs/{state}/{suburb}/sold` — in use (paginated sold listings).
- **`/v1/suburbs/{state}/{suburb}/listings` — UNTAPPED, ungated.** Current for-sale listings. Directly serves the "what's for sale" brief.
- `/v1/comparables` — recent sold comparables, filterable by radius / time / beds / type.
- `/v1/properties/{id}` (+ `/search`, `/history`, `/sold_summary`, `/similar`, `/nearby`, `/psp_with_confidence`) — property-level lookups. Useful but keyed by `property_id` (needs an address→id resolve), so secondary to our suburb-centric model.

**Gated (require an upgrade):**

| Endpoint | Tier | Relevance to mission |
|----------|------|----------------------|
| `/suburbs/.../market_cycle` | Pro | **High** — 2-axis phase/momentum/volatility (the "property clock" signal) |
| `/suburbs/.../heat_history` | Pro | **High** — daily market-heat time series |
| `/suburbs/.../price_history` | Pro | **High** — annual price/rent/yield time series |
| `/suburbs/rankings` | Pro | **High** — native suburb rankings by yield/growth/heat/price/DOM (could power our Rankings page) |
| supply/demand + rent trends + auction premium (blocks on the suburb call) | Pro | Medium-High |
| `/properties/{id}/investment_analysis` | Pro | Medium |
| `/properties/recently-modified` | Starter | Medium — incremental-sync feed, cheaper refreshes |
| suburb livability (walk/transit, crime, schools) | Starter | Medium — lifestyle, not momentum |
| `/regions`, `/regions/{slug}` | Growth | Low-Medium — macro context |

**New endpoints the brief didn't mention that are worth noting:** `/comparables`, `/similar`, `/psp_with_confidence`, `/history`, `/sold_summary` (all Hobby), and `/suburbs/rankings` (Pro — a drop-in for our Rankings page).

## 3. Correcting one framing in the brief: we already hold a heat *snapshot*

The brief treats "market heat" as gated. Precise picture: the **daily heat time series** (`heat_history`) is Pro+, but a **current heat_score snapshot** (house + unit) is *already in the Hobby suburb payload and already stored* in `suburb_market_stats` (`heat_score_house`, `heat_score_unit`), alongside `sales_12mo`, days-on-market, vacancy, inventory-months, stock-on-market%, and sold-vs-asking%. So we already have a point-in-time heat reading — we just lack PropRadar's history of it.

## 4. Quick wins — derivable now, zero extra API cost

Ordered by leverage:

1. **Ingest `/listings` (current for-sale).** Ungated, untapped, and explicitly in the brief. Unlocks live stock levels, asking prices, live DOM, list-vs-sold spread, and stock-on-market trend — all inputs professional analysts check first (see WS2).

2. **Our own accumulating time series — the sleeper win.** Each monthly refresh inserts a *new* `suburb_market_stats` row keyed by `YYYY-MM` (the `id` embeds the period; re-runs next month insert rather than overwrite). This means Suburb Intel is **already building its own longitudinal series of heat_score, medians, sales_12mo, DOM and vacancy — for free.** Once 2–3 months have accumulated, surfacing this as a trend line is a home-grown substitute for the gated `price_history` / `heat_history`. This needs no new data, just a chart and a query.

3. **Sale velocity** — sales-per-month-per-suburb computed from our own `sold_date` rows. Classic early heat/momentum proxy; no API cost.

4. **Own growth backfill** — PropRadar's growth fields are null for 40–59% of suburbs. Compute suburb growth from raw sold prices over time as a fallback/cross-check to fill those gaps.

5. **Supply-scarcity signal.** Combine PropRadar's `stock_on_market_pct` + `inventory_months` (Hobby) with our **already-ingested building-approvals data** to build a BA-ratio-style scarcity metric. This mirrors the #1 filter professional buyers agents use (WS2, HtAG "supply scarcity is the non-negotiable filter"). Buildable now.

6. **Similar-suburb clustering** off existing yield/growth/price fields — as the brief suggested.

## 5. Known permanent gaps (don't re-chase)

- **No land size, anywhere.** Confirmed absent across 13k+ sold rows; `land_size_sqm` is kept null in the model for a future non-PropRadar source. Price-per-sqm is not achievable via PropRadar.
- **No mix-adjusted "typical price."** PropRadar exposes medians only. Competitors (HtAG) argue median is unreliable for investment decisions and use a mix-adjusted typical price; we can't replicate that from PropRadar. Note as a limitation, not a task.

## 6. The Pro-upgrade decision — RESOLVED (no upgrade)

**Decision (2026-07-10, Linh): not upgrading. Staying on Hobby ($39/mo).**

For the record, the trade that was declined: Hobby $39 → Pro $399 = +$360/mo (~$4,320/yr) would have unlocked the market-cycle/heat/price-history stack, supply/demand + auction-premium blocks, and a native suburb-rankings endpoint. (Starter $99 was never the momentum tier — it only adds livability/crime/school signals.)

**Implication for the plan:** the momentum/timing metric — WS2's single biggest content gap — must be built in-house from Hobby-tier inputs. That means leaning fully on §4:

- Sale velocity (#3) and our own growth backfill (#4) become the **primary** momentum signals, not fallbacks.
- The self-accumulating monthly snapshot series (#2) becomes our substitute for `price_history`/`heat_history` — worth ensuring the monthly refresh runs reliably so the history compounds.
- The supply-scarcity metric (#5, PropRadar stock/inventory + our ABS building-approvals field) stands in for the Pro supply/demand block.

None of these need a plan change or new spend. They do need build time — see the prioritised plan.

---

## Handoff

**Next:** WS2 competitive research (`docs/research/WS2_competitive_research.md`) is complete; both feed the prioritised improvement plan (to be assembled next session per "research first, plan next"). The plan should treat §4 quick wins as near-term, and §6 Pro upgrade as the flagged bigger bet.
