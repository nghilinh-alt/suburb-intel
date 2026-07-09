import { ReactNode, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { DonutChart, HorizontalBars, TrendLine } from '../components/Charts'
import { colors } from '../lib/theme'

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
  domain_median_house_price: number | null
  domain_median_unit_price: number | null
  domain_days_on_market: number | null
  domain_clearance_rate: number | null
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

interface LocalPoiEntry {
  name: string
  group: string
  hospital_type: 'Public' | 'Private' | null
}

interface NearbyPoiEntry extends LocalPoiEntry {
  suburb: string
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
  insight: string
  risk_flags: string[]
  tags: string[]
  regional_comparison: RegionalComparison | null
  location: { distance_to_cbd_km: number | null }
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

// ---------------------------------------------------------------------------
// Shared building blocks
// ---------------------------------------------------------------------------

function Card({ children, style }: { children: ReactNode; style?: React.CSSProperties }) {
  return (
    <div
      style={{
        backgroundColor: colors.cardBg,
        border: `1px solid ${colors.border}`,
        borderRadius: '12px',
        boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
        padding: '24px',
        ...style,
      }}
    >
      {children}
    </div>
  )
}

function Section({
  title,
  subtitle,
  dataVintage,
  children,
}: {
  title: string
  subtitle?: string
  dataVintage?: string
  children: ReactNode
}) {
  return (
    <Card style={{ marginBottom: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        <h3 style={{ fontSize: '18px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
          {title}
        </h3>
        {dataVintage && (
          <span
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: colors.amber,
              backgroundColor: colors.amberLight,
              padding: '3px 9px',
              borderRadius: '999px',
            }}
            title="This section's figures are only as recent as this data source's last update."
          >
            {dataVintage}
          </span>
        )}
      </div>
      {subtitle && (
        <p style={{ fontSize: '13px', color: colors.textMuted, marginTop: '4px', marginBottom: '16px' }}>
          {subtitle}
        </p>
      )}
      <div style={{ marginTop: subtitle ? 0 : '16px' }}>{children}</div>
    </Card>
  )
}

function StatGrid({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
        gap: '16px',
      }}
    >
      {children}
    </div>
  )
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '4px' }}>{label}</div>
      <div style={{ fontSize: '20px', fontWeight: 600, color: colors.textPrimary }}>{value}</div>
    </div>
  )
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: '11px', color: colors.textMuted }}>{label}</div>
      <div style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary }}>{value}</div>
    </div>
  )
}

function Pill({ children, tone = 'blue' }: { children: ReactNode; tone?: 'blue' | 'pink' | 'green' | 'amber' }) {
  const toneColors = {
    blue: { bg: colors.blueLight, fg: colors.blue },
    pink: { bg: colors.pinkLight, fg: colors.pink },
    green: { bg: colors.greenLight, fg: colors.green },
    amber: { bg: colors.amberLight, fg: colors.amber },
  }[tone]
  return (
    <span
      style={{
        display: 'inline-block',
        backgroundColor: toneColors.bg,
        color: toneColors.fg,
        padding: '6px 12px',
        borderRadius: '999px',
        fontSize: '13px',
        fontWeight: 500,
      }}
    >
      {children}
    </span>
  )
}

const POI_GROUPS = ['Hospital', 'Shopping Centre', 'Stadium & Arena', 'Attraction']

function PoiRow({ poi, showSuburb = false }: { poi: NearbyPoiEntry | LocalPoiEntry; showSuburb?: boolean }) {
  const suburb = showSuburb ? (poi as NearbyPoiEntry).suburb : undefined
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
        {suburb && <span style={{ color: colors.textMuted }}> · {suburb}</span>}
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
    insight,
    risk_flags,
    tags,
    regional_comparison,
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
  const activeSpecLabel =
    selectedSpecLabel && property_market.price_history_by_spec.some((s) => s.label === selectedSpecLabel)
      ? selectedSpecLabel
      : property_market.price_history_by_spec[0]?.label ?? null
  const activeSpecHistory = property_market.price_history_by_spec.find((s) => s.label === activeSpecLabel) ?? null

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
        <p style={{ fontSize: '16px', color: colors.textSecondary, lineHeight: 1.6, margin: 0 }}>{insight}</p>
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
                style={{
                  padding: '16px',
                  backgroundColor: colors.pageBg,
                  borderRadius: '8px',
                }}
              >
                <h4 style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 12px 0' }}>
                  {s.suburb_name}
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
                    <StatGrid>
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
                    <StatGrid>
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
                  <MiniStat label="Vacancy Rate" value={fmtPct(s.vacancy_rate_pct)} />
                  <MiniStat label="Sold vs Asking" value={fmtPct(s.sold_vs_asking_pct)} />
                  <MiniStat label="Heat Score (House)" value={fmtNum(s.heat_score_house)} />
                  <MiniStat label="Heat Score (Unit)" value={fmtNum(s.heat_score_unit)} />
                </div>
              </div>
            ))}
          </div>
        </Section>
      )}

      <Section title="Investment Outlook" subtitle="Growth signals relevant to timing an investment decision">
        <StatGrid>
          <Stat label={`Population Growth (5yr, ${census_year} Census)`} value={fmtPct(investment_outlook.pop_growth_5yr)} />
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
        subtitle="Median prices sourced from Domain; per-listing sold data below is ready for PropRadar once connected."
      >
        <StatGrid>
          <Stat label="Median House Price" value={fmtCurrency(property_market.domain_median_house_price)} />
          <Stat label="Median Unit Price" value={fmtCurrency(property_market.domain_median_unit_price)} />
          <Stat label="Days on Market" value={fmtDays(property_market.domain_days_on_market)} />
          <Stat
            label="Auction Clearance Rate"
            value={
              property_market.domain_clearance_rate != null
                ? fmtPct(property_market.domain_clearance_rate * 100)
                : '—'
            }
          />
          <Stat label="Dwellings Approved (1yr)" value={fmtNum(property_market.building_approvals_1yr)} />
        </StatGrid>

        {property_market.domain_median_house_price != null && property_market.domain_median_unit_price != null && (
          <div style={{ marginTop: '24px' }}>
            <HorizontalBars
              color={colors.pink}
              items={[
                { label: 'Median House Price', value: property_market.domain_median_house_price, formattedValue: fmtCurrency(property_market.domain_median_house_price) },
                { label: 'Median Unit Price', value: property_market.domain_median_unit_price, formattedValue: fmtCurrency(property_market.domain_median_unit_price) },
              ]}
            />
          </div>
        )}

        {property_market.price_history_by_spec.length > 0 && (
          <div style={{ marginTop: '24px' }}>
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
                {property_market.price_history_by_spec.map((s) => (
                  <option key={s.label} value={s.label}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>
            <p style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '10px' }}>
              From PropRadar sold listings, monthly, for this exact bed/bath/garage/type combo — showing however
              much history is available (up to 5 years).
            </p>
            {activeSpecHistory && activeSpecHistory.history.length >= 2 ? (
              <TrendLine
                points={activeSpecHistory.history.map((p) => ({ label: p.period, value: p.median_price }))}
                width={600}
              />
            ) : (
              <p style={{ color: colors.textMuted, fontSize: '13px' }}>
                Not enough sold listings for this spec yet to chart a trend.
              </p>
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
              1 Bed/2 Bath, 2 Bed/1 Bath, ...).
            </p>
            <HorizontalBars
              color={colors.blue}
              items={property_market.detailed_specs.map((s) => ({
                label: `${s.label} (${s.sale_count} sold)`,
                value: s.median_price,
                formattedValue: fmtCurrency(s.median_price),
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
          subtitle="PropRadar's suburb-level rent, yield, days-on-market and vacancy. House/unit is the finest granularity available — PropRadar has no per-bed/bath rental-listings endpoint, only this suburb-wide snapshot. Trend charts fill in as more monthly snapshots accumulate."
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
              return (
                <div
                  key={r.suburb_name}
                  style={{
                    padding: '16px',
                    backgroundColor: colors.pageBg,
                    borderRadius: '8px',
                  }}
                >
                  <h4 style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 12px 0' }}>
                    {r.suburb_name}
                  </h4>
                  <StatGrid>
                    <Stat label="House Weekly Rent" value={latest.median_house_rent_weekly != null ? `$${fmtNum(latest.median_house_rent_weekly)}` : '—'} />
                    <Stat label="Unit Weekly Rent" value={latest.median_unit_rent_weekly != null ? `$${fmtNum(latest.median_unit_rent_weekly)}` : '—'} />
                    <Stat label="House Gross Yield" value={fmtPct(latest.gross_yield_house_pct)} />
                    <Stat label="Unit Gross Yield" value={fmtPct(latest.gross_yield_unit_pct)} />
                    <Stat label="House Days on Market" value={fmtDays(latest.days_on_market_house)} />
                    <Stat label="Unit Days on Market" value={fmtDays(latest.days_on_market_unit)} />
                    <Stat label="Vacancy Rate" value={fmtPct(latest.vacancy_rate_pct)} />
                  </StatGrid>

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

      {regional_comparison && (
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

      <Section
        title="Community & Socio-Economic Profile"
        subtitle="ABS SEIFA deciles (1 = most disadvantaged, 10 = most advantaged, relative to all of Australia)"
        dataVintage={`${census_year} SEIFA`}
      >
        {(() => {
          const items = [
            { label: 'Disadvantage (IRSD)', value: community.seifa_irsd_decile },
            { label: 'Advantage/Disadvantage (IRSAD)', value: community.seifa_irsad_decile },
            { label: 'Economic Resources (IER)', value: community.seifa_ier_decile },
            { label: 'Education & Occupation (IEO)', value: community.seifa_ieo_decile },
          ].filter((i): i is { label: string; value: number } => i.value != null)
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
        {schools.state_percentile && (
          <div style={{ marginBottom: '20px' }}>
            <Pill tone="green">{schools.state_percentile.top_pct_label} by avg. school ICSEA</Pill>
            <span style={{ fontSize: '12px', color: colors.textMuted, marginLeft: '10px' }}>
              Avg ICSEA {Math.round(schools.state_percentile.avg_icsea)} · ranked against{' '}
              {schools.state_percentile.sample_size} suburbs in {schools.state_percentile.state}
            </span>
          </div>
        )}

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
        <StatGrid>
          <Stat label="Zero-Car Households" value={fmtPct(transport.zero_car_dwellings_pct)} />
        </StatGrid>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '32px', marginTop: '20px' }}>
          {(() => {
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
