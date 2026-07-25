// Real-data-derived reference points for the Context Ruler (DSR-style —
// WS2 §3: "every statistic shown against the national average on a small
// visual scale"). Each value is the actual median of that field across every
// real suburb in the dev DB with a non-null value, computed 2026-07-18 from
// `suburb_market_stats` (latest snapshot per suburb) and `momentum.py`'s own
// documented scarcity-input medians — not a guessed round number, per this
// project's data-driven-calibration standard. Re-derive periodically as
// coverage/season shifts the distribution (same discipline as the momentum/
// scarcity thresholds in backend/app/core/momentum.py).
export const nationalMedians = {
  medianHousePrice: 1_000_000, // n=2,530
  medianHouseRentWeekly: 695, // n=2,719
  grossYieldHousePct: 3.62, // n=2,168 — matches momentum.py's _QUADRANT_YIELD_MEDIAN_PCT
  daysOnMarketHouse: 33, // n=2,689
  vacancyRatePct: 1.0, // n=2,697
  growthHouse1yPct: 9.6, // matches momentum.py's _QUADRANT_GROWTH_MEDIAN_PCT
  stockOnMarketPct: 0.355, // matches momentum.py's _STOCK_ON_MARKET_CEILING_PCT comment (ceiling = 2x median)
  inventoryMonths: 2.375, // matches momentum.py's _INVENTORY_MONTHS_CEILING comment
  buildingApprovalsPer1000: 3.38, // matches momentum.py's _APPROVALS_PER_1000_CEILING comment
} as const

// Reasonable display ranges for the ruler track (roughly p10-p90 of the same
// dataset, rounded) — not hard mins/maxes, values outside this range simply
// clamp to the track's edge.
export const nationalRanges = {
  medianHousePrice: { min: 400_000, max: 2_500_000 },
  medianHouseRentWeekly: { min: 300, max: 1_200 },
  grossYieldHousePct: { min: 1, max: 6 },
  daysOnMarketHouse: { min: 10, max: 90 },
  vacancyRatePct: { min: 0, max: 4 },
  growthHouse1yPct: { min: -10, max: 30 },
  stockOnMarketPct: { min: 0, max: 1.5 },
  inventoryMonths: { min: 0, max: 8 },
  buildingApprovalsPer1000: { min: 0, max: 12 },
} as const
