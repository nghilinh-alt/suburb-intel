import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'

interface Scores {
  investment_score: number | null
  liveability_score: number | null
  education_score: number | null
  growth_score: number | null
  demographic_score: number | null
  housing_score: number | null
  infrastructure_score: number | null
  gentrification_index: number | null
}

interface GroupReport {
  suburb_id: string
  suburb_name: string
  state: string
  sa2_count: number
  sa2_codes: string[]
  sa2_names: string[]
  population: number | null
  is_aggregate: boolean
  scores: Scores
  facts: {
    median_income: number | null
    median_age: number | null
    unemployment_pct: number | null
    uni_degree_pct: number | null
    pop_growth_proj_pct: number | null
  }
  risk_flags: string[]
  tags: string[]
  insight: string
  note: string | null
  score_version: string | null
}

type PageState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: GroupReport }

const DIMENSIONS = [
  { key: 'liveability_score',    label: 'Liveability',    desc: 'Amenity access, transit, healthcare, parks' },
  { key: 'growth_score',         label: 'Growth',         desc: 'Population growth, investment pipeline, gentrification' },
  { key: 'education_score',      label: 'Education',      desc: 'School quality, coverage of all levels' },
  { key: 'demographic_score',    label: 'Demographics',   desc: 'Income, SEIFA, workforce education' },
  { key: 'housing_score',        label: 'Housing Market', desc: 'Mortgage/rent stress, dwelling character' },
  { key: 'infrastructure_score', label: 'Infrastructure', desc: 'Committed government investment pipeline' },
  { key: 'gentrification_index', label: 'Gentrification', desc: 'Composite social uplift signal' },
]

function scoreColor(v: number | null) {
  if (v == null) return '#9ca0aa'
  if (v >= 7) return '#2ecc71'
  if (v >= 5) return '#f39c12'
  return '#e74c3c'
}

function fmt(v: number | null, dp = 1) {
  return v != null ? v.toFixed(dp) : '—'
}

function DimensionCard({ label, value, desc }: { label: string; value: number | null; desc: string }) {
  const color = scoreColor(value)
  const pct = value != null ? (value / 10) * 100 : 0
  return (
    <div style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '20px' }}>
      <div style={{ fontSize: '12px', color: '#9ca0aa', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '6px' }}>{label}</div>
      <div style={{ fontSize: '42px', fontWeight: 700, color }}>{fmt(value)}</div>
      <div style={{ height: '4px', backgroundColor: '#4b566a', borderRadius: '2px', margin: '10px 0 8px' }}>
        <div style={{ height: '100%', width: `${pct}%`, backgroundColor: color, borderRadius: '2px' }} />
      </div>
      <p style={{ color: '#9ca0aa', fontSize: '12px', margin: 0 }}>{desc}</p>
    </div>
  )
}

export default function SuburbGroupPage() {
  const { id = '' } = useParams<{ id: string }>()
  const [state, setState] = useState<PageState>({ status: 'loading' })
  const navigate = useNavigate()

  useEffect(() => {
    if (!id) { setState({ status: 'error', message: 'Missing suburb ID.' }); return }
    setState({ status: 'loading' })
    let cancelled = false
    fetch(`/api/suburb-group/${encodeURIComponent(id)}`)
      .then(async r => {
        if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail || r.statusText)
        return r.json() as Promise<GroupReport>
      })
      .then(data => { if (!cancelled) setState({ status: 'ready', data }) })
      .catch(err => { if (!cancelled) setState({ status: 'error', message: err instanceof Error ? err.message : 'Unknown error' }) })
    return () => { cancelled = true }
  }, [id])

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '0 20px 60px' }}>
      <div style={{ marginBottom: '24px' }}>
        <Link to="/" style={{ color: '#9ca0aa', textDecoration: 'none', fontSize: '14px' }}>← Back to Search</Link>
      </div>
      {state.status === 'loading' && <p style={{ color: '#9ca0aa' }}>Loading…</p>}
      {state.status === 'error' && (
        <div style={{ backgroundColor: '#3b2a2a', border: '1px solid #6b3b3b', borderRadius: '10px', padding: '24px', color: '#f8d7da' }}>
          <h2 style={{ marginTop: 0 }}>Could not load suburb</h2>
          <p style={{ margin: 0 }}>{state.message}</p>
        </div>
      )}
      {state.status === 'ready' && <ReadyView data={state.data} onNavigateSA2={navigate} />}
    </div>
  )
}

function ReadyView({ data, onNavigateSA2 }: { data: GroupReport; onNavigateSA2: (path: string) => void }) {
  const { suburb_name, state: stateCode, scores, facts, insight, risk_flags, tags, note, sa2_count, sa2_names, sa2_codes, population } = data

  return (
    <>
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' }}>
          <h1 style={{ fontSize: '42px', margin: 0 }}>{suburb_name}</h1>
          <span style={{ color: '#9ca0aa', fontSize: '22px' }}>{stateCode}</span>
        </div>
        {population && <p style={{ color: '#9ca0aa', margin: '4px 0 0', fontSize: '13px' }}>{population.toLocaleString()} residents</p>}
        {tags.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
            {tags.map(t => (
              <span key={t} style={{ padding: '4px 12px', backgroundColor: '#2a3a4a', color: '#7ec8e3', borderRadius: '20px', fontSize: '12px', fontWeight: 600 }}>{t}</span>
            ))}
          </div>
        )}
      </div>

      {/* Note about ABS split */}
      {sa2_count > 1 && (
        <div style={{ backgroundColor: '#2a3040', border: '1px solid #4b566a', borderRadius: '8px', padding: '12px 18px', marginBottom: '24px', display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
          <span style={{ fontSize: '18px' }}>ℹ️</span>
          <div>
            <p style={{ margin: '0 0 8px', color: '#d1d5da', fontSize: '14px' }}>
              <strong>Why are there {sa2_count} areas?</strong> The ABS splits this suburb into {sa2_count} statistical areas (SA2s) for census data collection. The scores below are population-weighted averages across all areas — this is the real Keysborough picture.
            </p>
            <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
              {sa2_codes.map((code, i) => (
                <button key={code} onClick={() => onNavigateSA2(`/suburb/${code}`)}
                  style={{ padding: '4px 12px', backgroundColor: '#343b47', color: '#9ca0aa', border: '1px solid #4b566a', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>
                  View {sa2_names[i]} →
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Investment score hero */}
      <div style={{ backgroundColor: '#1e2530', border: '1px solid #4b566a', borderRadius: '12px', padding: '28px 32px', marginBottom: '32px', display: 'flex', alignItems: 'center', gap: '32px' }}>
        <div>
          <div style={{ fontSize: '13px', color: '#9ca0aa', textTransform: 'uppercase', letterSpacing: '1px' }}>Investment Score</div>
          <div style={{ fontSize: '72px', fontWeight: 800, color: scoreColor(scores.investment_score), lineHeight: 1 }}>
            {fmt(scores.investment_score)}
          </div>
          <div style={{ color: '#9ca0aa', fontSize: '13px' }}>out of 10</div>
        </div>
        <div style={{ flex: 1, color: '#d1d5da', fontSize: '16px', lineHeight: 1.7 }}>{insight}</div>
      </div>

      {/* Dimension grid */}
      <h2 style={{ fontSize: '22px', marginBottom: '16px' }}>Score Breakdown</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '16px', marginBottom: '40px' }}>
        {DIMENSIONS.map(d => (
          <DimensionCard key={d.key} label={d.label} value={scores[d.key as keyof Scores]} desc={d.desc} />
        ))}
      </div>

      {/* Key facts */}
      <div style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '24px', marginBottom: '32px' }}>
        <h3 style={{ fontSize: '16px', marginTop: 0, marginBottom: '16px' }}>Key Facts</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '16px' }}>
          {[
            { label: 'Median income', value: facts.median_income ? `$${Math.round(facts.median_income).toLocaleString()}` : '—' },
            { label: 'Median age', value: fmt(facts.median_age, 0) },
            { label: 'Unemployment %', value: `${fmt(facts.unemployment_pct)}%` },
            { label: 'Uni degree %', value: `${fmt(facts.uni_degree_pct)}%` },
            { label: 'Pop. growth to 2031', value: `${fmt(facts.pop_growth_proj_pct)}%` },
          ].map(({ label, value }) => (
            <div key={label} style={{ backgroundColor: '#2a3040', borderRadius: '6px', padding: '12px 16px' }}>
              <div style={{ color: '#9ca0aa', fontSize: '12px', marginBottom: '4px' }}>{label}</div>
              <div style={{ color: '#f8f8f2', fontWeight: 600, fontSize: '18px' }}>{value}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Risk flags */}
      {risk_flags.length > 0 && (
        <div style={{ marginBottom: '40px' }}>
          <h3 style={{ fontSize: '18px', marginBottom: '12px' }}>⚠️ Risk Flags</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            {risk_flags.map(f => (
              <span key={f} style={{ padding: '8px 16px', backgroundColor: '#4a3030', color: '#e07070', borderRadius: '6px', fontSize: '13px' }}>
                {f.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Paywall */}
      <div style={{ marginTop: '48px', textAlign: 'center', backgroundColor: '#1e2530', border: '1px solid #4b566a', padding: '48px', borderRadius: '12px' }}>
        <h2 style={{ fontSize: '28px', marginBottom: '12px' }}>Unlock Full Report</h2>
        <p style={{ fontSize: '16px', color: '#9ca0aa', marginBottom: '28px', maxWidth: '480px', margin: '0 auto 28px' }}>
          Get suburb comparisons, school catchment maps, infrastructure project details, and PDF export.
        </p>
        <button style={{ padding: '16px 48px', fontSize: '18px', fontWeight: 700, backgroundColor: '#e74c3c', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
          Unlock for $9
        </button>
      </div>
    </>
  )
}
