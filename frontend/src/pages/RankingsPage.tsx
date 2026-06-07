import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import SeverityBadge from '../components/SeverityBadge'
import { usePageTitle } from '../hooks/usePageTitle'

interface RankedSuburb {
  rank: number
  sa2_code: string
  suburb_id: string | null
  sa2_name: string
  state: string
  population: number | null
  median_income: number | null
  scores: Record<string, number | null>
  risk_flags: string[]
}

interface RankingsResponse {
  score_type: string
  score_label: string
  count: number
  available_score_types: string[]
  rankings: RankedSuburb[]
}

const SCORE_LABELS: Record<string, string> = {
  investment_score:      'Overall Investment',
  liveability_score:    'Liveability',
  education_score:      'Education',
  growth_score:         'Growth',
  demographic_score:    'Demographics',
  housing_score:        'Housing Market',
  infrastructure_score: 'Infrastructure',
  gentrification_index: 'Gentrification',
}

const STATES = ['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT']

function scoreColor(v: number | null): string {
  if (v == null) return '#6b7fa0'
  if (v >= 7) return '#34d399'
  if (v >= 5) return '#fbbf24'
  return '#fb7185'
}

function ScoreBadge({ value }: { value: number | null }) {
  if (value == null) return <span style={{ color: '#6b7fa0' }}>—</span>
  return (
    <span style={{ color: scoreColor(value), fontWeight: 800, fontSize: '30px', letterSpacing: '-0.03em' }}>
      {value.toFixed(1)}
    </span>
  )
}

const LIMITS = [25, 50, 100, 200]

export default function RankingsPage() {
  const [scoreType, setScoreType] = useState('investment_score')
  const [stateFilter, setStateFilter] = useState('')
  const [limit, setLimit] = useState(25)
  const [data, setData] = useState<RankingsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()
  usePageTitle('Top Suburbs')

  useEffect(() => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams({ score_type: scoreType, limit: String(limit) })
    if (stateFilter) params.set('state', stateFilter)

    fetch(`/api/rankings?${params}`)
      .then(async r => {
        if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail || 'Failed to load rankings')
        return r.json() as Promise<RankingsResponse>
      })
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : 'Error'))
      .finally(() => setLoading(false))
  }, [scoreType, stateFilter, limit])

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '36px', fontWeight: 800, marginBottom: '8px', color: '#cdd8e8', letterSpacing: '-0.03em' }}>
        Top Suburbs
      </h1>
      <p style={{ color: '#6b7fa0', marginBottom: '32px', fontSize: '15px' }}>
        {data
          ? `Showing top ${data.rankings.length} of ${stateFilter ? `${data.rankings.length > limit - 1 ? limit + '+' : data.rankings.length}` : '~2,450'} ${stateFilter || 'Australian'} suburbs · ranked by ${SCORE_LABELS[scoreType] ?? scoreType}`
          : '2,450+ Australian SA2 regions ranked by investment signals from government open data.'}
      </p>

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '32px', alignItems: 'center' }}>
        {Object.entries(SCORE_LABELS).map(([key, label]) => (
          <button key={key} onClick={() => setScoreType(key)}
            style={{
              padding: '7px 14px', borderRadius: '8px', cursor: 'pointer', fontSize: '13px',
              backgroundColor: scoreType === key ? '#2dd4bf' : '#151b27',
              color: scoreType === key ? '#0d1117' : '#9aafc8',
              border: scoreType === key ? 'none' : '1px solid #28334a',
              fontWeight: scoreType === key ? 700 : 400,
              transition: 'all 0.15s',
            }}>
            {label}
          </button>
        ))}
        <select value={stateFilter} onChange={e => setStateFilter(e.target.value)}
          style={{ padding: '7px 14px', backgroundColor: '#151b27', color: '#9aafc8', border: '1px solid #28334a', borderRadius: '8px', cursor: 'pointer', fontSize: '13px' }}>
          <option value="">All States</option>
          {STATES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>

        {/* Show N selector */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginLeft: 'auto' }}>
          <span style={{ color: '#6b7fa0', fontSize: '12px' }}>Show</span>
          {LIMITS.map(n => (
            <button key={n} onClick={() => setLimit(n)}
              style={{
                padding: '5px 10px', borderRadius: '6px', cursor: 'pointer', fontSize: '12px',
                backgroundColor: limit === n ? 'rgba(45,212,191,0.15)' : 'transparent',
                color: limit === n ? '#2dd4bf' : '#6b7fa0',
                border: limit === n ? '1px solid rgba(45,212,191,0.3)' : '1px solid transparent',
              }}>
              {n}
            </button>
          ))}
        </div>
      </div>

      {loading && <p style={{ color: '#6b7fa0' }}>Loading rankings…</p>}
      {error   && <p style={{ color: '#fb7185' }}>{error}</p>}

      {data && !loading && (
        <div style={{ display: 'grid', gap: '10px' }}>
          {data.rankings.map(suburb => (
            <button key={suburb.sa2_code} onClick={() => navigate(suburb.suburb_id ? `/suburb-group/${suburb.suburb_id}` : `/suburb/${suburb.sa2_code}`)}
              style={{
                width: '100%', textAlign: 'left', cursor: 'pointer',
                backgroundColor: '#151b27',
                border: suburb.rank === 1 ? '1px solid rgba(52,211,153,0.4)' : '1px solid #28334a',
                borderRadius: '12px', padding: '18px 24px',
                display: 'grid', gridTemplateColumns: '48px 1fr auto auto',
                alignItems: 'center', gap: '16px', color: '#cdd8e8',
                boxShadow: '0 2px 12px rgba(0,0,0,0.35)',
                transition: 'border-color 0.15s',
              }}>
              {/* Rank */}
              <span style={{
                fontSize: '20px', fontWeight: 800, letterSpacing: '-0.02em',
                color: suburb.rank === 1 ? '#34d399' : suburb.rank <= 3 ? '#fbbf24' : '#6b7fa0',
              }}>
                #{suburb.rank}
              </span>

              {/* Name + meta */}
              <div>
                <div style={{ fontWeight: 700, fontSize: '16px', color: '#cdd8e8' }}>{suburb.sa2_name}</div>
                <div style={{ color: '#6b7fa0', fontSize: '13px', marginTop: '2px' }}>
                  {suburb.state}
                  {suburb.population ? ` · ${suburb.population.toLocaleString()} residents` : ''}
                  {suburb.median_income ? ` · $${Math.round(suburb.median_income / 1000)}k median income` : ''}
                </div>
                {suburb.risk_flags.length > 0 && (
                  <div style={{ marginTop: '6px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {suburb.risk_flags.slice(0, 3).map(f => (
                      <SeverityBadge key={f} level="bad" label={f.replace(/_/g, ' ')} />
                    ))}
                  </div>
                )}
              </div>

              {/* Primary score */}
              <div style={{ textAlign: 'center', minWidth: '64px' }}>
                <ScoreBadge value={suburb.scores[scoreType] ?? null} />
                <div style={{ color: '#6b7fa0', fontSize: '11px', marginTop: '2px' }}>
                  {SCORE_LABELS[scoreType]}
                </div>
              </div>

              {/* Mini dimension scores */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px', minWidth: '180px' }}>
                {Object.entries(SCORE_LABELS)
                  .filter(([k]) => k !== scoreType && k !== 'gentrification_index')
                  .slice(0, 4)
                  .map(([key, lbl]) => {
                    const v = suburb.scores[key] ?? 0
                    return (
                      <div key={key} style={{ fontSize: '11px', color: '#6b7fa0' }}>
                        <span style={{ color: scoreColor(v), fontWeight: 600 }}>{v.toFixed(1)}</span> {lbl}
                      </div>
                    )
                  })}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
