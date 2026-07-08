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
