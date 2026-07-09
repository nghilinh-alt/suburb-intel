import { FormEvent, ReactNode, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  askSearch,
  filterSuburbs,
  getFilterOptions,
  type AskSearchResponse,
  type FilteredSuburb,
  type SuburbFilters,
} from '../lib/api'
import { colors } from '../lib/theme'

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
}

function draftToFilters(d: DraftFilters): SuburbFilters {
  const num = (s: string): number | undefined => (s.trim() === '' ? undefined : Number(s))
  return {
    states: d.states.length > 0 ? d.states : undefined,
    max_distance_to_cbd_km: num(d.maxDistanceToCbdKm),
    min_median_house_price: num(d.minMedianHousePrice),
    max_median_house_price: num(d.maxMedianHousePrice),
    min_median_unit_price: num(d.minMedianUnitPrice),
    max_median_unit_price: num(d.maxMedianUnitPrice),
    min_population: num(d.minPopulation),
    max_population: num(d.maxPopulation),
    min_pop_growth_5yr_pct: num(d.minPopGrowth5yrPct),
    min_median_income: num(d.minMedianIncome),
    max_median_income: num(d.maxMedianIncome),
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

export default function SearchPage() {
  const [availableStates, setAvailableStates] = useState<string[]>([])
  const [draft, setDraft] = useState<DraftFilters>(EMPTY_DRAFT)
  const [appliedFilters, setAppliedFilters] = useState<SuburbFilters>({})
  const [sortBy, setSortBy] = useState('population')
  const [offset, setOffset] = useState(0)
  const [resultsState, setResultsState] = useState<ResultsState>({ status: 'idle' })

  const [prompt, setPrompt] = useState('')
  const [askState, setAskState] = useState<AskSearchState>({ status: 'idle' })

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
        <h1 style={{ fontSize: '32px', margin: 0, color: colors.textPrimary }}>Search Suburbs</h1>
        <p style={{ color: colors.textMuted, fontSize: '14px', marginTop: '6px' }}>
          Filter by any metric we track, then drill into a suburb's full investment report.
        </p>
      </div>

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

      <RangeFilter
        label="Median House Price"
        hint="Domain API data — not currently populated for any suburb; this filter won't narrow results yet"
        minValue={draft.minMedianHousePrice}
        maxValue={draft.maxMedianHousePrice}
        onMinChange={(v) => set('minMedianHousePrice', v)}
        onMaxChange={(v) => set('maxMedianHousePrice', v)}
        prefix="$"
      />
      <RangeFilter
        label="Median Unit Price"
        hint="Domain API data — not currently populated for any suburb; this filter won't narrow results yet"
        minValue={draft.minMedianUnitPrice}
        maxValue={draft.maxMedianUnitPrice}
        onMinChange={(v) => set('minMedianUnitPrice', v)}
        onMaxChange={(v) => set('maxMedianUnitPrice', v)}
        prefix="$"
      />
      <MinFilter
        label="Minimum Gross Yield (House)"
        hint="PropRadar data — currently only available for a handful of pilot suburbs"
        value={draft.minGrossYieldHousePct}
        onChange={(v) => set('minGrossYieldHousePct', v)}
        suffix="%"
      />
      <RangeFilter
        label="Population"
        minValue={draft.minPopulation}
        maxValue={draft.maxPopulation}
        onMinChange={(v) => set('minPopulation', v)}
        onMaxChange={(v) => set('maxPopulation', v)}
      />
      <MinFilter
        label="Population Growth (5yr)"
        value={draft.minPopGrowth5yrPct}
        onChange={(v) => set('minPopGrowth5yrPct', v)}
        suffix="%"
      />
      <RangeFilter
        label="Median Income"
        minValue={draft.minMedianIncome}
        maxValue={draft.maxMedianIncome}
        onMinChange={(v) => set('minMedianIncome', v)}
        onMaxChange={(v) => set('maxMedianIncome', v)}
        prefix="$"
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
        hint="Domain API data — not currently populated for any suburb; this filter won't narrow results yet"
        value={draft.maxDaysOnMarket}
        onChange={(v) => set('maxDaysOnMarket', v)}
        suffix="days"
      />
      <MaxFilter
        label="Vacancy Rate"
        hint="PropRadar data — currently only available for a handful of pilot suburbs"
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

function FilterGroup({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ marginBottom: '16px', paddingBottom: '16px', borderBottom: `1px solid ${colors.border}` }}>
      <div style={{ fontSize: '12px', fontWeight: 600, color: colors.textSecondary, marginBottom: '8px' }}>
        {label}
      </div>
      {children}
    </div>
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
}: {
  label: string
  minValue: string
  maxValue: string
  onMinChange: (v: string) => void
  onMaxChange: (v: string) => void
  prefix?: string
  suffix?: string
  hint?: string
}) {
  return (
    <FilterGroup label={label}>
      <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
        <NumberBox value={minValue} onChange={onMinChange} placeholder="Min" prefix={prefix} suffix={suffix} />
        <span style={{ color: colors.textMuted, fontSize: '12px' }}>–</span>
        <NumberBox value={maxValue} onChange={onMaxChange} placeholder="Max" prefix={prefix} suffix={suffix} />
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
}: {
  label: string
  value: string
  onChange: (v: string) => void
  suffix?: string
  hint?: string
}) {
  return (
    <FilterGroup label={label}>
      <NumberBox value={value} onChange={onChange} placeholder="Minimum" suffix={suffix} />
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
}: {
  label: string
  value: string
  onChange: (v: string) => void
  suffix?: string
  hint?: string
}) {
  return (
    <FilterGroup label={label}>
      <NumberBox value={value} onChange={onChange} placeholder="Maximum" suffix={suffix} />
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
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  prefix?: string
  suffix?: string
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
        style={{
          ...numberInputStyle,
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
                whiteSpace: 'nowrap',
              }}
            >
              {suburb.investment_score.toFixed(0)} score
            </div>
          )}
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
          <TileStat label="Median House" value={fmtCurrency(suburb.median_house_price)} />
          <TileStat label="Population" value={fmtNum(suburb.population)} />
          <TileStat label="Weekly Rent" value={fmtCurrency(suburb.median_rent_weekly)} />
          <TileStat label="To CBD" value={fmtKm(suburb.distance_to_cbd_km)} />
        </div>

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
      <div style={{ fontSize: '13px', fontWeight: 600, color: colors.textPrimary }}>{value}</div>
    </div>
  )
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
// Shared primitives
// ---------------------------------------------------------------------------

function Card({
  children,
  style,
  hoverable,
}: {
  children: ReactNode
  style?: React.CSSProperties
  hoverable?: boolean
}) {
  const [isHover, setIsHover] = useState(false)
  return (
    <div
      onMouseEnter={() => hoverable && setIsHover(true)}
      onMouseLeave={() => hoverable && setIsHover(false)}
      style={{
        backgroundColor: colors.cardBg,
        border: `1px solid ${isHover ? colors.pink : colors.border}`,
        borderRadius: '12px',
        boxShadow: isHover ? '0 4px 12px rgba(0,0,0,0.08)' : '0 1px 2px rgba(0,0,0,0.04)',
        padding: '24px',
        ...style,
      }}
    >
      {children}
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

const askResultCardStyle: React.CSSProperties = {
  backgroundColor: colors.pageBg,
  border: `1px solid ${colors.border}`,
  borderRadius: '8px',
  padding: '12px 16px',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
}
