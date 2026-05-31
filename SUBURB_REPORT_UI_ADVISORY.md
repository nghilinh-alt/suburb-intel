# Suburb Report — UI & Data Advisory

**Prepared by:** Frontier (Rogue Night)
**For:** Linh Nghi (review before any client/handoff)
**Date:** 2026-05-31
**Status:** DRAFT — flagged for Linh's review
**Source files reviewed:**
- `frontend/src/pages/SuburbPage.tsx`
- `frontend/src/components/{ScoreCard,Breakdown,Paywall,Layout}.tsx`
- `backend/app/api/suburb.py`
- `backend/app/db/models.py`
- `backend/app/core/{scoring,gov_score,utils}.py`

---

## 1. TL;DR

The current Suburb Report renders six score cards, a one-line insight, and chip tags — pulled from **hardcoded mock values**, not the API. It looks like a dashboard prototype, but for a property investor it's missing the entire "would I actually buy here?" layer: prices, yields, rents, growth trends, vacancy, and peer context. Every comparable site (YIP, SmartPropertyInvestment, Launch Finance) leads with **price + yield + growth + vacancy**, not abstract scores.

Two priorities:

1. **Wire the page to the live API** (today it ignores `useParams` for everything except the SA2 code label).
2. **Surface investor-grade fundamentals** — most of which we either already have in the DB (and don't show) or can derive without new ingestion.

---

## 2. Current State Audit

### What the page renders today
| Section | Source | Issue |
|---|---|---|
| Suburb name | Hardcoded `"Chermside QLD"` | Doesn't use `sa2Code` to fetch real data |
| 6 score cards | Hardcoded `"78"`, `"82"`, etc. | Never calls `/suburb/{sa2_code}` |
| Key Insight | Hardcoded sentence | API actually returns a real `insight` string — unused |
| Risk Flags | 2 hardcoded chips | API returns real `risk_flags` array — unused |
| Tags | 2 hardcoded chips | API returns real `tags` — unused |
| Paywall CTA | Hardcoded $9 button | No payment integration |

### What the backend already returns (and we ignore)
`GET /suburb/{sa2_code}` returns: `sa2_name`, `state`, full `scores` object (6 fields), `insight`, `risk_flags`, `tags`, `census_year`, `population`, `median_income`, `median_age`. **None of this is rendered.**

### What's in the DB but never surfaced anywhere
- `ABSCensusMetrics.industry_profile` (JSON) — could power an occupation/industry mix chart
- `ABSCensusMetrics.renters_pct` / `owners_pct` — basic tenure split
- `InfrastructureProject` records linked via `SA2ProjectLink` with `impact_score`, `value_aud`, `status`, `type`, `lat`/`lon` — currently only collapsed into a single Gov Investment score
- `AmenityData` (OSM 500m/1km/2km counts per amenity type) — exists, has its own table, **never shown to the user**
- `SuburbScore.updated_at` — no data-freshness indicator anywhere

### What every reference site leads with that we don't have at all
| Field | Source candidates |
|---|---|
| Median house & unit price (separated) | CoreLogic/Cotality (paid), Domain API, ABS PPI suburb file, scrape `realestate.com.au` sold listings |
| Quarterly / 12mo / 5yr / 10yr capital growth | Derived from price history once we have it |
| Weekly median rent (house & unit) | SQM Research (paid), scrape rental listings, ABS Census rent bands as fallback |
| Gross rental yield | `(weekly_rent × 52) / median_price` |
| Number of sales (12m) | Domain/CoreLogic, state land titles offices |
| Average days on market | Domain/realestate.com.au scrape |
| Vacancy rate | SQM Research, Domain rental insights |
| 5-year population change | We have `year` partitioned in `ABSCensusMetrics` — just need 2016 + 2021 rows loaded |

---

## 3. Critical UX Issues (regardless of new data)

1. **No data fetch.** `SuburbPage.tsx` ignores `sa2Code` for everything except a subtitle. The first PR should just hit the API and render what's already there.
2. **Score-only framing buries the lede.** An investor wants the *price*, then context. Scores belong below or alongside the fundamentals, not above them.
3. **Six 56px-font scorecards in a row** dominate ~60% of the viewport. Strong Investment Score deserves prominence; the five sub-scores should be a tighter sparkline/bar group (the `Breakdown.tsx` component already does this — it's just unused).
4. **No data provenance.** Every comparable site shows "Data as of <date>, sourced from <X>". We have `updated_at` and `census_year` in the response — show them.
5. **Risk flags as undifferentiated grey chips** read as tags, not warnings. Colour-code or icon them (yellow/red).
6. **Paywall is loud, premature, and identical** for every suburb. A locked preview ("18 more data points behind paywall") converts better than a wall.
7. **No back-pressure on missing data.** If a field is null, today it would render a literal "undefined" — components have no empty states.

---

## 4. Recommended Page Structure

A reorganised layout that mirrors how the inspiration sites cue investor decisions, while staying within what we can deliver in 2–3 PRs:

```
┌─ Header ──────────────────────────────────────────────────────┐
│ Chermside, QLD 4032        [State badge]   ⓘ Data as of …    │
│ SA2: 30150  •  Pop 18,420  •  Area 5.2 km²                   │
└──────────────────────────────────────────────────────────────┘

┌─ Hero: Investment Verdict ───────────────────────────────────┐
│  78 / 100   Strong Growth                                    │
│  ▓▓▓▓▓▓▓▓░░  vs Brisbane median 64  •  QLD median 61         │
│  "Infrastructure-driven suburb with demographic momentum…"   │
│  [tags: Early Growth Zone] [Infrastructure-Driven]           │
└──────────────────────────────────────────────────────────────┘

┌─ Market Snapshot (the missing layer) ────────────────────────┐
│ │ House      │ Unit       │                                  │
│ Median price │ $860k      │ $411k                            │
│ 12-mo growth │ +15.4%     │ –                                │
│ Weekly rent  │ $1,300     │ $775                             │
│ Gross yield  │ 8.13%      │ 9.16%                            │
│ Sales (12m)  │ 32         │ 3                                │
│ Days on mkt  │ 12         │ 19                               │
│ Vacancy rate │ 1.4%                                          │
└──────────────────────────────────────────────────────────────┘

┌─ Score Breakdown ────────┐ ┌─ Risk Flags ──────────────────┐
│ Demographics    82 ▓▓▓▓  │ │ ⚠ Rising rental volatility    │
│ Economy         74 ▓▓▓░  │ │ ⚠ Moderate retail dependency  │
│ Housing         69 ▓▓░░  │ └───────────────────────────────┘
│ Resilience      71 ▓▓▓░  │
│ Gov Investment  85 ▓▓▓▓  │ ┌─ Tags ────────────────────────┐
└──────────────────────────┘ │ [Premium Investment]          │
                             │ [Infrastructure-Driven]       │
                             └───────────────────────────────┘

┌─ Demographics ───────────────────────────────────────────────┐
│ Age distribution chart  •  Income brackets  •  Tenure split  │
│ Population trend: 2011 → 2016 → 2021 (line chart)            │
│ Occupations: top 5 industries (horizontal bar)               │
└──────────────────────────────────────────────────────────────┘

┌─ Infrastructure Pipeline ────────────────────────────────────┐
│ Map (lat/lon already in DB) with project pins                │
│ Table: Project | Type | Value $M | Status | Impact           │
└──────────────────────────────────────────────────────────────┘

┌─ Liveability (OSM amenities — already in DB!) ───────────────┐
│ Walk-to-cafe: 4 within 500m   Schools: 2 within 1km          │
│ Hospital: 1 within 2km        Gym: 3 within 1km              │
│ Amenity density score: 78 / 100                              │
└──────────────────────────────────────────────────────────────┘

┌─ Peer Suburbs ───────────────────────────────────────────────┐
│ "Similar suburbs in QLD": 5 tiles linking to their reports   │
└──────────────────────────────────────────────────────────────┘

┌─ Soft paywall ───────────────────────────────────────────────┐
│ Unlock: 5-yr price chart, ROI calculator, full peer list     │
└──────────────────────────────────────────────────────────────┘
```

---

## 5. Data Additions — by feasibility

### Tier 1 — Already in DB, just surface it (cheapest, do first)
| Add | DB source | Effort |
|---|---|---|
| Suburb name & state in header | `SA2Region` (joined in API today) | trivial |
| Population, median age, median income | already in API response | trivial |
| Owner/renter tenure split (donut) | `ABSCensusMetrics.{owners,renters}_pct` | trivial |
| Industry mix (horizontal bar) | `ABSCensusMetrics.industry_profile` JSON | small |
| Infrastructure project list & map | `InfrastructureProject` + `SA2ProjectLink` (have lat/lon) | medium |
| OSM amenity counts (cafes, schools, hospitals) | `AmenityData` table | small (need GET endpoint) |
| Data freshness badge | `SuburbScore.updated_at`, `census_year` | trivial |

### Tier 2 — Derivable from existing data (low effort, high value)
| Add | How derived |
|---|---|
| 5-yr population change | Diff 2016 vs 2021 census rows once both seeded (schema already supports multi-year) |
| 5-yr median income change | Same — diff across census years |
| Industry diversity (HHI) | Already computed in `utils.calculate_employment_diversity` — show the underlying number |
| Peer suburbs ("similar to this one") | Cluster on (state, score band, pop band) — single SQL query |
| State / national percentile rank | `SuburbScore` rank window function |
| Score vs state median delta bar | Aggregate over `SuburbScore` |
| "Stage of cycle" tag | Heuristic: combo of growth trend + vacancy + days-on-market once Tier 3 lands |

### Tier 3 — Needs new ingestion (the property fundamentals layer)
Without these, the report is academic rather than investible. Pick **one source** to start; CoreLogic/Cotality is the gold standard but paywalled.

| Field | Best free source | Best paid source |
|---|---|---|
| Median sale prices (house/unit) | ABS *Total Value of Dwellings* (suburb-level lag) | CoreLogic, Domain API |
| 1/3/5/10-yr capital growth | Derived from price series | Cotality direct |
| Median weekly rent | ABS Census rent (lagged) | SQM Research, Domain |
| Vacancy rate | SQM monthly free tier | SQM Pro, Cotality |
| Days on market | Scrape realestate.com.au | Domain API |
| Sales volume | State land registries (free, slow) | CoreLogic |

**Recommendation:** Start with Domain API (free developer tier covers most of the above for prototype scale) and a monthly SQM vacancy scrape. New tables:
- `suburb_price_history(sa2_code, period_end, dwelling_type, median_price, sales_count, days_on_market)`
- `suburb_rent_history(sa2_code, period_end, dwelling_type, median_weekly_rent, vacancy_rate)`

### Tier 4 — Differentiated "moat" features
These are what would actually justify a $9 paywall over scraping YIP for free.

- **Forward-looking infrastructure impact** — we already weight projects by stage (`under_construction` × 1.0, `planned` × 0.4). Show the *timeline* of expected uplift, not just a score.
- **Risk-adjusted yield** — gross yield minus vacancy rate minus a state-level price-volatility term. None of the competitor sites do this well.
- **Affordability vs borrowing power calculator** — "$X deposit, 6.04% rate → you can afford in 47% of QLD suburbs above score 70". This is exactly Launch Finance's wedge.
- **Gentrification signal** — owner-occupier % trending up + median income trending up + young-prof % trending up. We can compute this once we have two census points.
- **"Ripple-effect" suggestions** — adjacent suburbs that are 1–2 years behind on the curve. The Aus Investment Properties blog calls this out specifically and no one does it well in product.

---

## 6. Suggested Implementation Phasing

| PR | Scope | Effort |
|---|---|---|
| **F1** | Wire `SuburbPage.tsx` to `GET /suburb/{sa2_code}`. Render real scores, insight, risk flags, tags. Add loading + error + empty states. Show census year & population. | 1 session |
| **F2** | Add Demographics block (tenure donut, industry bar, age). Add data-freshness badge. Use existing `Breakdown.tsx` instead of giant scorecards. | 1 session |
| **F3** | Surface `AmenityData` via a new `/suburb/{sa2_code}/amenities` endpoint + Liveability block. Add Infrastructure block with project table (map can come later). | 1–2 sessions |
| **B1** | Backfill 2016 census so 5-yr trends render. Add peer-suburb query. | 1 session (data-heavy) |
| **B2** | Ingest one external property data source (Domain API recommended). New price/rent tables + scheduled refresh. | 2–3 sessions |
| **F4** | Market Snapshot block (Tier 3 fields). Re-anchor the page so this becomes the hero card alongside the score. | 1 session, blocked on B2 |

---

## 7. Open Questions for Linh

These need a decision before F2+ scope is final:

1. **Price/rent data source budget** — do we have a Domain/CoreLogic spend, or scrape-only? Determines whether F4 is 2 weeks or 2 months.
2. **Paywall strategy** — keep flat $9, or move to subscription / freemium (free city-level, paid SA2-level)? Affects information-architecture choices in F1.
3. **Geographic granularity** — stay at SA2 (~10–25k pop) or also add SA3 / postcode views? Investors search by postcode; SA2 isn't a name they recognise.
4. **Target persona** — first-home-buyer, yield-investor, growth-investor? The "verdict" copy and which scores headline depend on this.

---

## 8. Handoff

**Next agent:** Claude Code (or whichever Frontier agent picks up frontend work)
**File to read:** this document
**Suggested first task:** PR F1 above — purely a UI wire-up, no schema changes, immediately makes the page useful.

**Linh's review needed on:** Section 7 (open questions) and the phasing in Section 6 before any code is written.
