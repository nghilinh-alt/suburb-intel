import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import GaugeBar from '../components/GaugeBar'
import SectionPanel from '../components/SectionPanel'
import SeverityBadge from '../components/SeverityBadge'
import { usePageTitle } from '../hooks/usePageTitle'

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
  if (v == null) return '#6b7fa0'
  if (v >= 7) return '#34d399'
  if (v >= 5) return '#fbbf24'
  return '#fb7185'
}


function scoreBadgeLevel(v: number | null): 'good' | 'warn' | 'bad' | 'info' {
  if (v == null) return 'info'
  if (v >= 6.5)  return 'good'
  if (v >= 5)    return 'warn'
  return 'bad'
}

// ── Sub-components ─────────────────────────────────────────────────────────

function DimensionCard({ label, value, description }: { label: string; value: number | null; description: string }) {
  return (
    <div style={{
      backgroundColor: '#151b27', border: '1px solid #28334a',
      borderRadius: '12px', padding: '20px',
      display: 'flex', flexDirection: 'column', gap: '10px',
      boxShadow: '0 2px 12px rgba(0,0,0,0.45)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <span style={{ fontSize: '12px', fontWeight: 500, color: '#6b7fa0', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          {label}
        </span>
        <SeverityBadge level={scoreBadgeLevel(value)} label={value != null ? value.toFixed(1) : '—'} />
      </div>
      <GaugeBar value={value ?? 0} max={10} showValue={false} height={6} />
      <span style={{ fontSize: '12px', color: '#6b7fa0' }}>{description}</span>
    </div>
  )
}

function FactRow({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 0', borderBottom: '1px solid #1e2638' }}>
      <span style={{ color: '#6b7fa0', fontSize: '14px' }}>{label}</span>
      <span style={{ color: '#cdd8e8', fontSize: '14px', fontWeight: 600 }}>{value}</span>
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
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '0 0 80px' }}>
      <div style={{ marginBottom: '24px' }}>
        <Link to="/" style={{ color: '#6b7fa0', textDecoration: 'none', fontSize: '14px' }}>← Back to Search</Link>
      </div>

      {state.status === 'loading' && <p style={{ color: '#6b7fa0' }}>Loading {sa2Code}…</p>}
      {state.status === 'error' && (
        <div style={{ backgroundColor: 'rgba(251,113,133,0.08)', border: '1px solid rgba(251,113,133,0.25)', borderRadius: '12px', padding: '24px', color: '#fb7185' }}>
          <h2 style={{ marginTop: 0, color: '#fda4af' }}>Could not load {sa2Code}</h2>
          <p style={{ margin: 0 }}>{state.message}</p>
        </div>
      )}
      {state.status === 'ready' && <ReadyView data={state.data} />}
    </div>
  )
}

function ReadyView({ data }: { data: SuburbReport }) {
  const { sa2_code, sa2_name, state: stateCode, scores, intermediates, facts, insight, risk_flags, tags } = data
  const inv = scores.investment_score
  usePageTitle(sa2_name ?? sa2_code)

  return (
    <>
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' }}>
          <h1 style={{ fontSize: '40px', fontWeight: 800, margin: 0, color: '#cdd8e8', letterSpacing: '-0.03em' }}>
            {sa2_name ?? sa2_code}
          </h1>
          <span style={{ color: '#6b7fa0', fontSize: '22px' }}>{stateCode}</span>
        </div>
        <p style={{ color: '#6b7fa0', margin: '6px 0 0', fontSize: '13px' }}>SA2 {sa2_code}</p>
        {tags.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
            {tags.map(t => (
              <span key={t} style={{
                padding: '4px 12px', backgroundColor: 'rgba(45,212,191,0.1)',
                color: '#2dd4bf', borderRadius: '99px', fontSize: '12px', fontWeight: 600,
                border: '1px solid rgba(45,212,191,0.2)',
              }}>
                {t}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Investment score hero */}
      <div style={{
        backgroundColor: '#151b27', border: '1px solid #28334a',
        borderRadius: '16px', padding: '32px',
        marginBottom: '32px',
        display: 'flex', alignItems: 'flex-start', gap: '40px', flexWrap: 'wrap',
        boxShadow: '0 2px 12px rgba(0,0,0,0.45)',
      }}>
        <div style={{ minWidth: '140px' }}>
          <div style={{ fontSize: '12px', fontWeight: 500, color: '#6b7fa0', textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '4px' }}>
            Investment Score
          </div>
          <div style={{ fontSize: '76px', fontWeight: 800, color: scoreColor(inv), lineHeight: 1, letterSpacing: '-0.04em' }}>
            {fmt(inv, 1)}
          </div>
          <div style={{ marginTop: '8px' }}>
            <GaugeBar value={inv ?? 0} max={10} showValue={false} height={6} />
          </div>
          <div style={{ color: '#6b7fa0', fontSize: '12px', marginTop: '6px' }}>out of 10</div>
        </div>
        <div style={{ flex: 1, minWidth: '240px', color: '#9aafc8', fontSize: '16px', lineHeight: 1.75, paddingTop: '4px' }}>
          {insight}
        </div>
      </div>

      {/* Dimension score grid */}
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '16px', color: '#cdd8e8', letterSpacing: '-0.01em' }}>
        Score Breakdown
      </h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '14px', marginBottom: '40px' }}>
        <DimensionCard label="Liveability"     value={scores.liveability_score}    description="Amenity access, transit, healthcare, parks" />
        <DimensionCard label="Growth"          value={scores.growth_score}          description="Population growth, investment pipeline, gentrification" />
        <DimensionCard label="Education"       value={scores.education_score}       description="School quality, coverage of all levels" />
        <DimensionCard label="Demographics"    value={scores.demographic_score}     description="Income, SEIFA, workforce education" />
        <DimensionCard label="Housing Market"  value={scores.housing_score}         description="Mortgage/rent stress, dwelling character" />
        <DimensionCard label="Infrastructure"  value={scores.infrastructure_score}  description="Committed government investment pipeline" />
        <DimensionCard label="Gentrification"  value={scores.gentrification_index}  description="Composite social uplift signal" />
      </div>

      {/* Two-column fact panels */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: '20px', marginBottom: '40px' }}>
        <SectionPanel title="Demographics">
          <FactRow label="Population"               value={facts.population ? facts.population.toLocaleString() : '—'} />
          <FactRow label="Median income"            value={facts.median_income ? `$${Math.round(facts.median_income).toLocaleString()}` : '—'} />
          <FactRow label="Median age"               value={fmt(facts.median_age, 0)} />
          <FactRow label="Uni degree"               value={`${fmt(facts.uni_degree_pct, 1)}%`} />
          <FactRow label="Professionals / managers" value={`${fmt(facts.professionals_managers_pct, 1)}%`} />
          <FactRow label="Unemployment"             value={`${fmt(facts.unemployment_pct, 1)}%`} />
          <FactRow label="SEIFA disadvantage decile" value={`${facts.seifa_irsd_decile ?? '—'} / 10`} />
          <FactRow label="SEIFA education decile"   value={`${facts.seifa_ieo_decile ?? '—'} / 10`} />
        </SectionPanel>

        <SectionPanel title="Housing & Dwelling">
          <FactRow label="Separate houses"          value={`${fmt(facts.separate_house_pct, 1)}%`} />
          <FactRow label="Flats & apartments"       value={`${fmt(facts.flat_apartment_pct, 1)}%`} />
          <FactRow label="High-rise (9+ storey)"    value={`${fmt(facts.flat_high_rise_pct, 1)}%`} />
          <FactRow label="Renters"                  value={`${fmt(facts.renters_pct, 1)}%`} />
          <FactRow label="Mortgage stress"          value={`${fmt(facts.high_mortgage_stress_pct, 1)}%`} />
          <FactRow label="Building approvals (1yr)" value={facts.building_approvals_1yr?.toLocaleString() ?? '—'} />
          <FactRow label="Pop. growth to 2031"      value={`${fmt(facts.pop_growth_proj_pct, 1)}%`} />
        </SectionPanel>

        <SectionPanel title="Education">
          <FactRow label="Avg school ICSEA nearby"   value={fmt(intermediates.edu_avg_icsea, 0)} />
          <FactRow label="Top schools (ICSEA ≥ 1100)" value={intermediates.edu_top_school_count ?? '—'} />
          <FactRow label="Secondary schools nearby"  value={intermediates.edu_secondary_count ?? '—'} />
          <FactRow label="University / TAFE nearby"  value={intermediates.edu_tertiary_count ?? '—'} />
        </SectionPanel>

        <SectionPanel title="Infrastructure & Health">
          <FactRow label="Committed govt investment" value={fmtAUD(intermediates.infra_committed_aud)} />
          <FactRow label="Active projects linked"    value={intermediates.infra_project_count ?? '—'} />
          <FactRow label="Transit score"             value={fmt(intermediates.transit_score_raw, 0)} />
          <FactRow label="Train stops nearby"        value={facts.pt_stop_train ?? '—'} />
          <FactRow label="Bus stops nearby"          value={facts.pt_stop_bus ?? '—'} />
          <FactRow label="Public hospital score"     value={fmt(intermediates.health_hospital_score, 1)} />
          <FactRow label="GP clinics nearby"         value={intermediates.health_gp_count ?? '—'} />
          <FactRow label="Cafes nearby"              value={facts.osm_cafes ?? '—'} />
        </SectionPanel>
      </div>

      {/* Risk flags */}
      {risk_flags.length > 0 && (
        <div style={{ marginBottom: '40px' }}>
          <h3 style={{ fontSize: '17px', fontWeight: 700, marginBottom: '12px', color: '#cdd8e8' }}>Risk Flags</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {risk_flags.map(flag => (
              <SeverityBadge key={flag} level="bad" label={flag.replace(/_/g, ' ')} />
            ))}
          </div>
        </div>
      )}
    </>
  )
}
