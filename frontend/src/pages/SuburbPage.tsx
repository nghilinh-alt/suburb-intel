import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

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

interface Intermediates {
  edu_avg_icsea: number | null
  edu_top_school_count: number | null
  edu_secondary_count: number | null
  edu_tertiary_count: number | null
  health_hospital_score: number | null
  health_gp_count: number | null
  infra_committed_aud: number | null
  infra_project_count: number | null
  transit_score_raw: number | null
}

interface Facts {
  population: number | null
  median_income: number | null
  median_age: number | null
  unemployment_pct: number | null
  uni_degree_pct: number | null
  professionals_managers_pct: number | null
  separate_house_pct: number | null
  flat_apartment_pct: number | null
  flat_high_rise_pct: number | null
  renters_pct: number | null
  high_mortgage_stress_pct: number | null
  pop_growth_proj_pct: number | null
  building_approvals_1yr: number | null
  pt_stop_train: number | null
  pt_stop_bus: number | null
  osm_cafes: number | null
  osm_medical_centers: number | null
  seifa_irsd_decile: number | null
  seifa_ieo_decile: number | null
}

interface SuburbReport {
  sa2_code: string
  sa2_name: string | null
  state: string | null
  census_year: number
  scores: Scores
  intermediates: Intermediates
  facts: Facts
  risk_flags: string[]
  tags: string[]
  insight: string
  score_version: string | null
}

type PageState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: SuburbReport }

// ── Helpers ────────────────────────────────────────────────────────────────

function fmt(n: number | null | undefined, dp = 0): string {
  if (n == null || isNaN(n)) return '—'
  return n.toFixed(dp)
}

function fmtAUD(n: number | null): string {
  if (!n) return '—'
  if (n >= 1_000_000_000) return `$${(n / 1e9).toFixed(1)}B`
  if (n >= 1_000_000)     return `$${(n / 1e6).toFixed(0)}M`
  if (n >= 1_000)         return `$${(n / 1e3).toFixed(0)}K`
  return `$${n}`
}

function scoreColor(v: number | null): string {
  if (v == null) return '#9ca0aa'
  if (v >= 7) return '#2ecc71'
  if (v >= 5) return '#f39c12'
  return '#e74c3c'
}

// ── Components ─────────────────────────────────────────────────────────────

function DimensionCard({ label, value, description }: { label: string; value: number | null; description: string }) {
  const color = scoreColor(value)
  const pct = value != null ? (value / 10) * 100 : 0
  return (
    <div style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '20px' }}>
      <div style={{ fontSize: '12px', color: '#9ca0aa', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '6px' }}>
        {label}
      </div>
      <div style={{ fontSize: '42px', fontWeight: 700, color }}>{fmt(value, 1)}</div>
      {/* Progress bar */}
      <div style={{ height: '4px', backgroundColor: '#4b566a', borderRadius: '2px', margin: '10px 0 8px' }}>
        <div style={{ height: '100%', width: `${pct}%`, backgroundColor: color, borderRadius: '2px', transition: 'width 0.4s' }} />
      </div>
      <p style={{ color: '#9ca0aa', fontSize: '12px', margin: 0 }}>{description}</p>
    </div>
  )
}

function FactRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #3a4050' }}>
      <span style={{ color: '#9ca0aa', fontSize: '14px' }}>{label}</span>
      <span style={{ color: '#f8f8f2', fontSize: '14px', fontWeight: 600 }}>{value}</span>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function SuburbPage() {
  const { id: sa2Code = '' } = useParams<{ id: string }>()
  const [state, setState] = useState<PageState>({ status: 'loading' })

  useEffect(() => {
    if (!sa2Code) { setState({ status: 'error', message: 'Missing SA2 code.' }); return }
    setState({ status: 'loading' })
    let cancelled = false
    fetch(`/api/suburb/${encodeURIComponent(sa2Code)}`)
      .then(async r => {
        if (!r.ok) {
          const body = await r.json().catch(() => null)
          throw new Error(body?.detail || r.statusText)
        }
        return r.json() as Promise<SuburbReport>
      })
      .then(data => { if (!cancelled) setState({ status: 'ready', data }) })
      .catch(err => { if (!cancelled) setState({ status: 'error', message: err instanceof Error ? err.message : 'Unknown error' }) })
    return () => { cancelled = true }
  }, [sa2Code])

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '0 20px 60px' }}>
      <div style={{ marginBottom: '24px' }}>
        <Link to="/" style={{ color: '#9ca0aa', textDecoration: 'none', fontSize: '14px' }}>← Back to Search</Link>
      </div>

      {state.status === 'loading' && <p style={{ color: '#9ca0aa' }}>Loading {sa2Code}…</p>}
      {state.status === 'error' && (
        <div style={{ backgroundColor: '#3b2a2a', border: '1px solid #6b3b3b', borderRadius: '10px', padding: '24px', color: '#f8d7da' }}>
          <h2 style={{ marginTop: 0 }}>Could not load {sa2Code}</h2>
          <p style={{ margin: 0 }}>{state.message}</p>
        </div>
      )}
      {state.status === 'ready' && <ReadyView data={state.data} />}
    </div>
  )
}

function ReadyView({ data }: { data: SuburbReport }) {
  const { sa2_code, sa2_name, state: stateCode, scores, intermediates, facts, insight, risk_flags, tags } = data

  return (
    <>
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' }}>
          <h1 style={{ fontSize: '42px', margin: 0 }}>{sa2_name ?? sa2_code}</h1>
          <span style={{ color: '#9ca0aa', fontSize: '22px' }}>{stateCode}</span>
        </div>
        <p style={{ color: '#9ca0aa', margin: '6px 0 0', fontSize: '13px' }}>SA2 {sa2_code}</p>
        {tags.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
            {tags.map(t => (
              <span key={t} style={{ padding: '4px 12px', backgroundColor: '#2a3a4a', color: '#7ec8e3', borderRadius: '20px', fontSize: '12px', fontWeight: 600 }}>
                {t}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Composite score hero */}
      <div style={{ backgroundColor: '#1e2530', border: '1px solid #4b566a', borderRadius: '12px', padding: '28px 32px', marginBottom: '32px', display: 'flex', alignItems: 'center', gap: '32px' }}>
        <div>
          <div style={{ fontSize: '13px', color: '#9ca0aa', textTransform: 'uppercase', letterSpacing: '1px' }}>Investment Score</div>
          <div style={{ fontSize: '72px', fontWeight: 800, color: scoreColor(scores.investment_score), lineHeight: 1 }}>
            {fmt(scores.investment_score, 1)}
          </div>
          <div style={{ color: '#9ca0aa', fontSize: '13px' }}>out of 10</div>
        </div>
        <div style={{ flex: 1, color: '#d1d5da', fontSize: '16px', lineHeight: 1.7 }}>
          {insight}
        </div>
      </div>

      {/* Dimension scores grid */}
      <h2 style={{ fontSize: '22px', marginBottom: '16px' }}>Score Breakdown</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '16px', marginBottom: '40px' }}>
        <DimensionCard label="Liveability"     value={scores.liveability_score}    description="Amenity access, transit, healthcare, parks" />
        <DimensionCard label="Growth"          value={scores.growth_score}          description="Population growth, investment pipeline, gentrification" />
        <DimensionCard label="Education"       value={scores.education_score}       description="School quality, coverage of all levels" />
        <DimensionCard label="Demographics"    value={scores.demographic_score}     description="Income, SEIFA, workforce education" />
        <DimensionCard label="Housing Market"  value={scores.housing_score}         description="Mortgage/rent stress, dwelling character" />
        <DimensionCard label="Infrastructure"  value={scores.infrastructure_score}  description="Committed government investment pipeline" />
        <DimensionCard label="Gentrification"  value={scores.gentrification_index}  description="Composite social uplift signal" />
      </div>

      {/* Two-column detail */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '40px' }}>

        {/* Demographics */}
        <div style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '24px' }}>
          <h3 style={{ fontSize: '16px', marginBottom: '12px', marginTop: 0 }}>Demographics</h3>
          <FactRow label="Population" value={facts.population ? facts.population.toLocaleString() : '—'} />
          <FactRow label="Median income" value={facts.median_income ? `$${Math.round(facts.median_income).toLocaleString()}` : '—'} />
          <FactRow label="Median age" value={fmt(facts.median_age, 0)} />
          <FactRow label="Uni degree %" value={`${fmt(facts.uni_degree_pct, 1)}%`} />
          <FactRow label="Prof / managers %" value={`${fmt(facts.professionals_managers_pct, 1)}%`} />
          <FactRow label="Unemployment %" value={`${fmt(facts.unemployment_pct, 1)}%`} />
          <FactRow label="SEIFA disadvantage decile" value={`${facts.seifa_irsd_decile ?? '—'} / 10`} />
          <FactRow label="SEIFA education decile" value={`${facts.seifa_ieo_decile ?? '—'} / 10`} />
        </div>

        {/* Housing */}
        <div style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '24px' }}>
          <h3 style={{ fontSize: '16px', marginBottom: '12px', marginTop: 0 }}>Housing & Dwelling</h3>
          <FactRow label="Separate houses" value={`${fmt(facts.separate_house_pct, 1)}%`} />
          <FactRow label="Flats & apartments" value={`${fmt(facts.flat_apartment_pct, 1)}%`} />
          <FactRow label="High-rise (9+ storey)" value={`${fmt(facts.flat_high_rise_pct, 1)}%`} />
          <FactRow label="Renters" value={`${fmt(facts.renters_pct, 1)}%`} />
          <FactRow label="Mortgage stress" value={`${fmt(facts.high_mortgage_stress_pct, 1)}%`} />
          <FactRow label="Building approvals (1yr)" value={facts.building_approvals_1yr?.toLocaleString() ?? '—'} />
          <FactRow label="Pop. growth to 2031" value={`${fmt(facts.pop_growth_proj_pct, 1)}%`} />
        </div>

        {/* Education */}
        <div style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '24px' }}>
          <h3 style={{ fontSize: '16px', marginBottom: '12px', marginTop: 0 }}>Education</h3>
          <FactRow label="Avg school ICSEA nearby" value={fmt(intermediates.edu_avg_icsea, 0)} />
          <FactRow label="Top schools (ICSEA ≥ 1100)" value={intermediates.edu_top_school_count ?? '—'} />
          <FactRow label="Secondary schools nearby" value={intermediates.edu_secondary_count ?? '—'} />
          <FactRow label="University / TAFE nearby" value={intermediates.edu_tertiary_count ?? '—'} />
        </div>

        {/* Infrastructure & Health */}
        <div style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '24px' }}>
          <h3 style={{ fontSize: '16px', marginBottom: '12px', marginTop: 0 }}>Infrastructure & Health</h3>
          <FactRow label="Committed govt investment" value={fmtAUD(intermediates.infra_committed_aud)} />
          <FactRow label="Active projects linked" value={intermediates.infra_project_count ?? '—'} />
          <FactRow label="Transit score" value={fmt(intermediates.transit_score_raw, 0)} />
          <FactRow label="Train stops nearby" value={facts.pt_stop_train ?? '—'} />
          <FactRow label="Bus stops nearby" value={facts.pt_stop_bus ?? '—'} />
          <FactRow label="Public hospital score" value={fmt(intermediates.health_hospital_score, 1)} />
          <FactRow label="GP clinics nearby" value={intermediates.health_gp_count ?? '—'} />
          <FactRow label="Cafes nearby" value={facts.osm_cafes ?? '—'} />
        </div>
      </div>

      {/* Risk flags */}
      {risk_flags.length > 0 && (
        <div style={{ marginBottom: '40px' }}>
          <h3 style={{ fontSize: '18px', marginBottom: '12px' }}>⚠️ Risk Flags</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            {risk_flags.map(flag => (
              <span key={flag} style={{ padding: '8px 16px', backgroundColor: '#4a3030', color: '#e07070', borderRadius: '6px', fontSize: '13px' }}>
                {flag.replace(/_/g, ' ')}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Paywall */}
      <div style={{ marginTop: '48px', textAlign: 'center', backgroundColor: '#1e2530', border: '1px solid #4b566a', padding: '48px', borderRadius: '12px' }}>
        <h2 style={{ fontSize: '28px', marginBottom: '12px' }}>Unlock Full Report</h2>
        <p style={{ fontSize: '16px', color: '#9ca0aa', marginBottom: '28px', maxWidth: '480px', margin: '0 auto 28px' }}>
          Get suburb-vs-suburb comparisons, historical trend analysis, school catchment maps, and PDF export.
        </p>
        <button style={{ padding: '16px 48px', fontSize: '18px', fontWeight: 700, backgroundColor: '#e74c3c', color: 'white', border: 'none', borderRadius: '8px', cursor: 'pointer' }}>
          Unlock for $9
        </button>
      </div>
    </>
  )
}
