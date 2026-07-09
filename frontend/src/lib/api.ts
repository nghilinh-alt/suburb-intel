// Vite's dev server proxies /api/* to the backend (see vite.config.ts) so
// requests dodge CORS in dev without needing CORS middleware on the backend.
// Override with an absolute URL (e.g. in production) via VITE_API_BASE_URL.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? '/api'

export interface SuburbSearchResult {
  sa2_code: string
  sa2_name: string
  state: string
  population: number | null
  median_income: number | null
  median_age: number | null
  distance_to_cbd_km?: number | null
}

async function parseErrorDetail(response: Response): Promise<string> {
  const body = await response.json().catch(() => null)
  return (body && typeof body.detail === 'string' ? body.detail : null) ?? response.statusText
}

export async function searchSuburbs(
  query: string,
  opts: { state?: string; limit?: number } = {},
): Promise<SuburbSearchResult[] | SuburbSearchResult> {
  const params = new URLSearchParams({ query })
  if (opts.state) params.set('state', opts.state)
  if (opts.limit) params.set('limit', String(opts.limit))

  const res = await fetch(`${API_BASE}/search/?${params.toString()}`)
  if (!res.ok) throw new Error(await parseErrorDetail(res))
  return res.json()
}

export interface ParsedFilter {
  city: string | null
  state: string | null
  max_distance_to_cbd_km: number | null
  sort_by: string
  sort_dir: string
  limit: number
}

export interface AskSearchResult {
  sa2_code: string
  sa2_name: string
  state: string
  distance_to_cbd_km: number | null
  population: number | null
  median_income: number | null
  investment_score: number | null
}

export interface AskSearchResponse {
  parsed_filter: ParsedFilter
  results: AskSearchResult[]
  message: string | null
}

export async function askSearch(prompt: string): Promise<AskSearchResponse> {
  const res = await fetch(`${API_BASE}/search/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  })
  if (!res.ok) throw new Error(await parseErrorDetail(res))
  return res.json()
}

// ---------------------------------------------------------------------------
// Filter search (Search page's filter sidebar)
// ---------------------------------------------------------------------------

export interface SuburbFilters {
  states?: string[]
  max_distance_to_cbd_km?: number
  min_median_house_price?: number
  max_median_house_price?: number
  min_median_unit_price?: number
  max_median_unit_price?: number
  min_population?: number
  max_population?: number
  min_pop_growth_5yr_pct?: number
  min_median_income?: number
  max_median_income?: number
  min_median_rent_weekly?: number
  max_median_rent_weekly?: number
  min_owner_occupied_pct?: number
  max_owner_occupied_pct?: number
  max_social_housing_pct?: number
  max_unemployment_pct?: number
  min_seifa_irsd_decile?: number
  min_avg_school_icsea?: number
  max_days_on_market?: number
  min_investment_score?: number
  min_economic_score?: number
  min_demographic_score?: number
  min_gross_yield_house_pct?: number
  max_vacancy_rate_pct?: number
}

export interface FilteredSuburb {
  sa2_code: string
  sa2_name: string
  state: string
  distance_to_cbd_km: number | null
  population: number | null
  median_income: number | null
  median_rent_weekly: number | null
  owner_occupied_pct: number | null
  social_housing_pct: number | null
  unemployment_pct: number | null
  seifa_irsd_decile: number | null
  avg_school_icsea: number | null
  pop_growth_5yr_pct: number | null
  pop_growth_proj_pct: number | null
  median_house_price: number | null
  median_unit_price: number | null
  days_on_market: number | null
  investment_score: number | null
  economic_score: number | null
  demographic_score: number | null
  gross_yield_house_pct: number | null
  vacancy_rate_pct: number | null
}

export interface FilterSuburbsResponse {
  total_count: number
  limit: number
  offset: number
  results: FilteredSuburb[]
}

export async function filterSuburbs(
  filters: SuburbFilters,
  opts: { sortBy?: string; sortDir?: 'asc' | 'desc'; limit?: number; offset?: number } = {},
): Promise<FilterSuburbsResponse> {
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(filters)) {
    if (value === undefined || value === null) continue
    params.set(key, Array.isArray(value) ? value.join(',') : String(value))
  }
  if (opts.sortBy) params.set('sort_by', opts.sortBy)
  if (opts.sortDir) params.set('sort_dir', opts.sortDir)
  params.set('limit', String(opts.limit ?? 20))
  params.set('offset', String(opts.offset ?? 0))

  const res = await fetch(`${API_BASE}/search/filter?${params.toString()}`)
  if (!res.ok) throw new Error(await parseErrorDetail(res))
  return res.json()
}

export async function getFilterOptions(): Promise<{ states: string[] }> {
  const res = await fetch(`${API_BASE}/search/filter-options`)
  if (!res.ok) throw new Error(await parseErrorDetail(res))
  return res.json()
}

// ---------------------------------------------------------------------------
// Rankings
// ---------------------------------------------------------------------------

export type ScoreType =
  | 'investment_score'
  | 'demographic_score'
  | 'economic_score'
  | 'housing_pressure_score'
  | 'resilience_score'
  | 'gov_investment_score'

export interface RankedSuburb {
  rank: number
  sa2_code: string
  sa2_name: string
  state: string
  distance_to_cbd_km: number | null
  investment_score: number | null
  demographic_score: number | null
  economic_score: number | null
  housing_pressure_score: number | null
  resilience_score: number | null
  gov_investment_score: number | null
}

export interface RankingsResponse {
  score_type: ScoreType
  count: number
  rankings: RankedSuburb[]
}

export async function getRankings(scoreType: ScoreType, limit = 25): Promise<RankingsResponse> {
  const params = new URLSearchParams({ score_type: scoreType, limit: String(limit) })
  const res = await fetch(`${API_BASE}/rankings/?${params.toString()}`)
  if (!res.ok) throw new Error(await parseErrorDetail(res))
  return res.json()
}
