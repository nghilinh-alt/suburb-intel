import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'

// ── Types ──────────────────────────────────────────────────────────────────

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

interface SA2Entry {
  sa2_code: string
  sa2_name: string
  population: number | null
  scores: Scores
  intermediates: Record<string, number | null>
  facts: Record<string, number | null>
  risk_flags: string[]
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
  sa2_breakdown: SA2Entry[]
  facts: Record<string, number | null>
  intermediates: Record<string, number | null>
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

// ── Helpers ────────────────────────────────────────────────────────────────

function fmt(v: number | null | undefined, dp = 1, suffix = '') {
  if (v == null) return '—'
  return `${v.toFixed(dp)}${suffix}`
}

function fmtAUD(v: number | null) {
  if (!v) return '—'
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`
  return `$${Math.round(v).toLocaleString()}`
}

function scoreColor(v: number | null) {
  if (v == null) return '#9ca0aa'
  if (v >= 7) return '#2ecc71'
  if (v >= 5) return '#f39c12'
  return '#e74c3c'
}

// Key facts shown under each dimension score card
function getDimFacts(key: string, intermediates: Record<string, number | null>, facts: Record<string, number | null>): string[] {
  switch (key) {
    case 'liveability_score': return [
      `${facts.osm_cafes ?? '—'} cafes · ${facts.osm_restaurants ?? '—'} restaurants`,
      `${facts.pt_stop_train ?? 0} train · ${facts.pt_stop_tram ?? 0} tram · ${facts.pt_stop_bus ?? '—'} bus stops`,
      `${intermediates.health_gp_count ?? '—'} GP clinics · ${facts.osm_pharmacies ?? '—'} pharmacies`,
      `${facts.osm_parks ?? '—'} parks · ${facts.osm_gyms ?? '—'} gyms`,
    ]
    case 'growth_score': return [
      `${fmt(facts.pop_growth_proj_pct, 1, '%')} population growth to 2031`,
      `${facts.building_approvals_1yr ?? '—'} building approvals (1yr)`,
      intermediates.infra_project_count
        ? `${intermediates.infra_project_count} active govt projects · ${fmtAUD(intermediates.infra_committed_aud)} committed`
        : 'No committed govt projects nearby',
    ]
    case 'education_score': return [
      `Avg school ICSEA: ${fmt(intermediates.edu_avg_icsea, 0)}`,
      `${intermediates.edu_top_school_count ?? '—'} top schools (ICSEA ≥ 1100)`,
      `${intermediates.edu_secondary_count ?? '—'} secondary schools · ${intermediates.edu_tertiary_count ?? '—'} uni/TAFE nearby`,
    ]
    case 'demographic_score': return [
      `Median income: ${facts.median_income ? `$${Math.round(facts.median_income).toLocaleString()}` : '—'}`,
      `Uni degree: ${fmt(facts.uni_degree_pct, 1, '%')} · Professionals: ${fmt(facts.professionals_managers_pct, 1, '%')}`,
      `Unemployment: ${fmt(facts.unemployment_pct, 1, '%')} · SEIFA IEO decile: ${facts.seifa_ieo_decile ?? '—'}/10`,
    ]
    case 'housing_score': return [
      `Mortgage stress: ${fmt(facts.high_mortgage_stress_pct, 1, '%')} · Rent stress: ${fmt(facts.high_rent_stress_pct, 1, '%')}`,
      `${fmt(facts.separate_house_pct, 1, '%')} houses · ${fmt(facts.flat_apartment_pct, 1, '%')} apartments`,
      `${fmt(facts.renters_pct, 1, '%')} renters · ${fmt(facts.social_housing_pct, 1, '%')} social housing`,
    ]
    case 'infrastructure_score': return [
      intermediates.infra_committed_aud
        ? `${fmtAUD(intermediates.infra_committed_aud)} committed investment`
        : 'No committed govt investment nearby',
      `${intermediates.infra_project_count ?? 0} active infrastructure projects`,
      `Transit score: ${fmt(intermediates.transit_score_raw, 0)} (train×4 + tram×3 + bus×1)`,
    ]
    case 'gentrification_index': return [
      `Residential turnover (1yr): ${fmt(facts.moved_in_1yr_pct, 1, '%')}`,
      `Professionals: ${fmt(facts.professionals_managers_pct, 1, '%')} · Degree holders: ${fmt(facts.uni_degree_pct, 1, '%')}`,
      `Cafes per 1k residents · Building activity · Pop. growth projection`,
    ]
    default: return []
  }
}

const DIMENSIONS = [
  { key: 'liveability_score',    label: 'Liveability',     desc: 'Amenity access, transit, healthcare, parks' },
  { key: 'growth_score',         label: 'Growth',          desc: 'Population growth, investment pipeline, gentrification' },
  { key: 'education_score',      label: 'Education',       desc: 'School quality, coverage of all levels' },
  { key: 'demographic_score',    label: 'Demographics',    desc: 'Income, SEIFA, workforce education' },
  { key: 'housing_score',        label: 'Housing Market',  desc: 'Mortgage/rent stress, dwelling character' },
  { key: 'infrastructure_score', label: 'Infrastructure',  desc: 'Committed government investment pipeline' },
  { key: 'gentrification_index', label: 'Gentrification',  desc: 'Composite social uplift signal' },
]

// ── Components ─────────────────────────────────────────────────────────────

function DimensionCard({
  dimKey, label, value, facts, intermediates, sa2Breakdown, isMulti,
}: {
  dimKey: string
  label: string
  value: number | null
  facts: Record<string, number | null>
  intermediates: Record<string, number | null>
  sa2Breakdown: SA2Entry[]
  isMulti: boolean
}) {
  const color = scoreColor(value)
  const pct   = value != null ? (value / 10) * 100 : 0
  const subFacts = getDimFacts(dimKey, intermediates, facts)

  return (
    <div style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '20px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
      {/* Header */}
      <div style={{ fontSize: '12px', color: '#9ca0aa', textTransform: 'uppercase', letterSpacing: '1px' }}>{label}</div>
      <div style={{ fontSize: '40px', fontWeight: 700, color, lineHeight: 1 }}>{fmt(value)}</div>

      {/* Progress bar */}
      <div style={{ height: '4px', backgroundColor: '#4b566a', borderRadius: '2px' }}>
        <div style={{ height: '100%', width: `${pct}%`, backgroundColor: color, borderRadius: '2px' }} />
      </div>

      {/* Per-SA2 breakdown for multi-area suburbs */}
      {isMulti && sa2Breakdown.length > 0 && (
        <div style={{ borderTop: '1px solid #4b566a', paddingTop: '8px' }}>
          {sa2Breakdown.map(sa2 => {
            const v = sa2.scores[dimKey as keyof Scores]
            const c = scoreColor(v)
            const w = v != null ? (v / 10) * 100 : 0
            const shortName = sa2.sa2_name.replace(/^.+ - /, '')
            return (
              <div key={sa2.sa2_code} style={{ marginBottom: '6px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', marginBottom: '3px' }}>
                  <span style={{ color: '#9ca0aa' }}>{shortName}</span>
                  <span style={{ color: c, fontWeight: 600 }}>{fmt(v)}</span>
                </div>
                <div style={{ height: '3px', backgroundColor: '#4b566a', borderRadius: '2px' }}>
                  <div style={{ height: '100%', width: `${w}%`, backgroundColor: c, borderRadius: '2px', opacity: 0.7 }} />
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Key input facts */}
      {subFacts.length > 0 && (
        <div style={{ borderTop: '1px solid #4b566a', paddingTop: '8px' }}>
          {subFacts.filter(f => f && !f.includes('undefined') && !f.includes('NaN')).map((fact, i) => (
            <div key={i} style={{ fontSize: '12px', color: '#9ca0aa', marginBottom: '3px', lineHeight: 1.4 }}>
              {fact}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────

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
  const { suburb_name, state: stateCode, scores, facts, intermediates, insight, risk_flags, tags, sa2_count, sa2_names, sa2_codes, sa2_breakdown, population } = data
  const isMulti = sa2_count > 1

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

      {/* ABS split notice */}
      {isMulti && (
        <div style={{ backgroundColor: '#2a3040', border: '1px solid #4b566a', borderRadius: '8px', padding: '12px 18px', marginBottom: '24px', display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
          <span style={{ fontSize: '18px' }}>ℹ️</span>
          <div>
            <p style={{ margin: '0 0 8px', color: '#d1d5da', fontSize: '14px' }}>
              <strong>Why are there {sa2_count} areas?</strong> The ABS splits this suburb into {sa2_count} statistical areas for census data collection.
              The combined score is a population-weighted average — each dimension card shows individual area scores below.
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

      {/* Dimension grid with breakdown */}
      <h2 style={{ fontSize: '22px', marginBottom: '16px' }}>Score Breakdown</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px', marginBottom: '40px' }}>
        {DIMENSIONS.map(d => (
          <DimensionCard
            key={d.key}
            dimKey={d.key}
            label={d.label}
            value={scores[d.key as keyof Scores]}
            facts={facts}
            intermediates={intermediates}
            sa2Breakdown={sa2_breakdown}
            isMulti={isMulti}
          />
        ))}
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
