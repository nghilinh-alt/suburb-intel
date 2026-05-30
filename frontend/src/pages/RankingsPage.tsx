import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

interface RankedSuburb {
  rank: number
  sa2_code: string
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
  investment_score:    'Overall Investment',
  liveability_score:  'Liveability',
  education_score:    'Education',
  growth_score:       'Growth',
  demographic_score:  'Demographics',
  housing_score:      'Housing Market',
  infrastructure_score: 'Infrastructure',
  gentrification_index: 'Gentrification',
}

const STATES = ['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT']

function ScoreBadge({ value }: { value: number | null }) {
  if (value == null) return <span style={{ color: '#9ca0aa' }}>—</span>
  const color = value >= 7 ? '#2ecc71' : value >= 5 ? '#f39c12' : '#e74c3c'
  return <span style={{ color, fontWeight: 700, fontSize: '28px' }}>{value.toFixed(1)}</span>
}

export default function RankingsPage() {
  const [scoreType, setScoreType] = useState('investment_score')
  const [stateFilter, setStateFilter] = useState('')
  const [data, setData] = useState<RankingsResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    setLoading(true)
    setError(null)
    const params = new URLSearchParams({ score_type: scoreType, limit: '30' })
    if (stateFilter) params.set('state', stateFilter)

    fetch(`/api/rankings?${params}`)
      .then(async r => {
        if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail || 'Failed to load rankings')
        return r.json() as Promise<RankingsResponse>
      })
      .then(setData)
      .catch(e => setError(e instanceof Error ? e.message : 'Error'))
      .finally(() => setLoading(false))
  }, [scoreType, stateFilter])

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '32px', marginBottom: '8px' }}>Top Suburbs</h2>
      <p style={{ color: '#9ca0aa', marginBottom: '32px' }}>
        2,472 Australian SA2 regions ranked by investment signals from government open data.
      </p>

      {/* Filter bar */}
      <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', marginBottom: '32px' }}>
        {Object.entries(SCORE_LABELS).map(([key, label]) => (
          <button key={key} onClick={() => setScoreType(key)}
            style={{
              padding: '8px 16px', borderRadius: '6px', cursor: 'pointer', fontSize: '13px',
              backgroundColor: scoreType === key ? '#f8f8f2' : '#343b47',
              color: scoreType === key ? '#282c34' : '#d1d5da',
              border: scoreType === key ? 'none' : '1px solid #4b566a',
              fontWeight: scoreType === key ? 700 : 400,
            }}>
            {label}
          </button>
        ))}
        <select value={stateFilter} onChange={e => setStateFilter(e.target.value)}
          style={{ padding: '8px 14px', backgroundColor: '#343b47', color: '#f8f8f2', border: '1px solid #4b566a', borderRadius: '6px', cursor: 'pointer', fontSize: '13px' }}>
          <option value="">All States</option>
          {STATES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      {loading && <p style={{ color: '#9ca0aa' }}>Loading rankings…</p>}
      {error   && <p style={{ color: '#e74c3c' }}>{error}</p>}

      {data && !loading && (
        <div style={{ display: 'grid', gap: '12px' }}>
          {data.rankings.map(suburb => (
            <button key={suburb.sa2_code} onClick={() => navigate(`/suburb/${suburb.sa2_code}`)}
              style={{
                width: '100%', textAlign: 'left', cursor: 'pointer',
                backgroundColor: suburb.rank === 1 ? '#2a3a2a' : '#343b47',
                border: suburb.rank === 1 ? '1px solid #2ecc71' : '1px solid #4b566a',
                borderRadius: '10px', padding: '20px 24px',
                display: 'grid', gridTemplateColumns: '48px 1fr auto auto',
                alignItems: 'center', gap: '16px', color: '#f8f8f2',
              }}>
              {/* Rank */}
              <span style={{ fontSize: '22px', fontWeight: 700, color: suburb.rank <= 3 ? '#f39c12' : '#9ca0aa' }}>
                #{suburb.rank}
              </span>
              {/* Name + meta */}
              <div>
                <div style={{ fontWeight: 600, fontSize: '17px' }}>{suburb.sa2_name}</div>
                <div style={{ color: '#9ca0aa', fontSize: '13px', marginTop: '2px' }}>
                  {suburb.state}
                  {suburb.population ? ` · ${suburb.population.toLocaleString()} residents` : ''}
                  {suburb.median_income ? ` · $${Math.round(suburb.median_income / 1000)}k median income` : ''}
                </div>
                {suburb.risk_flags.length > 0 && (
                  <div style={{ marginTop: '6px', display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                    {suburb.risk_flags.slice(0, 3).map(f => (
                      <span key={f} style={{ fontSize: '11px', padding: '2px 8px', backgroundColor: '#4a3030', color: '#e07070', borderRadius: '4px' }}>
                        {f.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                )}
              </div>
              {/* Primary score */}
              <div style={{ textAlign: 'center', minWidth: '64px' }}>
                <ScoreBadge value={suburb.scores[scoreType] ?? null} />
                <div style={{ color: '#9ca0aa', fontSize: '11px', marginTop: '2px' }}>
                  {SCORE_LABELS[scoreType]}
                </div>
              </div>
              {/* Mini dimension bars */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 16px', minWidth: '180px' }}>
                {Object.entries(SCORE_LABELS).filter(([k]) => k !== scoreType && k !== 'gentrification_index').slice(0, 4).map(([key, lbl]) => (
                  <div key={key} style={{ fontSize: '11px', color: '#9ca0aa' }}>
                    <span style={{ color: '#d1d5da' }}>{(suburb.scores[key] ?? 0).toFixed(1)}</span> {lbl}
                  </div>
                ))}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
