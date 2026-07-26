import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ContextRuler, DonutChart, HorizontalBars, PropertyCycleClock, TrendLine, type CyclePosition } from '../components/Charts'
import { Card, MetricWithInfo, MiniStat, Pill, Section, Stat, StatGrid } from '../components/primitives'
import type { GrowthYieldQuadrant, MomentumPhase, NeighborhoodSignal } from '../lib/api'
import { nationalMedians, nationalRanges } from '../lib/nationalBaselines'
import { colors, fonts } from '../lib/theme'

interface RecentSale {
  address: string | null
  bedrooms: number | null
  bathrooms: number | null
  property_type: string | null
  sold_price: number | null
  sold_date: string | null
}

interface PriceHistoryPoint {
  period: string
  median_price: number
  sale_count: number
}

interface LandSizeBand {
  label: string
  sale_count: number
}

interface DetailedSpec {
  label: string
  median_price: number
  sale_count: number
}

interface SpecPriceHistory {
  label: string
  history: PriceHistoryPoint[]
}

interface PropertyMarket {
  building_approvals_1yr: number | null
  recent_sales: RecentSale[]
  recent_sales_available: boolean
  price_history: PriceHistoryPoint[]
  price_history_by_spec: SpecPriceHistory[]
  detailed_specs: DetailedSpec[]
  land_size_breakdown: LandSizeBand[]
}

interface RentalSnapshot {
  period: string
  median_house_rent_weekly: number | null
  median_unit_rent_weekly: number | null
  gross_yield_house_pct: number | null
  gross_yield_unit_pct: number | null
  days_on_market_house: number | null
  days_on_market_unit: number | null
  vacancy_rate_pct: number | null
}

interface RentalMarketEntry {
  suburb_name: string
  history: RentalSnapshot[]
}

interface SuburbMarketStat {
  suburb_name: string
  median_house_price: number | null
  median_unit_price: number | null
  median_house_rent_weekly: number | null
  median_unit_rent_weekly: number | null
  growth_house_1y_pct: number | null
  growth_house_3y_pct: number | null
  growth_house_5y_pct: number | null
  growth_unit_1y_pct: number | null
  growth_unit_3y_pct: number | null
  growth_unit_5y_pct: number | null
  gross_yield_house_pct: number | null
  gross_yield_unit_pct: number | null
  days_on_market_house: number | null
  days_on_market_unit: number | null
  vacancy_rate_pct: number | null
  sold_vs_asking_pct: number | null
  heat_score_house: number | null
  heat_score_unit: number | null
  sales_12mo_house: number | null
  sales_12mo_unit: number | null
}

interface InvestmentOutlook {
  pop_growth_5yr: number | null
  pop_proj_2026: number | null
  pop_proj_2031: number | null
  pop_growth_proj_pct: number | null
  building_approvals_1yr: number | null
  distance_to_cbd_km: number | null
}

interface Demographics {
  population: number | null
  median_age: number | null
  avg_household_size: number | null
  families_with_children_pct: number | null
  overseas_born_pct: number | null
  moved_in_1yr_pct: number | null
  moved_in_5yr_pct: number | null
  uni_degree_pct: number | null
  professionals_managers_pct: number | null
}

interface Economy {
  median_income: number | null
  unemployment_pct: number | null
}

interface HouseTypeBucket {
  label: string
  median_price: number
  sale_count: number
}

interface Housing {
  renters_pct: number | null
  owners_pct: number | null
  median_rent_weekly: number | null
  median_mortgage_monthly: number | null
  high_rent_stress_pct: number | null
  high_mortgage_stress_pct: number | null
  separate_house_pct: number | null
  flat_apartment_pct: number | null
  one_bedroom_pct: number | null
  social_housing_pct: number | null
  by_house_type: HouseTypeBucket[]
}

interface Community {
  seifa_irsd_decile: number | null
  seifa_irsad_decile: number | null
  seifa_ier_decile: number | null
  seifa_ieo_decile: number | null
}

interface GovProject {
  name: string
  type: string
  status: string
  value_aud: number | null
  timing: string | null
  expected_start: string | null
  expected_end: string | null
}

interface LocalSchoolEntry {
  name: string
  level: string | null
  sector: 'Public' | 'Private' | null
  icsea_percentile: number | null
}

interface NearbySchoolEntry extends LocalSchoolEntry {
  suburb: string
}

interface SchoolPercentile {
  avg_icsea: number
  state: string
  percentile: number
  top_pct_label: string
  sample_size: number
}

interface Schools {
  avg_school_icsea: number | null
  num_schools: number | null
  local: LocalSchoolEntry[]
  nearby: NearbySchoolEntry[]
  state_percentile: SchoolPercentile | null
}

interface Amenities {
  cafes: number | null
  bakeries: number | null
  restaurants: number | null
  fast_food: number | null
  supermarkets: number | null
  parks: number | null
  gyms: number | null
  hospitals: number | null
  pharmacies: number | null
  shopping_centres: number | null
  cuisines: Record<string, number>
}

interface Transport {
  pt_stop_train: number | null
  pt_stop_tram: number | null
  pt_stop_bus: number | null
  pt_stop_ferry: number | null
  car_commute_pct: number | null
  pt_commute_pct: number | null
  work_from_home_pct: number | null
  zero_car_dwellings_pct: number | null
  distance_to_cbd_km: number | null
}

interface RegionalMetric {
  key: string
  label: string
  format: 'currency' | 'pct'
  suburb_value: number
  region_average: number
}

interface RegionalComparison {
  region_label: string
  metrics: RegionalMetric[]
}

interface InvestmentHighlight {
  label: string
  format: 'text' | 'pct' | 'rate' | 'score' | 'days'
  value: number | string | null
  tone: 'positive' | 'neutral' | 'negative'
}

interface InvestmentSnapshot {
  verdict: string | null
  highlights: InvestmentHighlight[]
}

interface SaleVelocityMonthly {
  period: string
  count: number
}

interface SaleVelocity {
  monthly_counts: SaleVelocityMonthly[]
  recent_3mo_count: number
  prior_3mo_count: number
  trend_pct: number | null
}

interface ScarcityComponents {
  stock_on_market_score: number | null
  inventory_months_score: number | null
  building_approvals_score: number | null
}

interface SupplyScarcityEntry {
  suburb_name: string
  scarcity_score: number | null
  components: ScarcityComponents
}

interface MomentumSignalDetail {
  signal: number | null
  trend_pct?: number | null
  growth_pct?: number | null
  scarcity_score?: number | null
  value?: number | null
}

interface MomentumComponents {
  sale_velocity: MomentumSignalDetail
  growth: MomentumSignalDetail
  supply_scarcity: MomentumSignalDetail
  heat_score: MomentumSignalDetail
}

interface MomentumCompositeEntry {
  suburb_name: string
  phase: MomentumPhase | null
  momentum_score: number | null
  components: MomentumComponents
}

interface NeighborhoodMomentum {
  total_neighbors: number
  counts: { accelerating: number; steady: number; cooling: number }
  accelerating_pct: number | null
  cooling_pct: number | null
  signal: NeighborhoodSignal | null
}

interface GrowthYieldQuadrantEntry {
  suburb_name: string
  quadrant: GrowthYieldQuadrant | null
  label: string | null
}

interface PropertyCycleEntry {
  suburb_name: string
  position: CyclePosition | null
  label: string | null
  angle_degrees: number | null
  confidence: number | null
}

interface Momentum {
  sale_velocity: SaleVelocity
  supply_scarcity: SupplyScarcityEntry[]
  composite: MomentumCompositeEntry[]
  neighborhood: NeighborhoodMomentum
  growth_yield_quadrant: GrowthYieldQuadrantEntry[]
  property_cycle: PropertyCycleEntry[]
}

interface LocalPoiEntry {
  name: string
  group: string
  hospital_type: 'Public' | 'Private' | null
}

interface NearbyPoiEntry extends LocalPoiEntry {
  suburb: string
  distance_km: number
}

interface PointsOfInterest {
  local: LocalPoiEntry[]
  nearby: NearbyPoiEntry[]
}

interface SuburbReport {
  sa2_code: string
  sa2_name: string | null
  state: string | null
  census_year: number
  show_census_sections: boolean
  insight: string
  investment_snapshot: InvestmentSnapshot | null
  risk_flags: string[]
  tags: string[]
  regional_comparison: RegionalComparison | null
  location: { distance_to_cbd_km: number | null }
  momentum: Momentum
  market_stats: SuburbMarketStat[]
  rental_market: RentalMarketEntry[]
  property_market: PropertyMarket
  investment_outlook: InvestmentOutlook
  demographics: Demographics
  economy: Economy
  housing: Housing
  community: Community
  government_investment: { projects: GovProject[] }
  schools: Schools
  amenities: Amenities
  points_of_interest: PointsOfInterest
  transport: Transport
}

type FetchState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: SuburbReport }

// ---------------------------------------------------------------------------
// Formatting helpers
// ---------------------------------------------------------------------------

function fmtNum(v: number | null | undefined): string {
  return v == null ? '—' : Math.round(v).toLocaleString()
}
function fmtPct(v: number | null | undefined, digits = 1): string {
  return v == null ? '—' : `${v.toFixed(digits)}%`
}
function fmtCurrency(v: number | null | undefined): string {
  return v == null ? '—' : `$${Math.round(v).toLocaleString()}`
}
function fmtKm(v: number | null | undefined): string {
  return v == null ? '—' : `${v.toFixed(1)} km`
}
function fmtDecile(v: number | null | undefined): string {
  return v == null ? '—' : `${v} / 10`
}
function fmtDays(v: number | null | undefined): string {
  return v == null ? '—' : `${Math.round(v)} days`
}
function titleCase(s: string): string {
  return s.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
function fmtTopPercent(percentile: number): string {
  return `Top ${Math.max(Math.round(100 - percentile), 1)}%`
}
function fmtSignal(v: number | null | undefined): string {
  return v == null ? '—' : `${v > 0 ? '+' : ''}${v.toFixed(2)}`
}
function fmtScore100(v: number | null | undefined): string {
  return v == null ? '—' : `${Math.round(v)}/100`
}
function momentumPhaseTone(phase: MomentumPhase | null): 'green' | 'blue' | 'amber' {
  if (phase === 'accelerating') return 'green'
  if (phase === 'cooling') return 'amber'
  return 'blue'
}
function momentumPhaseArrow(phase: MomentumPhase | null): string {
  if (phase === 'accelerating') return '▲'
  if (phase === 'cooling') return '▼'
  return '→'
}
const QUADRANT_TAG_LABEL: Record<GrowthYieldQuadrant, string> = {
  hot: 'Hot',
  growth_play: 'Growth play',
  cash_flow_play: 'Cash-flow play',
  avoid: 'Avoid',
}

// ---------------------------------------------------------------------------
// Plain-English section summaries (Phase 3 Task 3.2) — one-line, auto-
// generated interpretations shown at the top of a section, before any chart
// (WS2 §3-4). Each summary reuses signals already computed by the backend
// (momentum phase, scarcity score, growth/yield quadrant) rather than
// re-deriving new judgment calls in the frontend, except where noted — the
// new population-growth thresholds below are this project's usual real-data
// discipline: p25/p75 of ABSCEntensMetrics.pop_growth_proj_pct across 2,418
// suburbs with a value (2026-07 snapshot: p25=1.46%, median=6.07%,
// p75=12.40%), not guessed round numbers. Re-derive periodically the same
// way as backend/app/core/momentum.py's thresholds.
const _POP_GROWTH_STRONG_PCT = 12.4
const _POP_GROWTH_WEAK_PCT = 1.46
const _VACANCY_TIGHT_PCT = 0.62 // p25 of vacancy_rate_pct, n=2,697, 2026-07 snapshot
const _VACANCY_ELEVATED_PCT = 1.5 // p75, same dataset

function summarizeMomentum(phase: MomentumPhase | null, scarcityScore: number | null): string | null {
  const supplyRead =
    scarcityScore == null ? null : scarcityScore >= 60 ? 'Supply is tight' : scarcityScore <= 30 ? 'Supply is abundant' : 'Supply is balanced'
  const demandRead =
    phase === 'accelerating' ? 'demand is accelerating' : phase === 'cooling' ? 'demand is cooling' : phase === 'steady' ? 'demand is steady' : null
  const parts = [supplyRead, demandRead].filter((p): p is string => p != null)
  if (parts.length === 0) return null
  return parts.join(' and ') + '.'
}

function summarizeOutlook(popGrowthProjPct: number | null | undefined): string | null {
  if (popGrowthProjPct == null) return null
  if (popGrowthProjPct >= _POP_GROWTH_STRONG_PCT) {
    return `Population is projected to grow strongly (+${popGrowthProjPct.toFixed(1)}% by 2031).`
  }
  if (popGrowthProjPct <= _POP_GROWTH_WEAK_PCT) {
    return popGrowthProjPct < 0
      ? `Population is projected to decline (${popGrowthProjPct.toFixed(1)}% by 2031).`
      : `Population growth is projected to be flat (+${popGrowthProjPct.toFixed(1)}% by 2031).`
  }
  return `Population is projected to grow steadily (+${popGrowthProjPct.toFixed(1)}% by 2031).`
}

function summarizeVacancy(vacancyRatePct: number | null | undefined): string | null {
  if (vacancyRatePct == null) return null
  if (vacancyRatePct <= _VACANCY_TIGHT_PCT) return `Rental vacancy is tight (${vacancyRatePct.toFixed(1)}%) — favours landlords.`
  if (vacancyRatePct >= _VACANCY_ELEVATED_PCT) return `Rental vacancy is elevated (${vacancyRatePct.toFixed(1)}%) — favours tenants.`
  return `Rental vacancy is typical for the market (${vacancyRatePct.toFixed(1)}%).`
}

/** SA2 names often combine multiple gazetted suburbs (e.g. "Rochedale -
 * Burbank", "Kedron - Gordon Park") since that's the ABS statistical area,
 * not a real suburb boundary. For display, use just the first named suburb
 * — the full official SA2 name stays visible in the subtitle line so
 * nothing's lost, just de-emphasized. */
function primarySuburbName(sa2Name: string | null | undefined): string {
  if (!sa2Name) return 'This Suburb'
  const withoutStateSuffix = sa2Name.replace(/\s*\((Vic\.|NSW|ACT|SA|WA|QLD|NT|Tas\.)\)\s*$/i, '')
  return withoutStateSuffix.split(' - ')[0].trim()
}

function fmtHighlightValue(h: InvestmentHighlight): string {
  if (h.value == null) return '—'
  if (h.format === 'pct') {
    // A delta (e.g. price growth) — sign matters, unlike 'rate' below.
    const v = h.value as number
    return `${v > 0 ? '+' : ''}${v.toFixed(1)}%`
  }
  if (h.format === 'rate') return fmtPct(h.value as number)
  if (h.format === 'score') return `${Math.round(h.value as number)}/100`
  if (h.format === 'days') return fmtDays(h.value as number)
  return String(h.value)
}

const HIGHLIGHT_INFO: Record<string, string> = {
  Momentum: 'Our in-house accelerating/steady/cooling read, derived from sale velocity, price growth, supply scarcity, and PropRadar heat score — a substitute for the gated market-cycle endpoint.',
  '1yr Price Growth': "Change in this suburb's median house sale price over the past 12 months.",
  'Gross Rental Yield': 'Annual rent as a % of the median house price, before costs — 4%+ is commonly cited as a solid investor yield in AU capital cities.',
  'Supply Scarcity': '0-100 score combining stock-on-market %, inventory months, and building approvals — higher means less for-sale supply relative to demand.',
  'Days on Market': 'Median number of days a house listing takes to sell in this suburb — fewer days signals stronger buyer demand.',
}

function InvestmentHighlightTile({ highlight }: { highlight: InvestmentHighlight }) {
  const toneColor =
    highlight.tone === 'positive' ? colors.green : highlight.tone === 'negative' ? colors.amber : colors.textPrimary
  const toneBg =
    highlight.tone === 'positive' ? colors.greenLight : highlight.tone === 'negative' ? colors.amberLight : colors.pageBg
  const info = HIGHLIGHT_INFO[highlight.label]

  return (
    <div style={{ padding: '12px 14px', borderRadius: '8px', backgroundColor: toneBg }}>
      <div style={{ fontSize: '11px', color: colors.textMuted, marginBottom: '4px' }}>
        {info ? <MetricWithInfo label={highlight.label} info={info} /> : highlight.label}
      </div>
      <div style={{ fontSize: '18px', fontWeight: 700, color: toneColor, fontFamily: fonts.mono }}>{fmtHighlightValue(highlight)}</div>
    </div>
  )
}

const POI_GROUPS = ['Hospital', 'Shopping Centre', 'Stadium & Arena', 'Attraction']

function PoiRow({ poi, showSuburb = false }: { poi: NearbyPoiEntry | LocalPoiEntry; showSuburb?: boolean }) {
  const nearby = showSuburb ? (poi as NearbyPoiEntry) : undefined
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: '13px',
        padding: '10px 14px',
        backgroundColor: colors.pageBg,
        borderRadius: '8px',
        gap: '12px',
      }}
    >
      <span style={{ color: colors.textPrimary }}>
        {poi.name}
        {nearby && <span style={{ color: colors.textMuted }}> · {nearby.suburb} · {nearby.distance_km.toFixed(1)} km away</span>}
      </span>
      {poi.hospital_type && (
        <Pill tone={poi.hospital_type === 'Public' ? 'blue' : 'amber'}>{poi.hospital_type}</Pill>
      )}
    </div>
  )
}

function SchoolRow({ school, showSuburb = false }: { school: NearbySchoolEntry | LocalSchoolEntry; showSuburb?: boolean }) {
  const suburb = showSuburb ? (school as NearbySchoolEntry).suburb : undefined
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        fontSize: '13px',
        padding: '10px 14px',
        backgroundColor: colors.pageBg,
        borderRadius: '8px',
        gap: '12px',
      }}
    >
      <span style={{ color: colors.textPrimary }}>
        {school.name}
        {school.level && <span style={{ color: colors.textMuted }}> · {school.level}</span>}
        {suburb && <span style={{ color: colors.textMuted }}> · {suburb}</span>}
      </span>
      <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
        {school.sector && (
          <Pill tone={school.sector === 'Public' ? 'blue' : 'amber'}>{school.sector}</Pill>
        )}
        {school.icsea_percentile != null && (
          <Pill tone="green">{fmtTopPercent(school.icsea_percentile)}</Pill>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SuburbPage() {
  const { id: sa2Code = '' } = useParams<{ id: string }>()
  const [state, setState] = useState<FetchState>({ status: 'loading' })

  useEffect(() => {
    if (!sa2Code) {
      setState({ status: 'error', message: 'Missing SA2 code in URL.' })
      return
    }

    let cancelled = false
    setState({ status: 'loading' })

    fetch(`/api/suburb/${encodeURIComponent(sa2Code)}`)
      .then(async (response) => {
        if (!response.ok) {
          const body = await response.json().catch(() => null)
          const detail = body && typeof body.detail === 'string' ? body.detail : response.statusText
          throw new Error(`${response.status}: ${detail}`)
        }
        return (await response.json()) as SuburbReport
      })
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof Error ? err.message : 'Unknown error fetching suburb.'
        setState({ status: 'error', message })
      })

    return () => {
      cancelled = true
    }
  }, [sa2Code])

  return (
    <div
      style={{
        backgroundColor: colors.pageBg,
        backgroundImage:
          'radial-gradient(circle at 1px 1px, rgba(15,23,42,0.06) 1px, transparent 0)',
        backgroundSize: '18px 18px',
        margin: '-20px',
        padding: '20px',
        minHeight: 'calc(100vh - 40px)',
      }}
    >
      <div style={{ marginBottom: '20px' }}>
        <Link
          to="/"
          style={{
            display: 'inline-block',
            backgroundColor: colors.cardBg,
            color: colors.textPrimary,
            border: `1px solid ${colors.border}`,
            padding: '8px 16px',
            borderRadius: '6px',
            cursor: 'pointer',
            textDecoration: 'none',
            fontSize: '14px',
          }}
        >
          ← Back to Search
        </Link>
      </div>

      {state.status === 'loading' && (
        <p style={{ color: colors.textSecondary, fontSize: '18px' }}>Loading suburb {sa2Code}...</p>
      )}

      {state.status === 'error' && (
        <Card style={{ borderColor: '#FCA5A5' }}>
          <h2 style={{ marginTop: 0, color: colors.textPrimary }}>Could not load suburb {sa2Code}</h2>
          <p style={{ marginBottom: 0, color: colors.textSecondary }}>{state.message}</p>
        </Card>
      )}

      {state.status === 'ready' && <ReadyView data={state.data} />}
    </div>
  )
}

function ReadyView({ data }: { data: SuburbReport }) {
  const {
    sa2_code,
    sa2_name,
    state,
    census_year,
    show_census_sections,
    insight,
    investment_snapshot,
    risk_flags,
    tags,
    regional_comparison,
    momentum,
    market_stats,
    rental_market,
    property_market,
    investment_outlook,
    demographics,
    economy,
    housing,
    community,
    government_investment,
    schools,
    amenities,
    points_of_interest,
    transport,
  } = data

  const [selectedSpecLabel, setSelectedSpecLabel] = useState<string | null>(null)
  const chartableSpecs = property_market.price_history_by_spec.filter((s) => s.history.length >= 2)
  const activeSpecLabel =
    selectedSpecLabel && chartableSpecs.some((s) => s.label === selectedSpecLabel)
      ? selectedSpecLabel
      : chartableSpecs[0]?.label ?? null
  const activeSpecHistory = chartableSpecs.find((s) => s.label === activeSpecLabel) ?? null
  const chartableSpecLabels = new Set(chartableSpecs.map((s) => s.label))
  const rentalMarketSuburbs = new Set(rental_market.map((r) => r.suburb_name))
  const marketSnapshotSuburbs = new Set(market_stats.map((s) => s.suburb_name))

  function jumpTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  function jumpToSpec(label: string) {
    setSelectedSpecLabel(label)
    jumpTo('median-sold-price-over-time')
  }

  return (
    <>
      <div style={{ marginBottom: '24px' }}>
        <h1 style={{ fontSize: '36px', margin: 0, color: colors.textPrimary }}>
          {sa2_name ? primarySuburbName(sa2_name) : `Suburb ${sa2_code}`}
          {state ? (
            <span style={{ color: colors.textMuted, fontSize: '20px', marginLeft: '12px' }}>{state}</span>
          ) : null}
        </h1>
        <p style={{ color: colors.textMuted, fontSize: '15px', marginTop: '6px' }}>
          SA2 Code: {sa2_code}
          {sa2_name && sa2_name !== primarySuburbName(sa2_name) && <> · {sa2_name}</>}
          {transport.distance_to_cbd_km != null && <> · {fmtKm(transport.distance_to_cbd_km)} to CBD</>}
        </p>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '12px' }}>
          {tags.map((tag) => (
            <Pill key={tag} tone="pink">
              {tag}
            </Pill>
          ))}
        </div>
      </div>

      <Card style={{ marginBottom: '20px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 8px 0' }}>
          Key Insight
        </h3>
        <p style={{ fontSize: '16px', color: colors.textSecondary, lineHeight: 1.6, margin: 0 }}>
          {investment_snapshot?.verdict ?? insight}
        </p>

        {investment_snapshot && (
          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
              gap: '12px',
              marginTop: '20px',
            }}
          >
            {investment_snapshot.highlights.map((h) => (
              <InvestmentHighlightTile key={h.label} highlight={h} />
            ))}
          </div>
        )}

        {risk_flags.length > 0 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '16px' }}>
            {risk_flags.map((flag) => (
              <Pill key={flag} tone="amber">
                {flag}
              </Pill>
            ))}
          </div>
        )}
      </Card>

      {market_stats.length > 0 && (
        <Section
          title="Market Snapshot"
          subtitle="PropRadar's suburb-level stats — one card per real suburb when this SA2 combines more than one."
        >
          <div style={{ display: 'grid', gap: '16px' }}>
            {market_stats.map((s) => (
              <div
                key={s.suburb_name}
                id={`market-snapshot-${s.suburb_name}`}
                style={{
                  padding: '16px',
                  backgroundColor: colors.pageBg,
                  borderRadius: '8px',
                  scrollMarginTop: '20px',
                }}
              >
                <h4 style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 12px 0' }}>
                  {s.suburb_name}
                  {rentalMarketSuburbs.has(s.suburb_name) && (
                    <button
                      onClick={() => jumpTo(`rental-market-${s.suburb_name}`)}
                      style={{
                        marginLeft: '10px',
                        fontSize: '11px',
                        fontWeight: 600,
                        color: colors.pink,
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        padding: 0,
                        textDecoration: 'underline',
                      }}
                    >
                      See rental detail ↓
                    </button>
                  )}
                </h4>
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 1fr',
                    gap: '16px',
                  }}
                >
                  <div>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: colors.textMuted, marginBottom: '8px', textTransform: 'uppercase' }}>
                      House
                    </div>
                    <StatGrid compact>
                      <Stat label="Median Price" value={fmtCurrency(s.median_house_price)} />
                      <Stat label="Weekly Rent" value={s.median_house_rent_weekly != null ? `$${fmtNum(s.median_house_rent_weekly)}` : '—'} />
                      <Stat label="Gross Yield" value={fmtPct(s.gross_yield_house_pct)} />
                      <Stat label="Growth (1yr)" value={fmtPct(s.growth_house_1y_pct)} />
                      <Stat label="Growth (3yr)" value={fmtPct(s.growth_house_3y_pct)} />
                      <Stat label="Growth (5yr)" value={fmtPct(s.growth_house_5y_pct)} />
                      <Stat label="Days on Market" value={fmtDays(s.days_on_market_house)} />
                      <Stat label="Sales (12mo)" value={fmtNum(s.sales_12mo_house)} />
                    </StatGrid>
                  </div>
                  <div>
                    <div style={{ fontSize: '11px', fontWeight: 600, color: colors.textMuted, marginBottom: '8px', textTransform: 'uppercase' }}>
                      Unit
                    </div>
                    <StatGrid compact>
                      <Stat label="Median Price" value={fmtCurrency(s.median_unit_price)} />
                      <Stat label="Weekly Rent" value={s.median_unit_rent_weekly != null ? `$${fmtNum(s.median_unit_rent_weekly)}` : '—'} />
                      <Stat label="Gross Yield" value={fmtPct(s.gross_yield_unit_pct)} />
                      <Stat label="Growth (1yr)" value={fmtPct(s.growth_unit_1y_pct)} />
                      <Stat label="Growth (3yr)" value={fmtPct(s.growth_unit_3y_pct)} />
                      <Stat label="Growth (5yr)" value={fmtPct(s.growth_unit_5y_pct)} />
                      <Stat label="Days on Market" value={fmtDays(s.days_on_market_unit)} />
                      <Stat label="Sales (12mo)" value={fmtNum(s.sales_12mo_unit)} />
                    </StatGrid>
                  </div>
                </div>

                {(s.median_house_price != null || s.gross_yield_house_pct != null || s.days_on_market_house != null) && (
                  <div
                    style={{
                      display: 'grid',
                      gap: '14px',
                      marginTop: '14px',
                      paddingTop: '14px',
                      borderTop: `1px solid ${colors.border}`,
                    }}
                  >
                    <div style={{ fontSize: '11px', fontWeight: 600, color: colors.textMuted, textTransform: 'uppercase' }}>
                      House vs National Median
                    </div>
                    {s.median_house_price != null && (
                      <ContextRuler
                        label="Median Price"
                        value={s.median_house_price}
                        baseline={nationalMedians.medianHousePrice}
                        min={nationalRanges.medianHousePrice.min}
                        max={nationalRanges.medianHousePrice.max}
                        formatValue={fmtCurrency}
                      />
                    )}
                    {s.gross_yield_house_pct != null && (
                      <ContextRuler
                        label="Gross Yield"
                        value={s.gross_yield_house_pct}
                        baseline={nationalMedians.grossYieldHousePct}
                        min={nationalRanges.grossYieldHousePct.min}
                        max={nationalRanges.grossYieldHousePct.max}
                        formatValue={fmtPct}
                        higherIsBetter
                      />
                    )}
                    {s.days_on_market_house != null && (
                      <ContextRuler
                        label="Days on Market"
                        value={s.days_on_market_house}
                        baseline={nationalMedians.daysOnMarketHouse}
                        min={nationalRanges.daysOnMarketHouse.min}
                        max={nationalRanges.daysOnMarketHouse.max}
                        formatValue={fmtDays}
                        higherIsBetter={false}
                      />
                    )}
                  </div>
                )}

                <div
                  style={{
                    display: 'flex',
                    gap: '20px',
                    marginTop: '14px',
                    paddingTop: '14px',
                    borderTop: `1px solid ${colors.border}`,
                    flexWrap: 'wrap',
                  }}
                >
                  <MiniStat label="Vacancy Rate" value={fmtPct(s.vacancy_rate_pct)} info="Share of rental stock currently vacant — under ~0.6% is tight (favours landlords), over ~1.5% is elevated (favours tenants), based on the national distribution." />
                  <MiniStat label="Sold vs Asking" value={fmtPct(s.sold_vs_asking_pct)} info="Average % difference between final sale price and original asking price across the suburb — positive means homes are selling above asking." />
                  <MiniStat label="Heat Score (House)" value={fmtNum(s.heat_score_house)} info="PropRadar's own proprietary 0-100 demand-heat index — a black-box figure we can't independently audit or derive, used as one input (20% weight) to our own Momentum score." />
                  <MiniStat label="Heat Score (Unit)" value={fmtNum(s.heat_score_unit)} info="PropRadar's own proprietary 0-100 demand-heat index for units — same caveat as the house figure." />
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {momentum.composite.length > 0 && (
        <Section
          title="Momentum & Timing"
          subtitle="In-house signals derived from PropRadar sold/listing data — our substitute for the gated market-cycle endpoints."
          summary={summarizeMomentum(
            momentum.composite[0].phase,
            momentum.supply_scarcity.find((s) => s.suburb_name === momentum.composite[0].suburb_name)?.scarcity_score ?? null,
          )}
        >
          {momentum.sale_velocity.monthly_counts.length >= 2 && (
            <div style={{ marginBottom: '24px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '8px', flexWrap: 'wrap', gap: '8px' }}>
                <h4 style={{ fontSize: '13px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
                  Sale Velocity (monthly sales)
                </h4>
                {momentum.sale_velocity.trend_pct != null && (
                  <span
                    style={{
                      fontSize: '12px',
                      fontWeight: 600,
                      color: momentum.sale_velocity.trend_pct >= 0 ? colors.green : colors.amber,
                    }}
                  >
                    {momentum.sale_velocity.trend_pct >= 0 ? '+' : ''}
                    {momentum.sale_velocity.trend_pct.toFixed(1)}% vs prior 3 months
                  </span>
                )}
              </div>
              <TrendLine
                points={momentum.sale_velocity.monthly_counts.map((m) => ({ label: m.period.slice(2), value: m.count }))}
                color={colors.blue}
                height={110}
              />
            </div>
          )}

          {momentum.neighborhood.signal && (
            <div
              style={{
                marginBottom: '24px',
                padding: '12px 16px',
                borderRadius: '8px',
                backgroundColor: momentum.neighborhood.signal === 'surrounded_by_acceleration' ? colors.greenLight : colors.amberLight,
              }}
            >
              <span
                style={{
                  fontSize: '13px',
                  fontWeight: 600,
                  color: momentum.neighborhood.signal === 'surrounded_by_acceleration' ? colors.green : colors.amber,
                }}
              >
                {momentum.neighborhood.signal === 'surrounded_by_acceleration'
                  ? '▲ Surrounded by acceleration'
                  : '▼ Surrounded by cooling'}
              </span>
              <span style={{ fontSize: '12px', color: colors.textSecondary, marginLeft: '8px' }}>
                {momentum.neighborhood.counts.accelerating} of {momentum.neighborhood.total_neighbors} neighboring
                suburbs are accelerating, {momentum.neighborhood.counts.cooling} cooling
              </span>
            </div>
          )}

          <div style={{ display: 'grid', gap: '16px' }}>
            {momentum.composite.map((m) => {
              const scarcity = momentum.supply_scarcity.find((s) => s.suburb_name === m.suburb_name)
              const quadrant = momentum.growth_yield_quadrant.find((q) => q.suburb_name === m.suburb_name)
              const cycle = momentum.property_cycle.find((c) => c.suburb_name === m.suburb_name)
              return (
                <div key={m.suburb_name} style={{ padding: '16px', backgroundColor: colors.pageBg, borderRadius: '8px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
                    <h4 style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
                      {m.suburb_name}
                    </h4>
                    <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                      {quadrant?.quadrant && <Pill tone="blue">{QUADRANT_TAG_LABEL[quadrant.quadrant]}</Pill>}
                      <Pill tone={momentumPhaseTone(m.phase)}>
                        {momentumPhaseArrow(m.phase)} {m.phase ? titleCase(m.phase) : 'Unknown'}
                        {m.momentum_score != null && ` (${m.momentum_score > 0 ? '+' : ''}${m.momentum_score.toFixed(1)})`}
                      </Pill>
                    </div>
                  </div>

                  {cycle?.position && (
                    <div style={{ display: 'flex', justifyContent: 'center', margin: '4px 0 20px' }}>
                      <div style={{ maxWidth: '340px', width: '100%' }}>
                        <div style={{ fontSize: '11px', fontWeight: 600, color: colors.textMuted, marginBottom: '8px', textTransform: 'uppercase', textAlign: 'center' }}>
                          Property Cycle Position
                        </div>
                        <PropertyCycleClock position={cycle.position} confidence={cycle.confidence} />
                      </div>
                    </div>
                  )}

                  <div style={{ fontSize: '11px', fontWeight: 600, color: colors.textMuted, marginBottom: '8px', textTransform: 'uppercase' }}>
                    Component Signals (−1.00 cooling .. +1.00 accelerating)
                  </div>
                  <StatGrid>
                    <Stat
                      label="Sale Velocity"
                      value={fmtSignal(m.components.sale_velocity.signal)}
                      info="How much monthly sale volume changed vs the prior 3 months, on a -1 (cooling) to +1 (accelerating) scale. Weighted 30% of the overall momentum score — the most responsive input."
                    />
                    <Stat
                      label="Price Growth"
                      value={fmtSignal(m.components.growth.signal)}
                      info="1-year median price growth, scaled so +/-20% maps to the full -1..+1 range. Weighted 25% of momentum."
                    />
                    <Stat
                      label="Supply Scarcity"
                      value={fmtSignal(m.components.supply_scarcity.signal)}
                      info="This suburb's 0-100 scarcity score re-centred so 50 (market-typical) reads as 0. Weighted 25% of momentum."
                    />
                    <Stat
                      label="Heat Score"
                      value={fmtSignal(m.components.heat_score.signal)}
                      info="PropRadar's own demand-heat index (0-100), re-centred the same way as scarcity. Weighted 20% of momentum — the only input we can't audit or derive ourselves."
                    />
                  </StatGrid>

                  {scarcity && (
                    <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: `1px solid ${colors.border}` }}>
                      <div style={{ fontSize: '11px', fontWeight: 600, color: colors.textMuted, marginBottom: '8px', textTransform: 'uppercase' }}>
                        Supply Scarcity Breakdown — {fmtScore100(scarcity.scarcity_score)}
                      </div>
                      <HorizontalBars
                        items={[
                          {
                            label: 'Stock on Market',
                            value: scarcity.components.stock_on_market_score ?? 0,
                            formattedValue: fmtScore100(scarcity.components.stock_on_market_score),
                            info: '% of dwelling stock currently listed for sale, scored 0 (abundant) to 100 (scarce) against the national median (~0.36%). 35% weight in the scarcity score.',
                          },
                          {
                            label: 'Inventory Months',
                            value: scarcity.components.inventory_months_score ?? 0,
                            formattedValue: fmtScore100(scarcity.components.inventory_months_score),
                            info: 'Months of stock at the current sales pace, scored against the national median (~2.4 months). 35% weight in the scarcity score.',
                          },
                          {
                            label: 'Building Approvals',
                            value: scarcity.components.building_approvals_score ?? 0,
                            formattedValue: fmtScore100(scarcity.components.building_approvals_score),
                            info: 'New dwellings approved per 1,000 residents in the last year, scored against the national median (~3.4) — the only forward-looking (vs live-snapshot) input. 30% weight in the scarcity score.',
                          },
                        ]}
                        max={100}
                        color={colors.blue}
                      />
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </Section>
      )}

      <Section
        title="Investment Outlook"
        subtitle="Growth signals relevant to timing an investment decision"
        summary={summarizeOutlook(investment_outlook.pop_growth_proj_pct)}
      >
        <StatGrid>
          {show_census_sections && (
            <Stat label={`Population Growth (5yr, ${census_year} Census)`} value={fmtPct(investment_outlook.pop_growth_5yr)} />
          )}
          <Stat label="Projected Population 2026" value={fmtNum(investment_outlook.pop_proj_2026)} />
          <Stat label="Projected Population 2031" value={fmtNum(investment_outlook.pop_proj_2031)} />
          <Stat label="Projected Growth to 2031" value={fmtPct(investment_outlook.pop_growth_proj_pct)} />
          <Stat label="Dwellings Approved (1yr)" value={fmtNum(investment_outlook.building_approvals_1yr)} />
          <Stat label="Distance to CBD" value={fmtKm(investment_outlook.distance_to_cbd_km)} />
        </StatGrid>

        {(() => {
          const points = [
            { label: 'Now', value: demographics.population },
            { label: '2026', value: investment_outlook.pop_proj_2026 },
            { label: '2031', value: investment_outlook.pop_proj_2031 },
          ].filter((p): p is { label: string; value: number } => p.value != null)
          return points.length >= 2 ? (
            <div style={{ marginTop: '20px' }}>
              <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '4px' }}>
                Population Trajectory
              </div>
              <TrendLine points={points} />
            </div>
          ) : null
        })()}
      </Section>

      {/* Housing Market — the headline section */}
      <Section
        title="Housing Market"
        subtitle="Sold-listing data from PropRadar. See Market Snapshot above for median price, rent, and yield."
        summary={momentum.growth_yield_quadrant[0]?.label ?? null}
      >
        <StatGrid>
          <Stat label="Dwellings Approved (1yr)" value={fmtNum(property_market.building_approvals_1yr)} />
        </StatGrid>

        {chartableSpecs.length > 0 && (
          <div id="median-sold-price-over-time" style={{ marginTop: '24px', scrollMarginTop: '20px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', flexWrap: 'wrap', gap: '8px', marginBottom: '4px' }}>
              <h4 style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
                Median Sold Price Over Time
              </h4>
              <select
                value={activeSpecLabel ?? ''}
                onChange={(e) => setSelectedSpecLabel(e.target.value)}
                style={{
                  fontSize: '13px',
                  padding: '4px 8px',
                  borderRadius: '6px',
                  border: `1px solid ${colors.border}`,
                  backgroundColor: colors.cardBg,
                  color: colors.textPrimary,
                }}
              >
                {chartableSpecs.map((s) => (
                  <option key={s.label} value={s.label}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <p style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '10px' }}>
              From PropRadar sold listings, monthly, for this exact bed/bath/garage/type combo — showing however
              much history is available (up to 5 years). Only specs with at least two months of sales are listed.
            </p>
            {activeSpecHistory && (
              <TrendLine
                points={activeSpecHistory.history.map((p) => ({ label: p.period, value: p.median_price }))}
                width={600}
              />
            )}
          </div>
        )}

        {property_market.detailed_specs.length > 0 && (
          <div style={{ marginTop: '24px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, marginBottom: '4px' }}>
              Median Price by Exact Spec
            </h4>
            <p style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '10px' }}>
              Bed / bath / garage combinations with at least one sold listing, sorted progressively (1 Bed/1 Bath,
              1 Bed/2 Bath, 2 Bed/1 Bath, ...). Underlined specs have a price trend below — click to jump to it.
            </p>
            <HorizontalBars
              color={colors.blue}
              items={property_market.detailed_specs.map((s) => ({
                label: `${s.label} (${s.sale_count} sold)`,
                value: s.median_price,
                formattedValue: fmtCurrency(s.median_price),
                onClick: chartableSpecLabels.has(s.label) ? () => jumpToSpec(s.label) : undefined,
              }))}
            />
          </div>
        )}

        {property_market.land_size_breakdown.length > 0 && (
          <div style={{ marginTop: '24px' }}>
            <h4 style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, marginBottom: '10px' }}>
              Land Size (Sold Listings)
            </h4>
            <HorizontalBars
              color={colors.green}
              items={property_market.land_size_breakdown.map((b) => ({
                label: b.label,
                value: b.sale_count,
                formattedValue: `${b.sale_count} sold`,
              }))}
            />
          </div>
        )}

        <div style={{ marginTop: '24px' }}>
          <h4 style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, marginBottom: '10px' }}>
            Recent Sales
          </h4>
          {property_market.recent_sales_available ? (
            <div style={{ display: 'grid', gap: '8px' }}>
              {property_market.recent_sales.map((sale, i) => (
                <div
                  key={i}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    backgroundColor: colors.pageBg,
                    borderRadius: '8px',
                    fontSize: '14px',
                  }}
                >
                  <span style={{ color: colors.textPrimary }}>{sale.address ?? 'Address withheld'}</span>
                  <span style={{ color: colors.textSecondary }}>
                    {sale.bedrooms != null && `${sale.bedrooms} bed · `}
                    {fmtCurrency(sale.sold_price)}
                    {sale.sold_date && ` · ${sale.sold_date}`}
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div
              style={{
                padding: '16px',
                backgroundColor: colors.pageBg,
                borderRadius: '8px',
                fontSize: '14px',
                color: colors.textMuted,
              }}
            >
              No sold-listing data yet — connect a PropRadar API key to show recent sales by bedroom count,
              price, and date here.
            </div>
          )}
        </div>
      </Section>

      {rental_market.length > 0 && (
        <Section
          title="Rental Market"
          subtitle="PropRadar's suburb-level rent and yield, visualised rather than repeating Market Snapshot's numbers. House/unit is the finest granularity available — PropRadar has no per-bed/bath rental-listings endpoint. Trend charts fill in as more monthly snapshots accumulate."
          summary={summarizeVacancy(rental_market[0]?.history[rental_market[0].history.length - 1]?.vacancy_rate_pct)}
        >
          <div style={{ display: 'grid', gap: '16px' }}>
            {rental_market.map((r) => {
              const latest = r.history[r.history.length - 1]
              const rentPoints = r.history
                .map((h) => ({ label: h.period, value: h.median_house_rent_weekly }))
                .filter((p): p is { label: string; value: number } => p.value != null)
              const vacancyPoints = r.history
                .map((h) => ({ label: h.period, value: h.vacancy_rate_pct }))
                .filter((p): p is { label: string; value: number } => p.value != null)
              const rentBars = [
                latest.median_house_rent_weekly != null && { label: 'House', value: latest.median_house_rent_weekly, formattedValue: `$${fmtNum(latest.median_house_rent_weekly)}` },
                latest.median_unit_rent_weekly != null && { label: 'Unit', value: latest.median_unit_rent_weekly, formattedValue: `$${fmtNum(latest.median_unit_rent_weekly)}` },
              ].filter((b): b is { label: string; value: number; formattedValue: string } => !!b)
              const yieldBars = [
                latest.gross_yield_house_pct != null && { label: 'House', value: latest.gross_yield_house_pct, formattedValue: fmtPct(latest.gross_yield_house_pct) },
                latest.gross_yield_unit_pct != null && { label: 'Unit', value: latest.gross_yield_unit_pct, formattedValue: fmtPct(latest.gross_yield_unit_pct) },
              ].filter((b): b is { label: string; value: number; formattedValue: string } => !!b)
              return (
                <div
                  key={r.suburb_name}
                  id={`rental-market-${r.suburb_name}`}
                  style={{
                    padding: '16px',
                    backgroundColor: colors.pageBg,
                    borderRadius: '8px',
                    scrollMarginTop: '20px',
                  }}
                >
                  <h4 style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 16px 0' }}>
                    {r.suburb_name}
                    {marketSnapshotSuburbs.has(r.suburb_name) && (
                      <button
                        onClick={() => jumpTo(`market-snapshot-${r.suburb_name}`)}
                        style={{
                          marginLeft: '10px',
                          fontSize: '11px',
                          fontWeight: 600,
                          color: colors.pink,
                          background: 'none',
                          border: 'none',
                          cursor: 'pointer',
                          padding: 0,
                          textDecoration: 'underline',
                        }}
                      >
                        ↑ See price & growth
                      </button>
                    )}
                  </h4>

                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
                    {rentBars.length > 0 && (
                      <div>
                        <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>Weekly Rent</div>
                        <HorizontalBars color={colors.blue} items={rentBars} />
                      </div>
                    )}
                    {yieldBars.length > 0 && (
                      <div>
                        <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>Gross Yield</div>
                        <HorizontalBars color={colors.green} items={yieldBars} />
                      </div>
                    )}
                  </div>

                  <div
                    style={{
                      display: 'flex',
                      gap: '20px',
                      marginTop: '16px',
                      paddingTop: '16px',
                      borderTop: `1px solid ${colors.border}`,
                      flexWrap: 'wrap',
                    }}
                  >
                    <MiniStat label="House Days on Market" value={fmtDays(latest.days_on_market_house)} />
                    <MiniStat label="Unit Days on Market" value={fmtDays(latest.days_on_market_unit)} />
                    <MiniStat label="Vacancy Rate" value={fmtPct(latest.vacancy_rate_pct)} />
                  </div>

                  {rentPoints.length >= 2 || vacancyPoints.length >= 2 ? (
                    <div style={{ marginTop: '20px', display: 'grid', gap: '20px' }}>
                      {rentPoints.length >= 2 && (
                        <div>
                          <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '4px' }}>
                            House Weekly Rent Over Time
                          </div>
                          <TrendLine points={rentPoints} />
                        </div>
                      )}
                      {vacancyPoints.length >= 2 && (
                        <div>
                          <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '4px' }}>
                            Vacancy Rate Over Time
                          </div>
                          <TrendLine points={vacancyPoints} />
                        </div>
                      )}
                    </div>
                  ) : (
                    <p style={{ color: colors.textMuted, fontSize: '12px', marginTop: '12px' }}>
                      Only one monthly snapshot so far — a month-over-month trend will appear once this data has
                      been refreshed in a later calendar month.
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        </Section>
      )}

      {show_census_sections && regional_comparison && (
        <Section
          title={`${primarySuburbName(sa2_name)} vs ${regional_comparison.region_label} Average`}
          subtitle={`Compared against the ${regional_comparison.region_label} region average (ABS SA4 level)`}
          dataVintage={`${census_year} Census`}
        >
          <div style={{ display: 'grid', gap: '14px' }}>
            {regional_comparison.metrics.map((m) => {
              const fmt = (v: number) => (m.format === 'currency' ? fmtCurrency(v) : fmtPct(v))
              const max = Math.max(m.suburb_value, m.region_average) * 1.15 || 1
              return (
                <div key={m.key}>
                  <div
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      fontSize: '13px',
                      marginBottom: '4px',
                    }}
                  >
                    <span style={{ color: colors.textSecondary }}>{m.label}</span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
                    <span style={{ fontSize: '12px', color: colors.textMuted, width: '90px' }}>This Suburb</span>
                    <div style={{ flex: 1, height: '8px', borderRadius: '999px', backgroundColor: colors.pageBg }}>
                      <div
                        style={{
                          height: '100%',
                          width: `${Math.min((m.suburb_value / max) * 100, 100)}%`,
                          backgroundColor: colors.pink,
                          borderRadius: '999px',
                        }}
                      />
                    </div>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: colors.textPrimary, width: '80px', textAlign: 'right' }}>
                      {fmt(m.suburb_value)}
                    </span>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <span style={{ fontSize: '12px', color: colors.textMuted, width: '90px' }}>
                      {regional_comparison.region_label} Avg
                    </span>
                    <div style={{ flex: 1, height: '8px', borderRadius: '999px', backgroundColor: colors.pageBg }}>
                      <div
                        style={{
                          height: '100%',
                          width: `${Math.min((m.region_average / max) * 100, 100)}%`,
                          backgroundColor: colors.blue,
                          borderRadius: '999px',
                        }}
                      />
                    </div>
                    <span style={{ fontSize: '13px', fontWeight: 600, color: colors.textPrimary, width: '80px', textAlign: 'right' }}>
                      {fmt(m.region_average)}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        </Section>
      )}

      {show_census_sections && (
      <>
      <Section title="Demographics" dataVintage={`${census_year} Census`}>
        <StatGrid>
          <Stat label="Population" value={fmtNum(demographics.population)} />
          <Stat label="Median Age" value={demographics.median_age != null ? demographics.median_age.toFixed(0) : '—'} />
          <Stat label="Avg Household Size" value={demographics.avg_household_size != null ? demographics.avg_household_size.toFixed(1) : '—'} />
        </StatGrid>

        {(() => {
          const items = [
            { label: 'Families with Children', value: demographics.families_with_children_pct },
            { label: 'Born Overseas', value: demographics.overseas_born_pct },
            { label: 'Moved in Last Year', value: demographics.moved_in_1yr_pct },
            { label: 'Moved in Last 5 Years', value: demographics.moved_in_5yr_pct },
            { label: 'University Educated', value: demographics.uni_degree_pct },
            { label: 'Professionals & Managers', value: demographics.professionals_managers_pct },
          ].filter((i): i is { label: string; value: number } => i.value != null)
          return items.length > 0 ? (
            <div style={{ marginTop: '20px' }}>
              <HorizontalBars
                isPercent
                items={items.map((i) => ({ ...i, formattedValue: fmtPct(i.value) }))}
              />
            </div>
          ) : null
        })()}
      </Section>

      <Section title="Economy" dataVintage={`${census_year} Census`}>
        <StatGrid>
          <Stat label="Median Income" value={fmtCurrency(economy.median_income)} />
          <Stat label="Unemployment Rate" value={fmtPct(economy.unemployment_pct)} />
        </StatGrid>
      </Section>

      <Section title="Housing" dataVintage={`${census_year} Census`}>
        <StatGrid>
          <Stat label="Median Weekly Rent" value={fmtCurrency(housing.median_rent_weekly)} />
          <Stat label="Median Monthly Mortgage" value={fmtCurrency(housing.median_mortgage_monthly)} />
          <Stat label="One-Bedroom Dwellings" value={fmtPct(housing.one_bedroom_pct)} />
          <Stat label="Social Housing" value={fmtPct(housing.social_housing_pct)} />
        </StatGrid>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '32px', marginTop: '20px' }}>
          {housing.renters_pct != null && housing.owners_pct != null && (
            <div>
              <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>
                Tenure
                {housing.owners_pct > 0 &&
                  ` — Renter:Owner Ratio ${(housing.renters_pct / housing.owners_pct).toFixed(2)} : 1`}
              </div>
              <DonutChart
                segments={[
                  { label: 'Renters', value: housing.renters_pct, color: colors.pink },
                  { label: 'Owners', value: housing.owners_pct, color: colors.blue },
                ]}
              />
            </div>
          )}

          {housing.separate_house_pct != null && housing.flat_apartment_pct != null && (
            <div>
              <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>Dwelling Type</div>
              <DonutChart
                segments={[
                  { label: 'Separate Houses', value: housing.separate_house_pct, color: colors.blue },
                  { label: 'Flats & Apartments', value: housing.flat_apartment_pct, color: colors.green },
                  ...(100 - housing.separate_house_pct - housing.flat_apartment_pct > 0.5
                    ? [{ label: 'Other (townhouses etc.)', value: 100 - housing.separate_house_pct - housing.flat_apartment_pct, color: colors.amber }]
                    : []),
                ]}
              />
            </div>
          )}
        </div>

        {(() => {
          const items = [
            { label: 'High Rent Stress', value: housing.high_rent_stress_pct },
            { label: 'High Mortgage Stress', value: housing.high_mortgage_stress_pct },
          ].filter((i): i is { label: string; value: number } => i.value != null)
          return items.length > 0 ? (
            <div style={{ marginTop: '20px' }}>
              <HorizontalBars
                color={colors.amber}
                isPercent
                items={items.map((i) => ({ ...i, formattedValue: fmtPct(i.value) }))}
              />
            </div>
          ) : null
        })()}

        {housing.by_house_type.length > 0 && (
          <div style={{ marginTop: '20px' }}>
            <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>
              Median Sold Price by House Type (PropRadar)
            </div>
            <HorizontalBars
              color={colors.blue}
              items={housing.by_house_type.map((b) => ({
                label: `${b.label} (${b.sale_count} sold)`,
                value: b.median_price,
                formattedValue: fmtCurrency(b.median_price),
              }))}
            />
          </div>
        )}
      </Section>
      </>
      )}

      <Section
        title="Community & Socio-Economic Profile"
        subtitle="ABS SEIFA deciles (1 = most disadvantaged, 10 = most advantaged, relative to all of Australia)"
        dataVintage={`${census_year} SEIFA`}
      >
        {(() => {
          const items = [
            {
              label: 'Disadvantage (IRSD)',
              value: community.seifa_irsd_decile,
              info: 'ABS Index of Relative Socio-Economic Disadvantage — ranks areas on disadvantage indicators only (low income, unemployment, low-skill jobs). Decile 1 = most disadvantaged nationally.',
            },
            {
              label: 'Advantage/Disadvantage (IRSAD)',
              value: community.seifa_irsad_decile,
              info: "ABS Index of Relative Socio-Economic Advantage and Disadvantage — a broader index than IRSD, weighing both advantage (high income, skilled jobs) and disadvantage indicators.",
            },
            {
              label: 'Economic Resources (IER)',
              value: community.seifa_ier_decile,
              info: "ABS Index of Economic Resources — focuses on income, housing costs, and asset-related indicators, excluding education/occupation.",
            },
            {
              label: 'Education & Occupation (IEO)',
              value: community.seifa_ieo_decile,
              info: "ABS Index of Education and Occupation — measures the qualification and job-skill profile of residents, excluding income.",
            },
          ].filter((i): i is { label: string; value: number; info: string } => i.value != null)
          return items.length > 0 ? (
            <HorizontalBars
              max={10}
              color={colors.green}
              items={items.map((i) => ({ ...i, formattedValue: fmtDecile(i.value) }))}
            />
          ) : (
            <p style={{ color: colors.textMuted, fontSize: '14px' }}>No SEIFA data loaded for this SA2 yet.</p>
          )
        })()}
      </Section>

      <Section title="Government Investment" subtitle="Nearby infrastructure projects from Infrastructure Australia / iPAMS">
        {government_investment.projects.length === 0 ? (
          <p style={{ color: colors.textMuted, fontSize: '14px' }}>No linked infrastructure projects found nearby.</p>
        ) : (
          <div style={{ display: 'grid', gap: '10px' }}>
            {government_investment.projects.map((p) => (
              <div
                key={p.name}
                style={{
                  padding: '14px',
                  backgroundColor: colors.pageBg,
                  borderRadius: '8px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <strong style={{ color: colors.textPrimary, fontSize: '14px' }}>{p.name}</strong>
                  <Pill tone={p.status === 'under_construction' ? 'green' : p.status === 'approved' ? 'blue' : 'amber'}>
                    {titleCase(p.status)}
                  </Pill>
                </div>
                <div style={{ color: colors.textSecondary, fontSize: '13px', marginTop: '4px' }}>
                  {titleCase(p.type)}
                  {p.value_aud != null && ` · ${fmtCurrency(p.value_aud)}`}
                  {p.timing && ` · ${p.timing}`}
                </div>
              </div>
            ))}
          </div>
        )}
      </Section>

      <Section
        title="Schools"
        subtitle={
          schools.local.length > 0 || schools.nearby.length > 0
            ? 'Public and private schools with an ABS/ACARA ICSEA ranking only. Surrounding suburbs capped to the top 10 by percentile.'
            : "No rated schools found for this SA2 (ACARA's School ICSEA data requires accepting commercial-use terms we haven't)."
        }
      >
        {schools.avg_school_icsea != null && !schools.state_percentile && (
          <StatGrid>
            <Stat label="Avg ICSEA Index (legacy aggregate)" value={Math.round(schools.avg_school_icsea).toString()} />
          </StatGrid>
        )}

        <div style={{ display: 'grid', gap: '24px', marginTop: schools.avg_school_icsea != null ? '20px' : 0 }}>
          <div>
            <h4 style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, marginBottom: '10px' }}>
              In {primarySuburbName(sa2_name)} ({schools.local.length})
            </h4>
            {schools.local.length === 0 ? (
              <p style={{ color: colors.textMuted, fontSize: '14px' }}>No schools found in this suburb.</p>
            ) : (
              <div style={{ display: 'grid', gap: '8px' }}>
                {schools.local.map((s, i) => (
                  <SchoolRow key={`${s.name}-${i}`} school={s} />
                ))}
              </div>
            )}
          </div>

          {schools.nearby.length > 0 && (
            <div>
              <h4 style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, marginBottom: '10px' }}>
                In Surrounding Suburbs ({schools.nearby.length})
              </h4>
              <div style={{ display: 'grid', gap: '8px' }}>
                {schools.nearby.map((s, i) => (
                  <SchoolRow key={`${s.name}-${i}`} school={s} showSuburb />
                ))}
              </div>
            </div>
          )}
        </div>
      </Section>

      <Section title="Amenities & Lifestyle" subtitle="Counts within the suburb boundary (Overture Maps)">
        {(() => {
          const items = [
            { label: 'Cafes', value: amenities.cafes },
            { label: 'Bakeries', value: amenities.bakeries },
            { label: 'Restaurants', value: amenities.restaurants },
            { label: 'Fast Food', value: amenities.fast_food },
            { label: 'Supermarkets', value: amenities.supermarkets },
            { label: 'Shopping Centres', value: amenities.shopping_centres },
            { label: 'Parks', value: amenities.parks },
            { label: 'Gyms', value: amenities.gyms },
            { label: 'Hospitals & Clinics', value: amenities.hospitals },
            { label: 'Pharmacies', value: amenities.pharmacies },
          ].filter((i): i is { label: string; value: number } => i.value != null)
          return items.length > 0 ? (
            <HorizontalBars color={colors.blue} items={items} />
          ) : (
            <p style={{ color: colors.textMuted, fontSize: '14px' }}>No amenity data loaded for this SA2 yet.</p>
          )
        })()}
        {Object.keys(amenities.cuisines).length > 0 && (
          <div style={{ marginTop: '16px' }}>
            <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>Cuisine breakdown</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {Object.entries(amenities.cuisines).map(([cuisine, count]) => (
                <Pill key={cuisine} tone="blue">
                  {titleCase(cuisine)} ({count})
                </Pill>
              ))}
            </div>
          </div>
        )}
      </Section>

      <Section
        title="Points of Interest"
        subtitle="Hospitals, shopping centres, stadiums & arenas, and attractions from Overture Maps — up to 5 per category, not exhaustive. Public/private hospital tagging is a best-effort name heuristic, not authoritative — see a hospital's own site to confirm."
      >
        {points_of_interest.local.length === 0 && points_of_interest.nearby.length === 0 ? (
          <p style={{ color: colors.textMuted, fontSize: '14px' }}>No points of interest loaded for this SA2 yet.</p>
        ) : (
          <div style={{ display: 'grid', gap: '24px' }}>
            {POI_GROUPS.map((group) => {
              const localInGroup = points_of_interest.local.filter((p) => p.group === group)
              const nearbyInGroup = points_of_interest.nearby.filter((p) => p.group === group)
              if (localInGroup.length === 0 && nearbyInGroup.length === 0) return null
              return (
                <div key={group}>
                  <h4 style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, marginBottom: '10px' }}>
                    {group}
                  </h4>
                  <div style={{ display: 'grid', gap: '6px' }}>
                    {localInGroup.map((p, i) => (
                      <PoiRow key={`local-${i}`} poi={p} />
                    ))}
                    {nearbyInGroup.map((p, i) => (
                      <PoiRow key={`nearby-${i}`} poi={p} showSuburb />
                    ))}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </Section>

      <Section title="Transport & Connectivity" subtitle={`PT stop counts are from the current GTFS feed; commute-mode and zero-car figures are from the ${census_year} Census.`}>
        {show_census_sections && (
          <StatGrid>
            <Stat label="Zero-Car Households" value={fmtPct(transport.zero_car_dwellings_pct)} />
          </StatGrid>
        )}

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '32px', marginTop: '20px' }}>
          {(() => {
            if (!show_census_sections) return null
            const car = transport.car_commute_pct
            const pt = transport.pt_commute_pct
            const wfh = transport.work_from_home_pct
            if (car == null && pt == null && wfh == null) return null
            const segments = [
              { label: 'Car', value: car ?? 0, color: colors.blue },
              { label: 'Public Transport', value: pt ?? 0, color: colors.pink },
              { label: 'Work From Home', value: wfh ?? 0, color: colors.green },
            ]
            const other = 100 - segments.reduce((s, x) => s + x.value, 0)
            if (other > 0.5) segments.push({ label: 'Other', value: other, color: colors.textMuted })
            return (
              <div>
                <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>
                  Commute Mode ({census_year} Census)
                </div>
                <DonutChart segments={segments} />
              </div>
            )
          })()}

          {(() => {
            const items = [
              { label: 'Train Stops', value: transport.pt_stop_train },
              { label: 'Tram Stops', value: transport.pt_stop_tram },
              { label: 'Bus Stops', value: transport.pt_stop_bus },
              { label: 'Ferry Stops', value: transport.pt_stop_ferry },
            ].filter((i): i is { label: string; value: number } => i.value != null)
            return items.length > 0 ? (
              <div style={{ minWidth: '220px', flex: 1 }}>
                <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '8px' }}>PT Stops</div>
                <HorizontalBars color={colors.pink} items={items} />
              </div>
            ) : null
          })()}
        </div>
      </Section>

      <Card
        style={{
          textAlign: 'center',
          backgroundColor: colors.textPrimary,
          border: 'none',
        }}
      >
        <h2 style={{ fontSize: '26px', marginBottom: '12px', color: '#fff' }}>Unlock Full Report</h2>
        <p style={{ fontSize: '15px', color: '#D1D5DB', marginBottom: '20px' }}>
          Get detailed analysis, peer comparisons, and actionable investment advice
        </p>
        <button
          style={{
            padding: '14px 40px',
            fontSize: '16px',
            fontWeight: 600,
            backgroundColor: colors.pink,
            color: 'white',
            border: 'none',
            borderRadius: '6px',
            cursor: 'pointer',
          }}
        >
          Unlock for $9
        </button>
      </Card>
    </>
  )
}
