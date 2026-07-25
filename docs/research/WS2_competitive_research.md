# Workstream 2 — Competitive Research

**Prepared for:** Suburb Intel improvement plan (Rogue Night consulting)
**Date:** 2026-07-10
**Status:** Research complete — feeds the prioritised plan. Includes external evidence bearing on the two flagged section-removal decisions (SEIFA, Government Investment).
**Focus:** Tools aimed at professional buyers agents & investors — not consumer home-buyer tools.

---

## TL;DR

Every serious competitor leads with the **same thing Suburb Intel is missing: a momentum/timing signal.** HtAG's Growth Rate Cycle and DSR's Market Cycle Timing both answer "is this suburb *accelerating* or *decelerating*?" — the question a buyers agent asks first, and one that headline medians can't answer. Beneath that, the professional research process is a **funnel** (macro → timing → supply scarcity → demand/socio → price validation → street level), which maps almost exactly onto Suburb Intel's three pages. And two of the specific signals competitors rely on — socioeconomic decile (SEIFA/IRSAD) and the infrastructure pipeline — are the very sections flagged for possible removal. The competitive evidence argues for **keeping and reframing both**, not cutting them.

---

## 1. The landscape (professional-tier tools)

| Tool | Positioning | Leads with |
|------|-------------|-----------|
| **HtAG Analytics** | Data platform for investors + buyers agents; 150+ metrics, 15,000+ suburbs | **Growth Rate Cycle (GRC)** momentum; supply scarcity; IRSAD; typical price |
| **DSR Data / Suburb Data** (Jeremy Sheppard) | The original "hotspot" scoring tool | **Demand-to-Supply Ratio (DSR)** 0–100 composite; Market Cycle Timing |
| **Suburbtrends** | Suburb-level analysis, buyer/sales indices | Buyer demand index, sales volumes, rental dynamics |
| **Microburbs** | Suburb + street-level scores, forecasts | Lifestyle/demographic scores; market forecasts; street-level data |
| **CoreLogic / Cotality (RP Data)** | Incumbent enterprise data | Sales history, AVM valuations, market trends (enterprise pricing, ~$1,500/seat) |
| **PriceFinder** | Agent appraisal tool | Sales histories, comparables, appraisal workflow |

The gap Suburb Intel can exploit: the incumbents (CoreLogic, PriceFinder) are broad and expensive; the modern challengers (HtAG, DSR) win specifically by packaging **forward-looking momentum + supply/demand into a fast shortlist workflow.** That is exactly Suburb Intel's stated mission.

## 2. What a professional actually checks first (the analyst's funnel)

Synthesised from HtAG's published 6-step buyers-agent framework and DSR's methodology. This is the single most useful artefact from the research:

| Stage | Question | Key metrics | Suburb Intel page |
|-------|----------|-------------|-------------------|
| 1. Macro | Is the state/LGA heading the right way over 3–7 yrs? | Population growth, interstate migration, **infrastructure pipeline**, employment | Search (filters) |
| 2. **Timing** | Is growth *accelerating or decelerating*? | **Growth Rate Cycle / Market Cycle Timing** (turning points 6–12mo before medians) | Rankings / Suburb |
| 3. **Supply scarcity** ("non-negotiable") | Is stock structurally constrained? | Stock-on-market %, **BA ratio** (approvals ÷ dwellings), inventory | Suburb |
| 4. Demand + socio stability | Is demand genuine and stable? | Declining DOM, vacancy <1%, owner-occ >65%, auction clearance, online search index, **IRSAD/SEIFA decile** | Suburb |
| 5. Price validation | Is the price real and affordable? | **Typical (mix-adjusted) price**, "years-to-own" affordability, yield | Suburb |
| 6. Street-level DD | Best street, best property? | Comparables, postcode vacancy, infra proximity, flood/bushfire risk | Suburb |

Two things stand out. First, **timing (stage 2) is where the money is** — HtAG's own data claims GRC Phase 1–2 entries delivered 9.3% first-year growth vs 3.1% for late-cycle entries. Suburb Intel has no timing metric today; this is the biggest single content gap. Second, the funnel maps cleanly onto Search → Rankings → Suburb — Suburb Intel could **explicitly frame its three pages as this funnel** rather than as three independent views.

## 3. How they visualise trend/momentum — patterns to adapt

Concrete, adaptable patterns (not "add more charts"):

- **Context Ruler (DSR).** Every statistic is shown against the national average on a small visual scale, so an unfamiliar number ("is 4.6 inventory-months good?") is instantly legible. Cheap to build with our existing hand-rolled SVG, and high-value for a data-dense report. **Strong quick win for the Suburb page.**
- **Per-stat historical mini-chart.** DSR lets you expand any stat into its own history. Pairs perfectly with WS1's finding that we're already accumulating a monthly series — each metric can get a sparkline.
- **Cycle phase dial / "property clock."** HtAG's 8-phase GRC and DSR's Market Cycle Timing are shown as a position on a cycle. With the PropRadar Pro `market_cycle` endpoint ruled out (no upgrade), we'd derive a simplified phase/momentum read in-house from our own growth-rate trend + sale-velocity signals (WS1 §4) — the same visual, powered by derived data.
- **"Market in Motion" animation + bubble chart.** HtAG animates phase movement across suburbs over time; a bubble chart (bubble = suburb, size = research/heat, colour = state) gives a whole-market momentum view. A static version is achievable now from our snapshot series.
- **Geographic heatmap** with switchable layers (growth, vacancy, yield, heat). HtAG (GeoDex), DSR, and even PropRadar's own consumer site all lead with this. Bigger build, but the canonical "where's moving" view.
- **Plain-English-first sections + hover-for-definition.** Notably, HtAG *just rebuilt* its suburb dashboards (announced 7 Jul 2026) so **every section opens with a plain-English read of what supply and demand are doing before you reach a single chart**, with hover-to-explain on every metric. This is a direct signal about the density question below.

## 4. The UI density question (dense/terminal vs. clean/consumer) — research-informed answer

The brief asked whether the target user wants a denser, terminal-like UI or a cleaner consumer one. The evidence points to a specific middle position, not either pole:

- 2026 design consensus for professional/power-user tools: **strategic density with strong information hierarchy beats minimalism** — power users want speed and fewer clicks, and the Bloomberg terminal (dense tables, monospace numerics, scannable rows) is the reference point.
- **But** the leading *property* pro-tool (HtAG) pairs that density with a plain-English interpretation line leading each section and hover definitions — because even professionals need the "so what" fast.

**Recommendation for WS3:** target **"data-dense but guided."** Denser and more scannable than today (tighter grid, monospace numerics, tables, context rulers, more metrics visible without clicks) — clearly not a consumer brochure — but every dense block led by a one-line "what this means," with definitions on hover. Not a raw terminal; not a lifestyle site. This is an evidence-based call, not taste.

## 5. Evidence bearing on the two flagged section-removal decisions

Both flagged sections turn out to be things professional competitors *actively use*. This is exactly the "considered call, not a default" the brief asked for.

**Community & Socio-Economic Profile (SEIFA deciles) — evidence says KEEP + reframe.**
HtAG uses IRSAD (the ABS advantage/disadvantage index — same SEIFA family) as a core **"demand-stability filter,"** and publishes an "IRSAD Crossover Effect": mid-tier decile (5–7) suburbs outperformed both premium and disadvantaged suburbs over 5 years (42.3% vs 35.1% vs 31.8%). So for *this* audience, socioeconomic decile is meaningful — but as a **growth-stability / affordability-cohort signal, not a "nice neighbourhood" score.** Recommendation: don't cut it; re-frame the SEIFA decile as a stability filter and consider pairing it with owner-occupier % (which PropRadar already returns). *Note also (WS4 relevance): SEIFA 2021 is the current SEIFA release — SEIFA is only produced each census cycle — so unlike stale census demographic snapshots, it is not "out of date," it is simply the latest that exists.*

**Government Investment (infrastructure projects / iPAMS) — evidence says KEEP + make it momentum-relevant.**
HtAG's framework lists **"infrastructure pipeline (announced and under construction)" as a Step-1 macro filter**; infrastructure investment is a textbook early hotspot signal for buyers agents. It was also just wired to a live, free source (1,182 real iPAMS projects). Recommendation: keep it, but shape it toward the mission — proximity + dollar value + status + timing as a forward signal, not a generic project list. Cutting a live, free, mission-relevant signal would be the weaker call.

**Both remain product decisions for Linh** — the research simply shifts the default from "cut" toward "keep and reframe," with evidence.

---

## Sources

- [HtAG Analytics — home](https://www.htag.com.au/) and [How Buyers Agents Research Suburbs: The 6-Step Data Framework](https://www.htag.com.au/buyers-agent-suburb-research/)
- [DSR Data — Suburb Analyser explainer](https://dsrdata.com.au/products/suburb_analyser) and [DSR home](https://dsrdata.com.au/)
- [Suburb Data — DSR3 metric](https://suburbdata.com.au/metrics/dsr3/)
- [Microburbs — competitor comparison](https://www.microburbs.com.au/research/compare-competitors) and [Top 10 property research tools](https://www2.microburbs.com.au/post/top-10-property-research-tools-for-2024-in-australia)
- [PropertySensor — best AU property data tools](https://www.propertysensor.com/articles/11/the-best-property-data-and-real-estate-analytics-tools-for-australian-investors)
- [MyDesigner — Dense Interfaces Are Back (2026)](https://mydesigner.gg/blog/dense-interfaces-information-hierarchy-2026); [Designing for Data Density](https://paulwallas.medium.com/designing-for-data-density-what-most-ui-tutorials-wont-teach-you-091b3e9b51f4)

## Handoff

**Next:** Both WS1 and WS2 research docs are complete. The prioritised improvement plan (next session) should: (a) treat a **momentum/timing metric** as the headline content gap; (b) frame the three pages as the analyst funnel; (c) adopt "data-dense but guided" for WS3; (d) put the SEIFA and Government-Investment decisions to Linh with the keep-and-reframe evidence above.
