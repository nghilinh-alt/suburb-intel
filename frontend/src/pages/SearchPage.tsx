import { FormEvent, ReactNode, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, FunnelStep } from '../components/primitives'
import {
  askSearch,
  filterSuburbs,
  getFilterOptions,
  searchSuburbs,
  type AskSearchResponse,
  type FilteredSuburb,
  type GrowthYieldQuadrant,
  type MomentumPhase,
  type SuburbFilters,
  type SuburbSearchResult,
} from '../lib/api'
import { colors, fonts } from '../lib/theme'

const MOMENTUM_PHASE_OPTIONS: { value: MomentumPhase; label: string }[] = [
  { value: 'accelerating', label: 'Accelerating' },
  { value: 'steady', label: 'Steady' },
  { value: 'cooling', label: 'Cooling' },
]

const QUADRANT_OPTIONS: { value: GrowthYieldQuadrant; label: string }[] = [
  { value: 'hot', label: 'Hot (growth + yield)' },
  { value: 'growth_play', label: 'Growth play' },
  { value: 'cash_flow_play', label: 'Cash-flow play' },
  { value: 'avoid', label: 'Avoid' },
]

const EXAMPLE_PROMPTS = [
  'Brisbane suburbs within 10km of CBD',
  'top 5 highest income suburbs in Sydney',
  'Melbourne suburbs closest to CBD',
]

const PAGE_SIZE = 20

const SORT_OPTIONS: { value: string; label: string }[] = [
  { value: 'population', label: 'Population' },
  { value: 'median_income', label: 'Median Income' },
  { value: 'median_house_price', label: 'Median House Price' },
  { value: 'median_unit_price', label: 'Median Unit Price' },
  { value: 'pop_growth_5yr_pct', label: 'Population Growth (5yr)' },
  { value: 'median_rent_weekly', label: 'Median Weekly Rent' },
  { value: 'distance_to_cbd_km', label: 'Distance to CBD' },
  { value: 'investment_score', label: 'Investment Score' },
  { value: 'economic_score', label: 'Economic Score' },
  { value: 'demographic_score', label: 'Demographic Score' },
  { value: 'momentum_score', label: 'Momentum' },
]

// ---------------------------------------------------------------------------
// Draft filter form state — strings so number inputs can be blank; parsed
// into a SuburbFilters object only when Search is pressed.
// ---------------------------------------------------------------------------

interface DraftFilters {
  states: string[]
  maxDistanceToCbdKm: string
  minMedianHousePrice: string
  maxMedianHousePrice: string
  minMedianUnitPrice: string
  maxMedianUnitPrice: string
  minPopulation: string
  maxPopulation: string
  minPopGrowth5yrPct: string
  minMedianIncome: string
  maxMedianIncome: string
  minMedianRentWeekly: string
  maxMedianRentWeekly: string
  minOwnerOccupiedPct: string
  maxOwnerOccupiedPct: string
  maxSocialHousingPct: string
  maxUnemploymentPct: string
  minSeifaIrsdDecile: string
  minAvgSchoolIcsea: string
  maxDaysOnMarket: string
  minInvestmentScore: string
  minEconomicScore: string
  minDemographicScore: string
  minGrossYieldHousePct: string
  maxVacancyRatePct: string
  momentumPhase: MomentumPhase | ''
  growthYieldQuadrant: GrowthYieldQuadrant | ''
  minScarcityScore: string
}

const EMPTY_DRAFT: DraftFilters = {
  states: [],
  maxDistanceToCbdKm: '',
  minMedianHousePrice: '',
  maxMedianHousePrice: '',
  minMedianUnitPrice: '',
  maxMedianUnitPrice: '',
  minPopulation: '',
  maxPopulation: '',
  minPopGrowth5yrPct: '',
  minMedianIncome: '',
  maxMedianIncome: '',
  minMedianRentWeekly: '',
  maxMedianRentWeekly: '',
  minOwnerOccupiedPct: '',
  maxOwnerOccupiedPct: '',
  maxSocialHousingPct: '',
  maxUnemploymentPct: '',
  minSeifaIrsdDecile: '',
  minAvgSchoolIcsea: '',
  maxDaysOnMarket: '',
  minInvestmentScore: '',
  minEconomicScore: '',
  minDemographicScore: '',
  minGrossYieldHousePct: '',
  maxVacancyRatePct: '',
  momentumPhase: '',
  growthYieldQuadrant: '',
  minScarcityScore: '',
}

// Large-value filter fields are entered in millions ($M) or thousands (k) in
// the UI for readability — these multipliers convert the entered number back
// to raw units before sending it to the API.
const MILLIONS = 1_000_000
const THOUSANDS = 1_000

function draftToFilters(d: DraftFilters): SuburbFilters {
  const num = (s: string, scale = 1): number | undefined =>
    s.trim() === '' ? undefined : Number(s) * scale
  return {
    states: d.states.length > 0 ? d.states : undefined,
    max_distance_to_cbd_km: num(d.maxDistanceToCbdKm),
    min_median_house_price: num(d.minMedianHousePrice, MILLIONS),
    max_median_house_price: num(d.maxMedianHousePrice, MILLIONS),
    min_median_unit_price: num(d.minMedianUnitPrice, MILLIONS),
    max_median_unit_price: num(d.maxMedianUnitPrice, MILLIONS),
    min_population: num(d.minPopulation, THOUSANDS),
    max_population: num(d.maxPopulation, THOUSANDS),
    min_pop_growth_5yr_pct: num(d.minPopGrowth5yrPct),
    min_median_income: num(d.minMedianIncome, THOUSANDS),
    max_median_income: num(d.maxMedianIncome, THOUSANDS),
    min_median_rent_weekly: num(d.minMedianRentWeekly),
    max_median_rent_weekly: num(d.maxMedianRentWeekly),
    min_owner_occupied_pct: num(d.minOwnerOccupiedPct),
    max_owner_occupied_pct: num(d.maxOwnerOccupiedPct),
    max_social_housing_pct: num(d.maxSocialHousingPct),
    max_unemployment_pct: num(d.maxUnemploymentPct),
    min_seifa_irsd_decile: num(d.minSeifaIrsdDecile),
    min_avg_school_icsea: num(d.minAvgSchoolIcsea),
    max_days_on_market: num(d.maxDaysOnMarket),
    min_investment_score: num(d.minInvestmentScore),
    min_economic_score: num(d.minEconomicScore),
    min_demographic_score: num(d.minDemographicScore),
    min_gross_yield_house_pct: num(d.minGrossYieldHousePct),
    max_vacancy_rate_pct: num(d.maxVacancyRatePct),
    momentum_phase: d.momentumPhase || undefined,
    growth_yield_quadrant: d.growthYieldQuadrant || undefined,
    min_scarcity_score: num(d.minScarcityScore),
  }
}

function countActiveFilters(d: DraftFilters): number {
  let n = d.states.length > 0 ? 1 : 0
  for (const [key, value] of Object.entries(d)) {
    if (key === 'states') continue
    if (String(value).trim() !== '') n += 1
  }
  return n
}

// ---------------------------------------------------------------------------
// Results state
// ---------------------------------------------------------------------------

type ResultsState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; results: FilteredSuburb[]; totalCount: number }

type AskSearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: AskSearchResponse }

type NameSearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; results: SuburbSearchResult[] }

export default function SearchPage() {
  const [availableStates, setAvailableStates] = useState<string[]>([])
  const [draft, setDraft] = useState<DraftFilters>(EMPTY_DRAFT)
  const [appliedFilters, setAppliedFilters] = useState<SuburbFilters>({})
  const [sortBy, setSortBy] = useState('population')
  const [offset, setOffset] = useState(0)
  const [resultsState, setResultsState] = useState<ResultsState>({ status: 'idle' })

  const [prompt, setPrompt] = useState('')
  const [askState, setAskState] = useState<AskSearchState>({ status: 'idle' })

  const [nameQuery, setNameQuery] = useState('')
  const [nameState, setNameState] = useState<NameSearchState>({ status: 'idle' })

  useEffect(() => {
    getFilterOptions()
      .then((opts) => setAvailableStates(opts.states))
      .catch(() => setAvailableStates([]))
  }, [])

  async function runSearch(filters: SuburbFilters, sort: string, off: number) {
    setResultsState({ status: 'loading' })
    try {
      const data = await filterSuburbs(filters, { sortBy: sort, limit: PAGE_SIZE, offset: off })
      setResultsState({ status: 'ready', results: data.results, totalCount: data.total_count })
    } catch (err) {
      setResultsState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Search failed.',
      })
    }
  }

  useEffect(() => {
    runSearch({}, sortBy, 0)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function handleSearch() {
    const filters = draftToFilters(draft)
    setAppliedFilters(filters)
    setOffset(0)
    runSearch(filters, sortBy, 0)
  }

  function handleReset() {
    setDraft(EMPTY_DRAFT)
    setAppliedFilters({})
    setOffset(0)
    runSearch({}, sortBy, 0)
  }

  function handleSortChange(newSort: string) {
    setSortBy(newSort)
    setOffset(0)
    runSearch(appliedFilters, newSort, 0)
  }

  function handlePage(newOffset: number) {
    setOffset(newOffset)
    runSearch(appliedFilters, sortBy, newOffset)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  async function runNameSearch(q: string) {
    if (!q.trim()) {
      setNameState({ status: 'idle' })
      return
    }
    setNameState({ status: 'loading' })
    try {
      const data = await searchSuburbs(q)
      const results = Array.isArray(data) ? data : [data]
      setNameState({ status: 'ready', results })
    } catch (err) {
      setNameState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Search failed.',
      })
    }
  }

  function handleNameSubmit(e: FormEvent) {
    e.preventDefault()
    runNameSearch(nameQuery)
  }

  function clearNameSearch() {
    setNameQuery('')
    setNameState({ status: 'idle' })
  }

  async function runAskSearch(p: string) {
    if (!p.trim()) return
    setAskState({ status: 'loading' })
    try {
      const data = await askSearch(p)
      setAskState({ status: 'ready', data })
    } catch (err) {
      setAskState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Search failed.',
      })
    }
  }

  function handleAskSubmit(e: FormEvent) {
    e.preventDefault()
    runAskSearch(prompt)
  }

  const totalCount = resultsState.status === 'ready' ? resultsState.totalCount : 0
  const rangeStart = totalCount === 0 ? 0 : offset + 1
  const rangeEnd = Math.min(offset + PAGE_SIZE, totalCount)
  const activeFilterCount = countActiveFilters(draft)

  return (
    <div
      style={{
        backgroundColor: colors.pageBg,
        backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(15,23,42,0.06) 1px, transparent 0)',
        backgroundSize: '18px 18px',
        margin: '-20px',
        padding: '20px',
        minHeight: 'calc(100vh - 40px)',
      }}
    >
      <div style={{ marginBottom: '24px' }}>
        <FunnelStep step={1} total={3} label="Macro filter" />
        <h1 style={{ fontSize: '32px', margin: 0, color: colors.textPrimary }}>Search Suburbs</h1>
        <p style={{ color: colors.textMuted, fontSize: '14px', marginTop: '6px' }}>
          Narrow the pool by state, price, momentum, and supply scarcity — then head to{' '}
          <Link to="/rankings" style={{ color: colors.pink, fontWeight: 600 }}>
            Rankings
          </Link>{' '}
          for a momentum/pressure-sorted shortlist, or click a suburb here for the full deep-dive report.
        </p>
      </div>

      <NameSearchBar
        query={nameQuery}
        setQuery={setNameQuery}
        state={nameState}
        onSubmit={handleNameSubmit}
        onClear={clearNameSearch}
      />

      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: '24px', alignItems: 'start' }}>
        <FilterSidebar
          draft={draft}
          setDraft={setDraft}
          availableStates={availableStates}
          activeFilterCount={activeFilterCount}
          onSearch={handleSearch}
          onReset={handleReset}
        />

        <div>
          <ResultsHeader
            rangeStart={rangeStart}
            rangeEnd={rangeEnd}
            totalCount={totalCount}
            sortBy={sortBy}
            onSortChange={handleSortChange}
          />

          {resultsState.status === 'loading' && (
            <p style={{ color: colors.textMuted, marginTop: '16px' }}>Searching...</p>
          )}

          {resultsState.status === 'error' && (
            <Card style={{ marginTop: '16px' }}>
              <p style={{ color: '#B91C1C', margin: 0 }}>{resultsState.message}</p>
            </Card>
          )}

          {resultsState.status === 'ready' && (
            <>
              {resultsState.results.length === 0 ? (
                <Card style={{ marginTop: '16px' }}>
                  <p style={{ color: colors.textMuted, margin: 0 }}>
                    No suburbs match these filters. Try loosening a few.
                  </p>
                </Card>
              ) : (
                <div
                  style={{
                    display: 'grid',
                    gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
                    gap: '16px',
                    marginTop: '16px',
                  }}
                >
                  {resultsState.results.map((s) => (
                    <SuburbTile key={s.sa2_code} suburb={s} />
                  ))}
                </div>
              )}

              <Pagination
                offset={offset}
                pageSize={PAGE_SIZE}
                totalCount={totalCount}
                onPage={handlePage}
              />
            </>
          )}

          <div style={{ borderTop: `1px solid ${colors.border}`, margin: '40px 0 24px' }} />

          <Card>
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: '0 0 4px 0' }}>
              Or Ask in Plain English
            </h3>
            <p style={{ fontSize: '13px', color: colors.textMuted, marginTop: 0, marginBottom: '16px' }}>
              e.g. "Brisbane suburbs within 10km of CBD"
            </p>

            <form onSubmit={handleAskSubmit} style={{ marginBottom: '12px' }}>
              <textarea
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder='e.g. "Brisbane suburbs within 10km of CBD"'
                rows={2}
                style={{ ...textInputStyle, resize: 'vertical', fontFamily: 'inherit', width: '100%' }}
              />
              <button type="submit" style={{ ...primaryButtonStyle, marginTop: '10px' }}>
                Search
              </button>
            </form>

            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: askState.status === 'idle' ? 0 : '16px' }}>
              {EXAMPLE_PROMPTS.map((example) => (
                <button
                  key={example}
                  onClick={() => {
                    setPrompt(example)
                    runAskSearch(example)
                  }}
                  style={pillButtonStyle}
                >
                  {example}
                </button>
              ))}
            </div>

            {askState.status === 'loading' && <p style={{ color: colors.textMuted }}>Searching...</p>}
            {askState.status === 'error' && <p style={{ color: '#B91C1C' }}>{askState.message}</p>}

            {askState.status === 'ready' && (
              <>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '12px' }}>
                  {Object.entries(askState.data.parsed_filter)
                    .filter(([, v]) => v !== null && v !== undefined)
                    .map(([k, v]) => (
                      <span key={k} style={chipStyle}>
                        {k}: {String(v)}
                      </span>
                    ))}
                </div>

                {askState.data.message && (
                  <p style={{ color: colors.textMuted, fontSize: '13px' }}>{askState.data.message}</p>
                )}

                <div style={{ display: 'grid', gap: '8px' }}>
                  {askState.data.results.map((r) => (
                    <Link key={r.sa2_code} to={`/suburb/${r.sa2_code}`} style={{ textDecoration: 'none' }}>
                      <div style={askResultCardStyle}>
                        <div>
                          <strong style={{ color: colors.textPrimary }}>{r.sa2_name}</strong>{' '}
                          <span style={{ color: colors.textMuted }}>{r.state}</span>
                        </div>
                        <div style={{ color: colors.textMuted, fontSize: '13px' }}>
                          {[
                            r.distance_to_cbd_km != null ? `${r.distance_to_cbd_km.toFixed(1)} km to CBD` : null,
                            r.population != null ? `Pop ${r.population.toLocaleString()}` : null,
                            r.median_income != null ? `Income $${r.median_income.toLocaleString()}` : null,
                          ]
                            .filter(Boolean)
                            .join(' · ')}
                        </div>
                      </div>
                    </Link>
                  ))}
                </div>
              </>
            )}
          </Card>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Name / SA2-code quick search
// ---------------------------------------------------------------------------

function NameSearchBar({
  query,
  setQuery,
  state,
  onSubmit,
  onClear,
}: {
  query: string
  setQuery: (v: string) => void
  state: NameSearchState
  onSubmit: (e: FormEvent) => void
  onClear: () => void
}) {
  return (
    <Card style={{ padding: '16px 20px', marginBottom: '24px' }}>
      <form onSubmit={onSubmit} style={{ display: 'flex', gap: '10px' }}>
        <div style={{ position: 'relative', flex: 1 }}>
          <SearchIcon />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by suburb name or enter SA2 code..."
            style={{ ...textInputStyle, width: '100%', paddingLeft: '38px' }}
          />
          {query && (
            <button
              type="button"
              onClick={onClear}
              aria-label="Clear search"
              style={{
                position: 'absolute',
                right: '10px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: colors.textMuted,
                display: 'flex',
                padding: 0,
              }}
            >
              <XIcon />
            </button>
          )}
        </div>
        <button type="submit" style={primaryButtonStyle}>
          Search
        </button>
      </form>

      {state.status === 'loading' && (
        <p style={{ color: colors.textMuted, fontSize: '13px', margin: '12px 0 0 0' }}>Searching...</p>
      )}
      {state.status === 'error' && (
        <p style={{ color: '#B91C1C', fontSize: '13px', margin: '12px 0 0 0' }}>{state.message}</p>
      )}
      {state.status === 'ready' && (
        <div style={{ display: 'grid', gap: '8px', marginTop: '12px' }}>
          {state.results.map((r) => (
            <Link key={r.sa2_code} to={`/suburb/${r.sa2_code}`} style={{ textDecoration: 'none' }}>
              <div style={askResultCardStyle}>
                <div>
                  <strong style={{ color: colors.textPrimary }}>{r.sa2_name}</strong>{' '}
                  <span style={{ color: colors.textMuted }}>{r.state}</span>
                </div>
                <div style={{ color: colors.textMuted, fontSize: '13px' }}>
                  {[
                    r.distance_to_cbd_km != null ? `${r.distance_to_cbd_km.toFixed(1)} km to CBD` : null,
                    r.population != null ? `Pop ${r.population.toLocaleString()}` : null,
                    r.median_income != null ? `Income $${r.median_income.toLocaleString()}` : null,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}
    </Card>
  )
}

function SearchIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      style={{ position: 'absolute', left: '12px', top: '50%', transform: 'translateY(-50%)' }}
    >
      <circle cx="7" cy="7" r="5.25" stroke={colors.textMuted} strokeWidth="1.4" />
      <path d="M11 11L14.5 14.5" stroke={colors.textMuted} strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Filter sidebar
// ---------------------------------------------------------------------------

function FilterSidebar({
  draft,
  setDraft,
  availableStates,
  activeFilterCount,
  onSearch,
  onReset,
}: {
  draft: DraftFilters
  setDraft: (d: DraftFilters) => void
  availableStates: string[]
  activeFilterCount: number
  onSearch: () => void
  onReset: () => void
}) {
  function set<K extends keyof DraftFilters>(key: K, value: DraftFilters[K]) {
    setDraft({ ...draft, [key]: value })
  }

  function toggleState(state: string) {
    const next = draft.states.includes(state)
      ? draft.states.filter((s) => s !== state)
      : [...draft.states, state]
    set('states', next)
  }

  return (
    <Card style={{ position: 'sticky', top: '20px', padding: '20px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '4px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>Filters</h3>
        {activeFilterCount > 0 && (
          <button onClick={onReset} style={resetLinkStyle}>
            <XIcon /> Reset All Filters
          </button>
        )}
      </div>

      <FilterGroup label="State">
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
          {availableStates.map((s) => (
            <label
              key={s}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '5px',
                padding: '5px 10px',
                borderRadius: '999px',
                border: `1px solid ${draft.states.includes(s) ? colors.pink : colors.border}`,
                backgroundColor: draft.states.includes(s) ? colors.pinkLight : colors.cardBg,
                color: draft.states.includes(s) ? colors.pink : colors.textSecondary,
                fontSize: '12px',
                fontWeight: 600,
                cursor: 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={draft.states.includes(s)}
                onChange={() => toggleState(s)}
                style={{ display: 'none' }}
              />
              {s}
            </label>
          ))}
        </div>
      </FilterGroup>

      <SelectFilter
        label="Momentum"
        hint="Derived in-house from sale velocity, price growth, supply scarcity, and heat score."
        value={draft.momentumPhase}
        onChange={(v) => set('momentumPhase', v as MomentumPhase | '')}
        options={MOMENTUM_PHASE_OPTIONS}
      />
      <SelectFilter
        label="Growth / Yield Quadrant"
        hint="Where this suburb sits vs the market median growth and yield right now."
        value={draft.growthYieldQuadrant}
        onChange={(v) => set('growthYieldQuadrant', v as GrowthYieldQuadrant | '')}
        options={QUADRANT_OPTIONS}
      />
      <MinFilter
        label="Supply Scarcity"
        hint="0-100 score combining stock-on-market %, inventory months, and building approvals — higher means less for-sale supply relative to demand."
        value={draft.minScarcityScore}
        onChange={(v) => set('minScarcityScore', v)}
      />

      <RangeFilter
        label="Median House Price"
        hint="PropRadar data — broadest coverage in capital cities, sparse elsewhere. Enter in millions, e.g. 1.2 = $1.2M"
        minValue={draft.minMedianHousePrice}
        maxValue={draft.maxMedianHousePrice}
        onMinChange={(v) => set('minMedianHousePrice', v)}
        onMaxChange={(v) => set('maxMedianHousePrice', v)}
        prefix="$"
        suffix="M"
      />
      <RangeFilter
        label="Median Unit Price"
        hint="PropRadar data — broadest coverage in capital cities, sparse elsewhere. Enter in millions, e.g. 1.2 = $1.2M"
        minValue={draft.minMedianUnitPrice}
        maxValue={draft.maxMedianUnitPrice}
        onMinChange={(v) => set('minMedianUnitPrice', v)}
        onMaxChange={(v) => set('maxMedianUnitPrice', v)}
        prefix="$"
        suffix="M"
      />
      <MinFilter
        label="Minimum Gross Yield (House)"
        hint="PropRadar data — broadest coverage in capital cities, sparse elsewhere"
        value={draft.minGrossYieldHousePct}
        onChange={(v) => set('minGrossYieldHousePct', v)}
        suffix="%"
      />
      <RangeFilter
        label="Population"
        hint="Enter in thousands, e.g. 30 = 30,000"
        minValue={draft.minPopulation}
        maxValue={draft.maxPopulation}
        onMinChange={(v) => set('minPopulation', v)}
        onMaxChange={(v) => set('maxPopulation', v)}
        suffix="k"
      />
      <MinFilter
        label="Population Growth (5yr)"
        value={draft.minPopGrowth5yrPct}
        onChange={(v) => set('minPopGrowth5yrPct', v)}
        suffix="%"
      />
      <RangeFilter
        label="Median Income"
        hint="Enter in thousands, e.g. 80 = $80,000"
        minValue={draft.minMedianIncome}
        maxValue={draft.maxMedianIncome}
        onMinChange={(v) => set('minMedianIncome', v)}
        onMaxChange={(v) => set('maxMedianIncome', v)}
        prefix="$"
        suffix="k"
      />
      <MinFilter
        label="Investment Score"
        value={draft.minInvestmentScore}
        onChange={(v) => set('minInvestmentScore', v)}
      />
      <MinFilter
        label="Economic Score"
        value={draft.minEconomicScore}
        onChange={(v) => set('minEconomicScore', v)}
      />
      <MaxFilter
        label="Days on Market"
        hint="PropRadar data — broadest coverage in capital cities, sparse elsewhere"
        value={draft.maxDaysOnMarket}
        onChange={(v) => set('maxDaysOnMarket', v)}
        suffix="days"
      />
      <MaxFilter
        label="Vacancy Rate"
        hint="PropRadar data — broadest coverage in capital cities, sparse elsewhere"
        value={draft.maxVacancyRatePct}
        onChange={(v) => set('maxVacancyRatePct', v)}
        suffix="%"
      />
      <MaxFilter
        label="Public Housing"
        value={draft.maxSocialHousingPct}
        onChange={(v) => set('maxSocialHousingPct', v)}
        suffix="%"
      />
      <RangeFilter
        label="Owner Occupied"
        minValue={draft.minOwnerOccupiedPct}
        maxValue={draft.maxOwnerOccupiedPct}
        onMinChange={(v) => set('minOwnerOccupiedPct', v)}
        onMaxChange={(v) => set('maxOwnerOccupiedPct', v)}
        suffix="%"
      />
      <RangeFilter
        label="Weekly Rent"
        minValue={draft.minMedianRentWeekly}
        maxValue={draft.maxMedianRentWeekly}
        onMinChange={(v) => set('minMedianRentWeekly', v)}
        onMaxChange={(v) => set('maxMedianRentWeekly', v)}
        prefix="$"
      />

      <details style={{ marginTop: '4px' }}>
        <summary style={{ fontSize: '13px', fontWeight: 600, color: colors.blue, cursor: 'pointer', padding: '8px 0' }}>
          Advanced Filters
        </summary>
        <div style={{ marginTop: '8px' }}>
          <MaxFilter
            label="Distance to CBD"
            value={draft.maxDistanceToCbdKm}
            onChange={(v) => set('maxDistanceToCbdKm', v)}
            suffix="km"
          />
          <MaxFilter
            label="Unemployment Rate"
            value={draft.maxUnemploymentPct}
            onChange={(v) => set('maxUnemploymentPct', v)}
            suffix="%"
          />
          <MinFilter
            label="SEIFA Disadvantage Decile"
            hint="1 = most disadvantaged, 10 = most advantaged"
            value={draft.minSeifaIrsdDecile}
            onChange={(v) => set('minSeifaIrsdDecile', v)}
          />
          <MinFilter
            label="Avg School ICSEA"
            value={draft.minAvgSchoolIcsea}
            onChange={(v) => set('minAvgSchoolIcsea', v)}
          />
          <MinFilter
            label="Demographic Score"
            value={draft.minDemographicScore}
            onChange={(v) => set('minDemographicScore', v)}
          />
        </div>
      </details>

      <button onClick={onSearch} style={{ ...primaryButtonStyle, width: '100%', marginTop: '16px' }}>
        Search
      </button>
    </Card>
  )
}

function FilterGroup({ label, children }: { label: ReactNode; children: ReactNode }) {
  return (
    <div style={{ marginBottom: '16px', paddingBottom: '16px', borderBottom: `1px solid ${colors.border}` }}>
      <div style={{ fontSize: '12px', fontWeight: 600, color: colors.textSecondary, marginBottom: '8px' }}>
        {label}
      </div>
      {children}
    </div>
  )
}

function NoDataBadge() {
  return (
    <span
      style={{
        display: 'inline-block',
        fontSize: '10px',
        fontWeight: 700,
        color: colors.amber,
        backgroundColor: colors.amberLight,
        padding: '2px 7px',
        borderRadius: '999px',
        marginLeft: '6px',
      }}
    >
      NO DATA YET
    </span>
  )
}

function RangeFilter({
  label,
  minValue,
  maxValue,
  onMinChange,
  onMaxChange,
  prefix,
  suffix,
  hint,
  disabled,
}: {
  label: string
  minValue: string
  maxValue: string
  onMinChange: (v: string) => void
  onMaxChange: (v: string) => void
  prefix?: string
  suffix?: string
  hint?: string
  disabled?: boolean
}) {
  return (
    <FilterGroup label={<>{label}{disabled && <NoDataBadge />}</>}>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <NumberBox value={minValue} onChange={onMinChange} placeholder="Min" prefix={prefix} suffix={suffix} disabled={disabled} />
        <span style={{ color: colors.textMuted, fontSize: '12px' }}>–</span>
        <NumberBox value={maxValue} onChange={onMaxChange} placeholder="Max" prefix={prefix} suffix={suffix} disabled={disabled} />
      </div>
      {hint && <div style={{ fontSize: '11px', color: colors.textMuted, marginTop: '6px' }}>{hint}</div>}
    </FilterGroup>
  )
}

function MinFilter({
  label,
  value,
  onChange,
  suffix,
  hint,
  disabled,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  suffix?: string
  hint?: string
  disabled?: boolean
}) {
  return (
    <FilterGroup label={<>{label}{disabled && <NoDataBadge />}</>}>
      <NumberBox value={value} onChange={onChange} placeholder="Minimum" suffix={suffix} disabled={disabled} />
      {hint && <div style={{ fontSize: '11px', color: colors.textMuted, marginTop: '6px' }}>{hint}</div>}
    </FilterGroup>
  )
}

function MaxFilter({
  label,
  value,
  onChange,
  suffix,
  hint,
  disabled,
}: {
  label: string
  value: string
  onChange: (v: string) => void
  suffix?: string
  hint?: string
  disabled?: boolean
}) {
  return (
    <FilterGroup label={<>{label}{disabled && <NoDataBadge />}</>}>
      <NumberBox value={value} onChange={onChange} placeholder="Maximum" suffix={suffix} disabled={disabled} />
      {hint && <div style={{ fontSize: '11px', color: colors.textMuted, marginTop: '6px' }}>{hint}</div>}
    </FilterGroup>
  )
}

function SelectFilter<T extends string>({
  label,
  value,
  onChange,
  options,
  hint,
}: {
  label: string
  value: T | ''
  onChange: (v: T | '') => void
  options: { value: T; label: string }[]
  hint?: string
}) {
  return (
    <FilterGroup label={label}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as T | '')}
        style={{ ...selectStyle, width: '100%' }}
      >
        <option value="">All</option>
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
      {hint && <div style={{ fontSize: '11px', color: colors.textMuted, marginTop: '6px' }}>{hint}</div>}
    </FilterGroup>
  )
}

function NumberBox({
  value,
  onChange,
  placeholder,
  prefix,
  suffix,
  disabled,
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  prefix?: string
  suffix?: string
  disabled?: boolean
}) {
  return (
    <div style={{ position: 'relative', flex: 1 }}>
      {prefix && (
        <span style={{ position: 'absolute', left: '8px', top: '50%', transform: 'translateY(-50%)', fontSize: '12px', color: colors.textMuted }}>
          {prefix}
        </span>
      )}
      <input
        type="number"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        disabled={disabled}
        style={{
          ...numberInputStyle,
          ...(disabled ? { backgroundColor: colors.border, cursor: 'not-allowed', color: colors.textMuted } : {}),
          paddingLeft: prefix ? '18px' : '10px',
          paddingRight: suffix ? '28px' : '10px',
        }}
      />
      {suffix && (
        <span style={{ position: 'absolute', right: '8px', top: '50%', transform: 'translateY(-50%)', fontSize: '11px', color: colors.textMuted }}>
          {suffix}
        </span>
      )}
    </div>
  )
}

function XIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 16 16" fill="none" style={{ display: 'inline', verticalAlign: '-1px' }}>
      <path d="M12 4L4 12M4 4l8 8" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Results
// ---------------------------------------------------------------------------

function ResultsHeader({
  rangeStart,
  rangeEnd,
  totalCount,
  sortBy,
  onSortChange,
}: {
  rangeStart: number
  rangeEnd: number
  totalCount: number
  sortBy: string
  onSortChange: (v: string) => void
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '8px' }}>
      <div>
        <h2 style={{ fontSize: '18px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>Suburbs</h2>
        <p style={{ fontSize: '13px', color: colors.textMuted, margin: '2px 0 0 0' }}>
          {totalCount === 0 ? '0 suburbs' : `${rangeStart} – ${rangeEnd} of ${totalCount.toLocaleString()} suburbs`}
        </p>
      </div>
      <label style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px', color: colors.textSecondary }}>
        Sort by
        <select value={sortBy} onChange={(e) => onSortChange(e.target.value)} style={selectStyle}>
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  )
}

function SuburbTile({ suburb }: { suburb: FilteredSuburb }) {
  return (
    <Link to={`/suburb/${suburb.sa2_code}`} style={{ textDecoration: 'none' }}>
      <Card style={{ padding: '18px', height: '100%', transition: 'box-shadow 0.15s' }} hoverable>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
          <div>
            <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
              {suburb.sa2_name}
            </h3>
            <span style={{ fontSize: '12px', color: colors.textMuted }}>{suburb.state}</span>
          </div>
          {suburb.investment_score != null && (
            <div
              style={{
                backgroundColor: colors.pinkLight,
                color: colors.pink,
                borderRadius: '999px',
                padding: '4px 10px',
                fontSize: '12px',
                fontWeight: 700,
                fontFamily: fonts.mono,
                whiteSpace: 'nowrap',
              }}
            >
              {suburb.investment_score.toFixed(0)} score
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '10px' }}>
          <TileStat label="Median House" value={fmtCurrency(suburb.median_house_price)} />
          <TileStat label="Population" value={fmtNum(suburb.population)} />
          <TileStat label="Weekly Rent" value={fmtCurrency(suburb.median_rent_weekly)} />
          <TileStat label="Gross Yield" value={fmtPct(suburb.gross_yield_house_pct)} />
          <TileStat label="Days on Mkt" value={fmtDays(suburb.days_on_market)} />
          <TileStat label="To CBD" value={fmtKm(suburb.distance_to_cbd_km)} />
        </div>

        {(suburb.momentum_phase || suburb.growth_yield_quadrant) && (
          <div style={{ display: 'flex', gap: '6px', marginTop: '10px', flexWrap: 'wrap' }}>
            {suburb.momentum_phase && <MomentumTag phase={suburb.momentum_phase} />}
            {suburb.growth_yield_quadrant && <QuadrantTag quadrant={suburb.growth_yield_quadrant} />}
          </div>
        )}

        {suburb.pop_growth_5yr_pct != null && (
          <div style={{ marginTop: '10px', fontSize: '12px', color: colors.green, fontWeight: 600 }}>
            +{suburb.pop_growth_5yr_pct.toFixed(1)}% population growth (5yr)
          </div>
        )}
      </Card>
    </Link>
  )
}

function TileStat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div style={{ fontSize: '11px', color: colors.textMuted }}>{label}</div>
      <div style={{ fontSize: '13px', fontWeight: 600, color: colors.textPrimary, fontFamily: fonts.mono }}>{value}</div>
    </div>
  )
}

const MOMENTUM_TAG_CONFIG: Record<string, { arrow: string; label: string; bg: string; fg: string }> = {
  accelerating: { arrow: '▲', label: 'Accelerating', bg: colors.greenLight, fg: colors.green },
  steady: { arrow: '→', label: 'Steady', bg: colors.blueLight, fg: colors.blue },
  cooling: { arrow: '▼', label: 'Cooling', bg: colors.amberLight, fg: colors.amber },
}

function MomentumTag({ phase }: { phase: string }) {
  const config = MOMENTUM_TAG_CONFIG[phase]
  if (!config) return null
  return (
    <span style={{ ...tagStyle, backgroundColor: config.bg, color: config.fg }}>
      {config.arrow} {config.label}
    </span>
  )
}

const QUADRANT_TAG_LABELS: Record<string, string> = {
  hot: 'Hot',
  growth_play: 'Growth play',
  cash_flow_play: 'Cash-flow play',
  avoid: 'Avoid',
}

function QuadrantTag({ quadrant }: { quadrant: string }) {
  const label = QUADRANT_TAG_LABELS[quadrant]
  if (!label) return null
  return <span style={{ ...tagStyle, backgroundColor: colors.pageBg, color: colors.textSecondary }}>{label}</span>
}

function Pagination({
  offset,
  pageSize,
  totalCount,
  onPage,
}: {
  offset: number
  pageSize: number
  totalCount: number
  onPage: (offset: number) => void
}) {
  if (totalCount <= pageSize) return null
  const hasPrev = offset > 0
  const hasNext = offset + pageSize < totalCount
  return (
    <div style={{ display: 'flex', justifyContent: 'center', gap: '10px', marginTop: '24px' }}>
      <button
        onClick={() => onPage(Math.max(0, offset - pageSize))}
        disabled={!hasPrev}
        style={{ ...secondaryButtonStyle, opacity: hasPrev ? 1 : 0.4, cursor: hasPrev ? 'pointer' : 'default' }}
      >
        ← Previous
      </button>
      <button
        onClick={() => onPage(offset + pageSize)}
        disabled={!hasNext}
        style={{ ...secondaryButtonStyle, opacity: hasNext ? 1 : 0.4, cursor: hasNext ? 'pointer' : 'default' }}
      >
        Next →
      </button>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Formatting
// ---------------------------------------------------------------------------

function fmtCurrency(v: number | null): string {
  return v == null ? '—' : `$${Math.round(v).toLocaleString()}`
}
function fmtNum(v: number | null): string {
  return v == null ? '—' : Math.round(v).toLocaleString()
}
function fmtKm(v: number | null): string {
  return v == null ? '—' : `${v.toFixed(1)} km`
}
function fmtPct(v: number | null): string {
  return v == null ? '—' : `${v.toFixed(1)}%`
}
function fmtDays(v: number | null): string {
  return v == null ? '—' : `${Math.round(v)} days`
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const textInputStyle: React.CSSProperties = {
  padding: '12px 14px',
  fontSize: '14px',
  backgroundColor: colors.cardBg,
  color: colors.textPrimary,
  border: `1px solid ${colors.border}`,
  borderRadius: '8px',
  outline: 'none',
  boxSizing: 'border-box',
}

const numberInputStyle: React.CSSProperties = {
  width: '100%',
  padding: '8px 10px',
  fontSize: '13px',
  backgroundColor: colors.pageBg,
  color: colors.textPrimary,
  border: `1px solid ${colors.border}`,
  borderRadius: '6px',
  outline: 'none',
  boxSizing: 'border-box',
}

const selectStyle: React.CSSProperties = {
  padding: '6px 10px',
  fontSize: '13px',
  backgroundColor: colors.cardBg,
  color: colors.textPrimary,
  border: `1px solid ${colors.border}`,
  borderRadius: '6px',
  outline: 'none',
}

const primaryButtonStyle: React.CSSProperties = {
  padding: '12px 20px',
  fontSize: '14px',
  fontWeight: 600,
  backgroundColor: colors.pink,
  color: '#FFFFFF',
  border: 'none',
  borderRadius: '8px',
  cursor: 'pointer',
}

const secondaryButtonStyle: React.CSSProperties = {
  padding: '10px 20px',
  fontSize: '13px',
  fontWeight: 600,
  backgroundColor: colors.cardBg,
  color: colors.textPrimary,
  border: `1px solid ${colors.border}`,
  borderRadius: '8px',
}

const pillButtonStyle: React.CSSProperties = {
  padding: '8px 14px',
  fontSize: '12px',
  backgroundColor: colors.pageBg,
  color: colors.textSecondary,
  border: `1px solid ${colors.border}`,
  borderRadius: '999px',
  cursor: 'pointer',
}

const resetLinkStyle: React.CSSProperties = {
  display: 'flex',
  alignItems: 'center',
  gap: '4px',
  fontSize: '12px',
  fontWeight: 600,
  color: colors.pink,
  background: 'none',
  border: 'none',
  cursor: 'pointer',
  padding: 0,
}

const chipStyle: React.CSSProperties = {
  backgroundColor: colors.pageBg,
  color: colors.textSecondary,
  padding: '6px 12px',
  borderRadius: '999px',
  fontSize: '12px',
  border: `1px solid ${colors.border}`,
}

const tagStyle: React.CSSProperties = {
  display: 'inline-block',
  fontSize: '11px',
  fontWeight: 600,
  padding: '3px 9px',
  borderRadius: '999px',
}

const askResultCardStyle: React.CSSProperties = {
  backgroundColor: colors.pageBg,
  border: `1px solid ${colors.border}`,
  borderRadius: '8px',
  padding: '12px 16px',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
}
