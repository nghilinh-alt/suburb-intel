import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import SectionPanel from '../components/SectionPanel'
import SeverityBadge from '../components/SeverityBadge'
import GaugeBar from '../components/GaugeBar'
import MetricBlock from '../components/MetricBlock'
import TrendSparkline from '../components/TrendSparkline'
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

interface SchoolEntry {
  name: string
  sector: string | null
  school_type: string | null
  icsea: number | null
  icsea_percentile: number | null
  rating: string | null
  in_suburb: boolean
  total_enrolments: number | null
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

interface Rank {
  national_rank: number
  national_total: number
  national_pct: number
  state_rank: number
  state_total: number
}

interface PeerSuburb {
  suburb_id: string
  suburb_name: string
  state: string
  population: number | null
  investment_score: number | null
  liveability_score: number | null
  growth_score: number | null
  education_score: number | null
}

interface MarketData {
  house_median_price: number | null
  unit_median_price: number | null
  house_weekly_rent: number | null
  unit_weekly_rent: number | null
  house_gross_yield_pct: number | null
  unit_gross_yield_pct: number | null
  house_1y_growth_pct: number | null
  unit_1y_growth_pct: number | null
  house_3y_growth_pct: number | null
  unit_3y_growth_pct: number | null
  house_5y_growth_pct: number | null
  unit_5y_growth_pct: number | null
  house_growth_confidence: string | null
  house_days_on_market: number | null
  unit_days_on_market: number | null
  vacancy_rate_pct: number | null
  house_sales_12mo: number | null
  unit_sales_12mo: number | null
  house_heat_score: number | null
  sold_vs_asking_pct: number | null
  as_of: string | null
}

interface CommuteTimes {
  drive_offpeak_min: number | null
  drive_peak_min: number | null
  pt_min: number
  pt_mode: string
  road_distance_km: number
  note: string
}

interface UniEntry {
  name: string
  school_type: string
  dist_km: number
  in_suburb: boolean
}

interface HospitalEntry {
  name: string
  type: string
  dist_km: number
  in_suburb: boolean
  impact_score: number
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
  schools_in_suburb: SchoolEntry[]
  schools_adjacent: SchoolEntry[]
  universities_nearby: UniEntry[]
  hospitals_nearby: HospitalEntry[]
  shopping_nearby: Array<{ name: string; dist_km: number; in_suburb: boolean }>
  shopping_nearby_count: number | null
  adjacent_has_train: boolean
  adjacent_train_suburbs: string[]
  cbd_distance_km: number | null
  cbd_city: string | null
  population_density: number | null
  parks_per_km2: number | null
  market_data: MarketData | null
  commute_times: CommuteTimes | null
  rank: Rank
  peer_suburbs: PeerSuburb[]
  risk_flags: string[]
  tags: string[]
  insight: string
  note: string | null
}

type PageState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: GroupReport }

// ── Helpers ────────────────────────────────────────────────────────────────

const fv = (v: number | null | undefined, dp = 1, sfx = '') =>
  v != null && !isNaN(v) ? `${v.toFixed(dp)}${sfx}` : '—'

const fAUD = (v: number | null) => {
  if (!v) return null
  if (v >= 1e9) return `$${(v / 1e9).toFixed(1)}B`
  if (v >= 1e6) return `$${(v / 1e6).toFixed(0)}M`
  return `$${Math.round(v).toLocaleString()}`
}

function scoreColor(v: number | null) {
  if (v == null) return '#6b7fa0'
  if (v >= 7) return '#34d399'
  if (v >= 5) return '#fbbf24'
  return '#fb7185'
}

function signalLevel(score: number | null): { level: 'good' | 'warn' | 'bad' | 'info'; label: string } {
  if (score == null) return { level: 'info',  label: 'No data' }
  if (score >= 7.5)  return { level: 'good',  label: '✓ Strong signal' }
  if (score >= 6.0)  return { level: 'good',  label: '↗ Positive' }
  if (score >= 5.0)  return { level: 'warn',  label: '→ Neutral' }
  if (score >= 3.5)  return { level: 'warn',  label: '↘ Caution' }
  return                    { level: 'bad',   label: '✗ Risk factor' }
}

// ── Components ─────────────────────────────────────────────────────────────

function scoreToTopPct(v: number | null): string | null {
  // Scores are built from national percentile ranks → score × 10 ≈ national percentile
  // e.g. score 7.5 → ~75th pct → "Top 25%"
  if (v == null) return null
  const top = Math.round((1 - v / 10) * 100)
  return top <= 1 ? 'Top 1%' : `Top ${top}%`
}

function ScoreCard({ label, value, desc }: { label: string; value: number | null; desc: string }) {
  const { level } = signalLevel(value)
  const topPct = scoreToTopPct(value)
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
        <SeverityBadge level={level} label={value != null ? value.toFixed(1) : '—'} />
      </div>
      <GaugeBar value={value ?? 0} max={10} showValue={false} height={6} />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <p style={{ color: '#6b7fa0', fontSize: '12px', margin: 0 }}>{desc}</p>
        {topPct && (
          <span style={{
            fontSize: '11px', color: value != null && value >= 7 ? '#34d399' : value != null && value >= 5 ? '#fbbf24' : '#fb7185',
            fontWeight: 600, whiteSpace: 'nowrap', marginLeft: '8px',
          }}>
            {topPct}
          </span>
        )}
      </div>
    </div>
  )
}

function IntelPanel({ emoji, label, score, children, sa2Breakdown, dimKey, isMulti }: {
  emoji: string; label: string; score: number | null
  children: React.ReactNode
  sa2Breakdown: SA2Entry[]; dimKey: string; isMulti: boolean
}) {
  const { level, label: sigLabel } = signalLevel(score)
  return (
    <SectionPanel
      title={`${emoji} ${label}`}
      action={<SeverityBadge level={level} label={score != null ? `${score.toFixed(1)}/10 · ${sigLabel}` : 'No data'} />}
    >
      {/* Per-area comparison (multi-SA2 only) */}
      {isMulti && sa2Breakdown.length > 1 && (
        <div style={{ backgroundColor: '#0d1117', borderRadius: '8px', padding: '14px 16px', marginBottom: '18px' }}>
          <div style={{ fontSize: '11px', color: '#6b7fa0', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.07em' }}>By area</div>
          {sa2Breakdown.map(sa2 => {
            const v = sa2.scores[dimKey as keyof Scores]
            const shortName = sa2.sa2_name.replace(/^.+ - /, '')
            return (
              <div key={sa2.sa2_code} style={{ marginBottom: '12px' }}>
                <GaugeBar
                  value={v ?? 0}
                  max={10}
                  label={`${shortName}${sa2.population ? ` · ${sa2.population.toLocaleString()}` : ''}`}
                />
              </div>
            )
          })}
        </div>
      )}

      {children}
    </SectionPanel>
  )
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ display: 'inline-block', padding: '5px 12px', backgroundColor: '#1e2638', color: '#9aafc8', borderRadius: '6px', fontSize: '13px', margin: '3px 6px 3px 0', border: '1px solid #28334a' }}>
      {children}
    </span>
  )
}

function Analysis({ children }: { children: React.ReactNode }) {
  return <p style={{ color: '#9aafc8', fontSize: '15px', lineHeight: 1.75, margin: '0 0 14px' }}>{children}</p>
}

// ── Intelligence sections ──────────────────────────────────────────────────

function LiveabilitySection({ score, facts, adjacentHasTrain, adjacentTrainSuburbs, universitiesNearby, hospitalsNearby, shoppingNearby, commuteTimes, cbdCity }: {
  score: number | null
  facts: Record<string, number | null>
  adjacentHasTrain: boolean
  adjacentTrainSuburbs: string[]
  universitiesNearby: UniEntry[]
  hospitalsNearby: HospitalEntry[]
  shoppingNearby: Array<{ name: string; dist_km: number; in_suburb: boolean }>
  commuteTimes: CommuteTimes | null
  cbdCity: string | null
}) {
  const hasTrain = (facts.pt_stop_train ?? 0) > 0
  const hasBizData = facts.biz_food_services != null

  let analysis = ''
  if ((score ?? 0) >= 7.5) {
    analysis = 'High liveability areas command rental premiums and attract quality long-term tenants. Dense café culture, walkability, and good transit access pull in professional renters who pay above-market rents and stay longer.'
  } else if ((score ?? 0) >= 5.5) {
    analysis = 'Moderate liveability — the suburb has the essentials for comfortable daily life but lacks the walkable density that draws young professionals. Expect steady family-oriented tenant demand.'
  } else {
    analysis = 'Low liveability is a rental risk. Limited walkable amenity and transit access reduces the renter pool. As tenant preferences continue shifting toward walkability, car-dependent suburbs face increasing headwinds. Strong purchase price discipline is essential.'
  }

  return (
    <>
      <Analysis>{analysis}</Analysis>

      {/* ABS Business Register counts */}
      {hasBizData && (
        <div style={{ backgroundColor: '#1e2638', borderRadius: '8px', padding: '16px', marginBottom: '14px' }}>
          <div style={{ fontSize: '12px', color: '#6b7fa0', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '1px' }}>
            Registered Businesses <span style={{ fontSize: '10px', color: '#28334a', textTransform: 'none' }}>(ABS Business Register, June 2025)</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '8px' }}>
            {[
              { label: 'Food & Beverage', value: facts.biz_food_services, icon: '🍽️', note: 'cafes, restaurants, takeaway' },
              { label: 'Health & Medical', value: facts.biz_health_social, icon: '🏥', note: 'GPs, pharmacies, allied health' },
              { label: 'Retail', value: facts.biz_retail_trade, icon: '🛍️', note: 'shops of all types' },
              { label: 'Arts & Recreation', value: facts.biz_arts_recreation, icon: '🏋️', note: 'gyms, sport, entertainment' },
              { label: 'Other Services', value: facts.biz_other_services, icon: '🔧', note: 'mechanics, hair, laundry' },
            ].map(({ label, value, icon, note }) => value != null && value > 0 ? (
              <div key={label} style={{ backgroundColor: '#151b27', borderRadius: '6px', padding: '10px 12px' }}>
                <div style={{ fontSize: '18px', marginBottom: '2px' }}>{icon} <span style={{ fontSize: '20px', fontWeight: 700, color: '#cdd8e8' }}>{value}</span></div>
                <div style={{ fontSize: '12px', color: '#9aafc8', fontWeight: 500 }}>{label}</div>
                <div style={{ fontSize: '11px', color: '#6b7fa0' }}>{note}</div>
              </div>
            ) : null)}
          </div>
          {facts.biz_total != null && (
            <div style={{ marginTop: '10px', fontSize: '11px', color: '#28334a' }}>
              {facts.biz_total.toLocaleString()} total registered businesses (includes construction, professional services, finance etc.)
            </div>
          )}
        </div>
      )}

      {/* Key Nearby Facilities */}
      {(universitiesNearby.length > 0 || hospitalsNearby.length > 0 || shoppingNearby.length > 0) && (
        <div style={{ backgroundColor: '#1e2638', borderRadius: '8px', padding: '16px', marginBottom: '14px' }}>
          <div style={{ fontSize: '12px', color: '#6b7fa0', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>
            Key Nearby Facilities
          </div>

          {/* Universities / TAFE */}
          {universitiesNearby.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <div style={{ fontSize: '12px', color: '#38bdf8', marginBottom: '6px', fontWeight: 600 }}>🎓 University / TAFE</div>
              {universitiesNearby.map((u, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #3a4050' }}>
                  <span style={{ color: '#9aafc8', fontSize: '13px' }}>{u.name}</span>
                  <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px',
                    backgroundColor: u.in_suburb ? 'rgba(52,211,153,0.1)' : '#151b27',
                    color: u.in_suburb ? '#34d399' : '#6b7fa0' }}>
                    {u.in_suburb ? 'In suburb' : `${u.dist_km}km away`}
                  </span>
                </div>
              ))}
              <div style={{ fontSize: '11px', color: '#28334a', marginTop: '4px', fontStyle: 'italic' }}>
                Access to university/TAFE expands the renter pool to students and academics — positive for rental demand.
              </div>
            </div>
          )}

          {/* Hospitals */}
          {hospitalsNearby.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <div style={{ fontSize: '12px', color: '#fb7185', marginBottom: '6px', fontWeight: 600 }}>🏥 Hospitals</div>
              {hospitalsNearby.slice(0, 6).map((h, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #3a4050' }}>
                  <span style={{ color: '#9aafc8', fontSize: '13px' }}>{h.name}</span>
                  <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px',
                    backgroundColor: h.dist_km <= 3 ? 'rgba(251,113,133,0.1)' : '#151b27',
                    color: h.dist_km <= 3 ? '#fb7185' : '#6b7fa0' }}>
                    {h.type} · {h.dist_km <= 1 ? 'In suburb' : `${h.dist_km}km`}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Major shopping — named centres from OSM */}
          {shoppingNearby.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <div style={{ fontSize: '12px', color: '#fbbf24', marginBottom: '6px', fontWeight: 600 }}>🛍️ Shopping Centres</div>
              {shoppingNearby.slice(0, 6).map((s, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid #3a4050' }}>
                  <span style={{ color: '#9aafc8', fontSize: '13px' }}>{s.name}</span>
                  <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px',
                    backgroundColor: s.in_suburb ? 'rgba(251,191,36,0.08)' : '#151b27',
                    color: s.in_suburb ? '#fbbf24' : '#6b7fa0' }}>
                    {s.in_suburb ? 'In suburb' : `${s.dist_km}km`}
                  </span>
                </div>
              ))}
              <div style={{ fontSize: '11px', color: '#28334a', marginTop: '6px' }}>
                Named shopping centres sourced from OpenStreetMap
              </div>
            </div>
          )}
        </div>
      )}

      {/* Commute to CBD — standalone section */}
      {commuteTimes && cbdCity && (
        <div style={{ backgroundColor: '#1e2638', borderRadius: '8px', padding: '16px', marginBottom: '14px' }}>
          <div style={{ fontSize: '12px', color: '#6b7fa0', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>
            🏙️ Commute to {cbdCity} CBD
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '8px' }}>
            {/* Drive off-peak */}
            <div style={{ backgroundColor: '#151b27', borderRadius: '6px', padding: '10px 12px' }}>
              <div style={{ fontSize: '11px', color: '#6b7fa0', marginBottom: '4px' }}>🚗 Drive off-peak</div>
              <div style={{ color: '#cdd8e8', fontSize: '20px', fontWeight: 700, lineHeight: 1 }}>
                {commuteTimes.drive_offpeak_min}<span style={{ fontSize: '12px', fontWeight: 400, color: '#6b7fa0' }}> min</span>
              </div>
              <div style={{ fontSize: '11px', color: '#28334a', marginTop: '3px' }}>{commuteTimes.road_distance_km}km by road</div>
            </div>
            {/* Drive peak */}
            <div style={{ backgroundColor: '#151b27', borderRadius: '6px', padding: '10px 12px' }}>
              <div style={{ fontSize: '11px', color: '#6b7fa0', marginBottom: '4px' }}>🚗 Drive peak hour</div>
              <div style={{ color: '#fbbf24', fontSize: '20px', fontWeight: 700, lineHeight: 1 }}>
                {commuteTimes.drive_peak_min}<span style={{ fontSize: '12px', fontWeight: 400, color: '#6b7fa0' }}> min</span>
              </div>
              <div style={{ fontSize: '11px', color: '#28334a', marginTop: '3px' }}>incl. congestion</div>
            </div>
            {/* PT */}
            <div style={{ backgroundColor: '#151b27', borderRadius: '6px', padding: '10px 12px' }}>
              <div style={{ fontSize: '11px', color: '#6b7fa0', marginBottom: '4px' }}>
                {commuteTimes.pt_mode === 'ferry' ? '⛴️ By Ferry' :
                 commuteTimes.pt_mode === 'train' ? '🚆 By Train' :
                 commuteTimes.pt_mode === 'tram'  ? '🚊 By Tram'  : '🚌 By Bus'}
              </div>
              <div style={{ color: '#38bdf8', fontSize: '20px', fontWeight: 700, lineHeight: 1 }}>
                ~{commuteTimes.pt_min}<span style={{ fontSize: '12px', fontWeight: 400, color: '#6b7fa0' }}> min</span>
              </div>
              <div style={{ fontSize: '11px', color: '#28334a', marginTop: '3px' }}>
                {commuteTimes.pt_mode === 'ferry' ? 'CityCat / ferry' :
                 commuteTimes.pt_mode === 'train' ? 'Via rail' :
                 commuteTimes.pt_mode === 'tram'  ? 'Via tram' : 'May need transfer'}
              </div>
            </div>
          </div>
          <div style={{ fontSize: '11px', color: '#28334a', marginTop: '10px', fontStyle: 'italic' }}>
            Driving: OSRM road network (free-flow off-peak, estimated peak congestion). PT: estimate from distance and transit modes available — actual times vary.
          </div>
        </div>
      )}

      {/* Public transport stops */}
      <div style={{ backgroundColor: '#1e2638', borderRadius: '8px', padding: '16px', marginBottom: '14px' }}>
        <div style={{ fontSize: '12px', color: '#6b7fa0', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>Public Transport</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>

          {/* Train */}
          <div style={{ padding: '8px 10px', borderRadius: '6px', backgroundColor: hasTrain ? 'rgba(52,211,153,0.1)' : '#151b27' }}>
            <div style={{ fontSize: '18px', marginBottom: '2px' }}>🚆</div>
            {hasTrain ? (
              <div style={{ color: '#34d399', fontSize: '13px', fontWeight: 600 }}>
                {facts.pt_stop_train} train stop{(facts.pt_stop_train ?? 0) > 1 ? 's' : ''}
              </div>
            ) : adjacentHasTrain ? (
              <div>
                <div style={{ color: '#fbbf24', fontSize: '13px', fontWeight: 600 }}>Train nearby</div>
                <div style={{ color: '#6b7fa0', fontSize: '11px' }}>{adjacentTrainSuburbs.slice(0,1).join(', ')}</div>
              </div>
            ) : (
              <div style={{ color: '#28334a', fontSize: '13px' }}>No train access</div>
            )}
          </div>

          {/* Ferry — only show if present */}
          {(facts.pt_stop_ferry ?? 0) > 0 && (
            <div style={{ padding: '8px 10px', borderRadius: '6px', backgroundColor: 'rgba(56,189,248,0.1)' }}>
              <div style={{ fontSize: '18px', marginBottom: '2px' }}>⛴️</div>
              <div style={{ color: '#38bdf8', fontSize: '13px', fontWeight: 600 }}>
                {facts.pt_stop_ferry} ferry stop{(facts.pt_stop_ferry ?? 0) > 1 ? 's' : ''}
              </div>
              <div style={{ color: '#6b7fa0', fontSize: '11px' }}>CityCat / ferry service</div>
            </div>
          )}

          {/* Tram (only show if present — Brisbane has none) */}
          {(facts.pt_stop_tram ?? 0) > 0 && (
            <div style={{ padding: '8px 10px', borderRadius: '6px', backgroundColor: 'rgba(45,212,191,0.1)' }}>
              <div style={{ fontSize: '18px', marginBottom: '2px' }}>🚊</div>
              <div style={{ color: '#34d399', fontSize: '13px', fontWeight: 600 }}>
                {facts.pt_stop_tram} tram stop{(facts.pt_stop_tram ?? 0) > 1 ? 's' : ''}
              </div>
            </div>
          )}

          {/* Bus */}
          <div style={{ padding: '8px 10px', borderRadius: '6px', backgroundColor: (facts.pt_stop_bus ?? 0) > 10 ? 'rgba(251,191,36,0.08)' : '#151b27' }}>
            <div style={{ fontSize: '18px', marginBottom: '2px' }}>🚌</div>
            {(facts.pt_stop_bus ?? 0) > 0 ? (
              <div style={{ color: (facts.pt_stop_bus ?? 0) > 20 ? '#fbbf24' : '#6b7fa0', fontSize: '13px', fontWeight: 600 }}>
                {facts.pt_stop_bus} bus stops
              </div>
            ) : (
              <div style={{ color: '#28334a', fontSize: '13px' }}>No bus stops</div>
            )}
            <div style={{ color: '#28334a', fontSize: '11px' }}>Route count coming soon</div>
          </div>

        </div>
      </div>
    </>
  )
}

function GrowthSection({ score, facts, intermediates }: {
  score: number | null
  facts: Record<string, number | null>
  intermediates: Record<string, number | null>
}) {
  const popGrowth  = facts.pop_growth_proj_pct
  const approvals  = facts.building_approvals_1yr
  const projCount  = intermediates.infra_project_count
  const projAUD    = intermediates.infra_committed_aud

  let analysis = ''
  if ((score ?? 0) >= 7.5) {
    analysis = 'Exceptional growth profile. Population demand, active development, and committed government investment create the conditions for sustained capital appreciation — this is where the infrastructure-led growth effect plays out.'
  } else if ((score ?? 0) >= 5.5) {
    analysis = `Moderate growth trajectory. ${popGrowth != null ? `ABS projects ${popGrowth.toFixed(1)}% population growth to 2031, sustaining underlying demand. ` : ''}${projCount ? `${projCount} active government project${projCount > 1 ? 's' : ''} nearby provide some infrastructure tailwind. ` : ''}Organic demand growth rather than investment-led uplift.`
  } else {
    analysis = `Modest growth outlook. ${popGrowth != null && popGrowth < 5 ? `Sub-5% projected population growth to 2031 signals limited demand pressure. ` : ''}Capital appreciation will largely track the broader market. Focus on yield over growth here.`
  }

  return (
    <>
      <Analysis>{analysis}</Analysis>
      <div style={{ display: 'flex', flexWrap: 'wrap' }}>
        {popGrowth != null && <Bullet>{popGrowth.toFixed(1)}% projected population growth to 2031 (ABS)</Bullet>}
        {approvals != null && <Bullet>{approvals} new dwelling approvals (last financial year)</Bullet>}
        {projAUD && <Bullet>{fAUD(projAUD)} committed government investment nearby</Bullet>}
        {projCount != null && projCount > 0 && <Bullet>{projCount} active infrastructure project{projCount > 1 ? 's' : ''}</Bullet>}
      </div>
    </>
  )
}

function EducationSection({ score, schoolsIn, schoolsAdj }: {
  score: number | null
  schoolsIn: SchoolEntry[]
  schoolsAdj: SchoolEntry[]
}) {
  // ── Key rule: Government schools have STRICT zones ───────────────────────
  // Algester residents cannot automatically attend Sunnybank Hills State School
  // just because it's in an adjacent SA2. Government school zones are precise —
  // they follow street boundaries, not SA2 lines.
  //
  // Catholic & Independent schools have NO strict zones (open enrolment).
  // Anyone can apply regardless of address.
  //
  // Investment commentary should only positively reference:
  //   - ALL schools that are IN the suburb (impact=1.0), any sector
  //   - Adjacent NON-GOVERNMENT schools (Catholic/Independent) — accessible to all
  //   - Adjacent GOVERNMENT schools: listed in the table but NOT named in investment analysis

  const nonGovAdj           = schoolsAdj.filter(s => s.sector !== 'Government')

  // Schools we can claim are investment-relevant (accessible without zone restriction)
  const accessibleSchools   = [...schoolsIn, ...nonGovAdj]

  const top5Accessible  = accessibleSchools.filter(s => s.icsea_percentile != null && s.icsea_percentile >= 95)
  const top10Accessible = accessibleSchools.filter(s => s.icsea_percentile != null && s.icsea_percentile >= 90 && s.icsea_percentile < 95)
  const top15Accessible = accessibleSchools.filter(s => s.icsea_percentile != null && s.icsea_percentile >= 85 && s.icsea_percentile < 90)
  const top25Accessible = accessibleSchools.filter(s => s.icsea_percentile != null && s.icsea_percentile >= 75)

  let analysis = ''

  if (top5Accessible.length > 0) {
    const s = top5Accessible[0]
    const loc = schoolsIn.includes(s) ? 'in this suburb' : 'nearby (Catholic/Independent, open enrolment)'
    analysis = `Elite school catchment — ${s.name} ranks in the Top 5% of all Australian schools (ICSEA ${s.icsea?.toFixed(0)}), ${loc}. This is a powerful and durable property value driver. Families commit to long-term home ownership to secure access to schools at this level, producing sustained demand and price resilience that outperforms the broader market.`
  } else if (top10Accessible.length > 0) {
    const s = top10Accessible[0]
    const loc = schoolsIn.includes(s) ? 'in this suburb' : 'nearby'
    analysis = `Strong school catchment — ${s.name} (Top 10% nationally, ICSEA ${s.icsea?.toFixed(0)}) is ${loc}. Quality school access reliably attracts family buyers willing to pay above-market prices to secure enrolment. Properties within the school's catchment zone typically trade at a measurable premium.`
  } else if (top15Accessible.length > 0) {
    const s = top15Accessible[0]
    const loc = schoolsIn.includes(s) ? 'in this suburb' : 'nearby'
    analysis = `Above-average school access — ${s.name} (Top 15%, ICSEA ${s.icsea?.toFixed(0)}) is ${loc}. This is a genuine investment differentiator for family buyers who make long-term residential decisions based on school access.`
  } else if (top25Accessible.length > 0) {
    const inCount = top25Accessible.filter(s => schoolsIn.includes(s)).length
    if (inCount > 0) {
      analysis = `Above-average schools within this suburb — ${inCount} school${inCount > 1 ? 's' : ''} in the Top 25% nationally. Quality school access supports family buyer demand and price stability.`
    } else {
      analysis = `Nearby Catholic and independent schools are above average nationally. Note that government school zones don't extend here — families relying on local government school access should check the specific catchment map for their address.`
    }
  } else if ((score ?? 0) >= 5.5) {
    analysis = `Schools within this suburb are around the national average. School quality is adequate but not a strong differentiating factor for investment — it won't deter buyers, but it's also not driving the catchment premiums that elite school suburbs command.`
  } else {
    analysis = `Below-average school quality within this suburb reduces demand from the most motivated buyer segment — families with school-age children. This limits the buyer pool and constrains capital growth compared to stronger catchment suburbs.`
  }

  // Add note about adjacent government schools NOT being automatically accessible
  const adjGovAboveAvg = schoolsAdj.filter(s => s.sector === 'Government' && s.icsea_percentile != null && s.icsea_percentile >= 75)
  if (adjGovAboveAvg.length > 0 && top5Accessible.length === 0) {
    analysis += ` Note: there are above-average government schools in adjacent suburbs (e.g. ${adjGovAboveAvg[0].name}), but government school zones are drawn by street boundary — residents of this suburb may not be in zone. Verify the specific catchment map before purchasing based on school access.`
  }

  function sectorColor(sector: string | null) {
    if (sector === 'Government')   return { bg: 'rgba(56,189,248,0.1)', color: '#38bdf8' }
    if (sector === 'Catholic')     return { bg: 'rgba(251,191,36,0.08)', color: '#fbbf24' }
    if (sector === 'Independent')  return { bg: 'rgba(52,211,153,0.1)', color: '#34d399' }
    return { bg: '#1e2638', color: '#6b7fa0' }
  }

  function ratingColor(rating: string | null) {
    if (!rating) return '#6b7fa0'
    const pct = parseInt(rating.replace(/[^0-9]/g, '') || '100')
    if (rating.startsWith('Top')) {
      if (pct <= 5)  return '#34d399'   // Top 5% — bright green
      if (pct <= 10) return '#34d399'   // Top 10% — green
      if (pct <= 15) return '#6ee7b7'   // Top 15% — light green
      if (pct <= 25) return '#f1c40f'   // Top 25% — yellow
      if (pct <= 35) return '#fbbf24'   // Top 35% — amber
      return '#fbbf24'                   // Top 50% — orange
    }
    return '#fb7185'                     // Bottom bands — red
  }

  const renderSchool = (s: SchoolEntry, i: number) => {
    const sc = sectorColor(s.sector)
    return (
      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #3a4050', flexWrap: 'wrap', gap: '6px' }}>
        <div style={{ flex: 1, minWidth: '200px' }}>
          <div style={{ color: '#cdd8e8', fontSize: '14px', fontWeight: 500 }}>{s.name}</div>
          <div style={{ display: 'flex', gap: '6px', marginTop: '4px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', backgroundColor: sc.bg, color: sc.color }}>{s.sector}</span>
            <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', backgroundColor: '#1e2638', color: '#6b7fa0' }}>{s.school_type}</span>
            {s.total_enrolments && <span style={{ fontSize: '11px', color: '#6b7fa0' }}>{s.total_enrolments.toLocaleString()} students</span>}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          {s.rating && (
            <div style={{ fontSize: '13px', fontWeight: 700, color: ratingColor(s.rating) }}>{s.rating}</div>
          )}
          {s.icsea && <div style={{ fontSize: '11px', color: '#6b7fa0' }}>ICSEA {s.icsea.toFixed(0)}</div>}
        </div>
      </div>
    )
  }

  return (
    <>
      <Analysis>{analysis}</Analysis>
      {schoolsIn.length > 0 && (
        <div style={{ backgroundColor: '#1e2638', borderRadius: '8px', padding: '16px', marginBottom: '14px' }}>
          <div style={{ fontSize: '12px', color: '#6b7fa0', marginBottom: '2px', textTransform: 'uppercase', letterSpacing: '1px' }}>Schools in this suburb</div>
          {schoolsIn.map(renderSchool)}
        </div>
      )}
      {schoolsAdj.length > 0 && (
        <div style={{ backgroundColor: '#1e2638', borderRadius: '8px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#6b7fa0', marginBottom: '2px', textTransform: 'uppercase', letterSpacing: '1px' }}>Schools in adjacent suburbs</div>
          <div style={{ fontSize: '12px', color: '#28334a', marginBottom: '8px' }}>These are within the broader catchment area</div>
          {schoolsAdj.map(renderSchool)}
        </div>
      )}
      {schoolsIn.length === 0 && schoolsAdj.length === 0 && (
        <p style={{ color: '#6b7fa0', fontSize: '14px' }}>School data not available for this suburb.</p>
      )}
      <div style={{ fontSize: '12px', color: '#28334a', fontStyle: 'italic', marginTop: '8px' }}>
        University and TAFE access is shown in the Liveability section — it is not factored into the education score as most suburbs have none, and absence should not penalise family-friendly suburbs.
      </div>
    </>
  )
}

function DemographicsSection({ score, facts }: {
  score: number | null
  facts: Record<string, number | null>
}) {
  const medianAge = facts.median_age
  const degree    = facts.uni_degree_pct
  const unemp     = facts.unemployment_pct
  const profess   = facts.professionals_managers_pct

  let analysis = ''
  if ((score ?? 0) >= 7) {
    analysis = `Strong demographic fundamentals. ${degree != null ? `${degree.toFixed(0)}% of residents hold university degrees — a high-education workforce that drives local spending and property demand.` : ''} High-income, educated demographics consistently support long-term capital growth.`
  } else if ((score ?? 0) >= 5) {
    analysis = `Middle-market demographics around the Australian median — a stable base that produces reliable tenant demand. ${unemp != null && unemp > 6 ? `Unemployment at ${unemp.toFixed(1)}% is worth monitoring.` : ''}`
  } else {
    analysis = `Below-average demographics present a trade-off. Lower education and professional workforce levels limit rent-paying capacity and constrain yield growth. Lower-income areas can still deliver strong gross yields at the right entry price.`
  }

  return (
    <>
      <Analysis>{analysis}</Analysis>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '12px', marginBottom: '14px' }}>
        {medianAge != null && (
          <MetricBlock label="Median age" value={medianAge.toFixed(0)} sentiment="neutral" />
        )}
        {degree != null && (
          <MetricBlock label="University degree" value={`${degree.toFixed(1)}%`}
            sentiment={degree >= 30 ? 'good' : degree >= 18 ? 'warn' : 'bad'} />
        )}
        {profess != null && (
          <MetricBlock label="Professionals & managers" value={`${profess.toFixed(1)}%`}
            sentiment={profess >= 25 ? 'good' : profess >= 15 ? 'warn' : 'bad'} />
        )}
        {unemp != null && (
          <MetricBlock label="Unemployment rate" value={`${unemp.toFixed(1)}%`}
            sentiment={unemp > 8 ? 'bad' : unemp > 5 ? 'warn' : 'good'} />
        )}
      </div>
      <div style={{ fontSize: '12px', color: '#28334a', fontStyle: 'italic' }}>
        Detailed age group breakdown (0–14, 15–24, 25–44, 45–64, 65+) coming soon.
      </div>
    </>
  )
}

function HousingSection({ score, facts }: {
  score: number | null
  facts: Record<string, number | null>
}) {
  const mortgageStress = facts.high_mortgage_stress_pct
  const rentStress     = facts.high_rent_stress_pct
  const houses         = facts.separate_house_pct
  const flats          = facts.flat_apartment_pct
  const lowRise        = facts.flat_low_rise_pct
  const midRise        = facts.flat_mid_rise_pct
  const highRise       = facts.flat_high_rise_pct
  const renters        = facts.renters_pct
  const socialHousing  = facts.social_housing_pct

  // Estimate townhouse % = total - houses - flats (remainder is semi-detached/townhouse)
  const townhouse = (houses != null && flats != null) ? Math.max(0, 100 - houses - flats) : null

  let analysis = ''
  if ((score ?? 0) >= 7) {
    analysis = `Healthy housing market fundamentals. ${mortgageStress != null ? `Only ${mortgageStress.toFixed(1)}% of mortgaged households are under stress — the market is not overextended. ` : ''}${socialHousing != null && socialHousing < 5 ? `Low social housing concentration (${socialHousing.toFixed(1)}%) signals a stable owner-occupier-led market.` : ''}`
  } else if ((score ?? 0) >= 5) {
    analysis = `Moderate housing market health. Some financial stress exists but is not systemic. ${mortgageStress != null ? `Mortgage stress at ${mortgageStress.toFixed(1)}%` : ''}${rentStress != null ? ` and rent stress at ${rentStress.toFixed(1)}%` : ''} are manageable. Monitor if interest rates rise further.`
  } else {
    analysis = `Elevated housing stress is a warning sign. ${mortgageStress != null && mortgageStress > 15 ? `${mortgageStress.toFixed(1)}% of mortgaged households are under financial stress — above the 10% danger threshold. ` : ''}${rentStress != null && rentStress > 20 ? `${rentStress.toFixed(1)}% rent stress increases vacancy and arrears risk.` : ''} High-stress markets can see forced selling and price corrections.`
  }

  return (
    <>
      <Analysis>{analysis}</Analysis>

      {/* Dwelling type breakdown */}
      <div style={{ backgroundColor: '#1e2638', borderRadius: '8px', padding: '16px', marginBottom: '14px' }}>
        <div style={{ fontSize: '12px', color: '#6b7fa0', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>Dwelling types</div>
        {[
          { label: 'Detached houses', value: houses, color: '#38bdf8' },
          { label: 'Townhouses / semi-detached', value: townhouse, color: '#a78bfa' },
          { label: 'Flats & apartments (total)', value: flats, color: '#fbbf24' },
          { label: '  └ Low-rise (1–2 storey)', value: lowRise, color: '#d4995a', indent: true },
          { label: '  └ Mid-rise (3–8 storey)', value: midRise, color: '#c8804a', indent: true },
          { label: '  └ High-rise (9+ storey)', value: highRise, color: '#c06030', indent: true },
        ].filter(r => r.value != null && r.value > 0).map(({ label, value, color, indent }) => (
          <div key={label} style={{ marginBottom: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: indent ? '12px' : '13px', marginBottom: '3px' }}>
              <span style={{ color: indent ? '#6b7fa0' : '#9aafc8' }}>{label}</span>
              <span style={{ color, fontWeight: 600 }}>{value!.toFixed(1)}%</span>
            </div>
            <div style={{ height: indent ? '3px' : '5px', backgroundColor: '#28334a', borderRadius: '2px' }}>
              <div style={{ height: '100%', width: `${value}%`, backgroundColor: color, borderRadius: '2px', opacity: indent ? 0.7 : 1 }} />
            </div>
          </div>
        ))}
      </div>

      {/* Financial stress */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '12px', marginBottom: '14px' }}>
        {mortgageStress != null && (
          <MetricBlock label="Mortgage stress" value={`${mortgageStress.toFixed(1)}%`}
            sentiment={mortgageStress > 15 ? 'bad' : mortgageStress > 10 ? 'warn' : 'good'} />
        )}
        {rentStress != null && (
          <MetricBlock label="Rent stress" value={`${rentStress.toFixed(1)}%`}
            sentiment={rentStress > 25 ? 'bad' : rentStress > 15 ? 'warn' : 'good'} />
        )}
        {renters != null && (
          <MetricBlock label="Renters" value={`${renters.toFixed(1)}%`} sentiment="neutral" />
        )}
        {socialHousing != null && (
          <MetricBlock label="Social housing" value={`${socialHousing.toFixed(1)}%`}
            sentiment={socialHousing > 15 ? 'bad' : 'neutral'} />
        )}
      </div>
      <div style={{ fontSize: '12px', color: '#28334a', fontStyle: 'italic' }}>
        Bedroom count breakdown (3-bed, 4-bed, 5-bed) and full dwelling structure detail coming soon.
      </div>
    </>
  )
}

function InfrastructureSection({ score, intermediates }: {
  score: number | null
  intermediates: Record<string, number | null>
}) {
  const projAUD   = intermediates.infra_committed_aud
  const projCount = intermediates.infra_project_count

  let analysis = ''
  if ((score ?? 0) >= 7) {
    analysis = `Significant government infrastructure investment is one of the most reliable capital growth predictors. ${projAUD ? `${fAUD(projAUD)} in committed investment signals that government planners have already priced this suburb's future into their capital program.` : ''} Historically, suburbs with major infrastructure projects within 5km see 15–25% price premiums over 5-year holding periods.`
  } else if ((score ?? 0) >= 5) {
    analysis = `Moderate infrastructure commitment. ${projCount ? `${projCount} active project${projCount > 1 ? 's' : ''} nearby` : 'Some nearby activity'} provides a tailwind but this is not a primary infrastructure-growth story. Watch for new government announcements — infrastructure surprise is one of the fastest suburb re-raters.`
  } else {
    analysis = `No committed government infrastructure investment is linked to this suburb. This is the biggest single gap in the investment case — without a project pipeline, capital growth will track broad market conditions rather than outperform. Monitor state budgets and transport plans for future announcements.`
  }

  return (
    <>
      <Analysis>{analysis}</Analysis>
      <div style={{ display: 'flex', flexWrap: 'wrap' }}>
        {projAUD ? <Bullet>{fAUD(projAUD)} committed investment nearby</Bullet> : <Bullet>No committed govt investment nearby</Bullet>}
        {projCount != null && projCount > 0 && <Bullet>{projCount} active infrastructure project{projCount > 1 ? 's' : ''}</Bullet>}
      </div>
    </>
  )
}

function GentrificationSection({ score, facts }: {
  score: number | null
  facts: Record<string, number | null>
}) {
  const degree   = facts.uni_degree_pct
  const profess  = facts.professionals_managers_pct
  const popGrowth = facts.pop_growth_proj_pct

  let analysis = ''
  if ((score ?? 0) >= 7.5) {
    analysis = 'Strong gentrification in progress. Rising professional workforce composition and high residential mobility are the classic signals of suburb transformation — the kind that produces above-market capital growth as the suburb reprices to its new demographic reality. Early entry captures the full repricing upside.'
  } else if ((score ?? 0) >= 5.5) {
    analysis = `Moderate gentrification signals — the suburb is in transition but not yet fully repriced. ${degree != null ? `${degree.toFixed(0)}% university degree holders` : ''}${profess != null ? ` and ${profess.toFixed(0)}% professionals` : ''} point to an upward-trending workforce. Entry at the right price matters here — buy the trend, not the premium.`
  } else {
    analysis = 'Limited gentrification underway. The social indicators do not yet show the professional influx that precedes sustained suburb repricing. This is not necessarily negative — stable, established suburbs with low turnover can be excellent buy-and-hold investments at the right price. Growth expectations should be modest and yield-driven.'
  }

  return (
    <>
      <Analysis>{analysis}</Analysis>
      <div style={{ display: 'flex', flexWrap: 'wrap' }}>
        {profess != null && <Bullet>{profess.toFixed(1)}% professionals & managers</Bullet>}
        {degree != null && <Bullet>{degree.toFixed(1)}% university degree holders</Bullet>}
        {popGrowth != null && <Bullet>{popGrowth.toFixed(1)}% projected population growth to 2031</Bullet>}
      </div>
    </>
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

  usePageTitle(state.status === 'ready' ? `${state.data.suburb_name} ${state.data.state}` : null)

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '0 0 80px' }}>
      <div style={{ marginBottom: '24px' }}>
        <Link to="/" style={{ color: '#6b7fa0', textDecoration: 'none', fontSize: '14px' }}>← Back to Search</Link>
      </div>
      {state.status === 'loading' && <p style={{ color: '#6b7fa0' }}>Loading…</p>}
      {state.status === 'error' && (
        <div style={{ backgroundColor: 'rgba(251,113,133,0.08)', border: '1px solid rgba(251,113,133,0.25)', borderRadius: '12px', padding: '24px', color: '#fb7185' }}>
          <h2 style={{ marginTop: 0, color: '#fda4af' }}>Could not load suburb</h2>
          <p style={{ margin: 0 }}>{state.message}</p>
        </div>
      )}
      {state.status === 'ready' && <ReadyView data={state.data} onNavigateSA2={navigate} />}
    </div>
  )
}

function ReadyView({ data, onNavigateSA2 }: { data: GroupReport; onNavigateSA2: (p: string) => void }) {
  const { suburb_name, state: stateCode, scores, facts, intermediates, insight, risk_flags, tags,
    sa2_count, sa2_names, sa2_codes, sa2_breakdown, population,
    schools_in_suburb, schools_adjacent, adjacent_has_train, adjacent_train_suburbs,
    universities_nearby, hospitals_nearby, shopping_nearby, cbd_distance_km, cbd_city, commute_times,
    population_density, parks_per_km2, market_data, rank, peer_suburbs } = data
  const isMulti = sa2_count > 1

  return (
    <>
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' }}>
          <h1 style={{ fontSize: '40px', fontWeight: 800, margin: 0, color: '#cdd8e8', letterSpacing: '-0.03em' }}>{suburb_name}</h1>
          <span style={{ color: '#6b7fa0', fontSize: '22px' }}>{stateCode}</span>
        </div>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginTop: '6px', flexWrap: 'wrap' }}>
          {population && <span style={{ color: '#6b7fa0', fontSize: '13px' }}>{population.toLocaleString()} residents</span>}
          {population_density != null && (
            <span style={{ color: '#6b7fa0', fontSize: '13px' }}>
              🏘️ <span style={{ color: '#9aafc8' }}>{Math.round(population_density).toLocaleString()}</span> people/km²
            </span>
          )}
          {parks_per_km2 != null && (
            <span style={{ color: '#6b7fa0', fontSize: '13px' }}>
              🌳 <span style={{ color: '#9aafc8' }}>{parks_per_km2.toFixed(1)}</span> parks/km²
            </span>
          )}
          {cbd_distance_km != null && cbd_city && (
            <span style={{ color: '#6b7fa0', fontSize: '13px' }}>
              📍 <span style={{ color: '#9aafc8' }}>{cbd_distance_km}km</span> from {cbd_city} CBD
            </span>
          )}
        </div>
        {tags.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
            {tags.map(t => {
              const note = t === 'Emerging Opportunity'
                ? ` — score ${scores.investment_score?.toFixed(1)}/10`
                : t === 'Moderate Growth'
                ? ` — score ${scores.investment_score?.toFixed(1)}/10`
                : ''
              return (
                <span key={t} style={{
                  padding: '4px 12px', backgroundColor: 'rgba(45,212,191,0.1)',
                  color: '#2dd4bf', borderRadius: '99px', fontSize: '12px', fontWeight: 600,
                  border: '1px solid rgba(45,212,191,0.2)',
                }}>
                  {t}{note}
                </span>
              )
            })}
          </div>
        )}
      </div>

      {/* ABS split notice */}
      {isMulti && (
        <div style={{ backgroundColor: '#1e2638', border: '1px solid #28334a', borderRadius: '10px', padding: '14px 18px', marginBottom: '24px', display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
          <span>ℹ️</span>
          <div style={{ fontSize: '14px', color: '#9aafc8' }}>
            <strong style={{ color: '#cdd8e8' }}>{suburb_name}</strong> spans {sa2_count} ABS statistical areas — scores are population-weighted averages. Each intelligence section shows individual area comparisons.
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px', flexWrap: 'wrap' }}>
              {sa2_codes.map((code, i) => (
                <button key={code} onClick={() => onNavigateSA2(`/suburb/${code}`)}
                  style={{ padding: '3px 10px', backgroundColor: '#151b27', color: '#6b7fa0', border: '1px solid #28334a', borderRadius: '6px', cursor: 'pointer', fontSize: '12px' }}>
                  View {sa2_names[i]} →
                </button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Investment score hero */}
      <div className="hero-row" style={{
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
          <div style={{ fontSize: '76px', fontWeight: 800, color: scoreColor(scores.investment_score), lineHeight: 1, letterSpacing: '-0.04em' }}>
            {fv(scores.investment_score)}
          </div>
          <div style={{ marginTop: '10px' }}>
            <GaugeBar value={scores.investment_score ?? 0} max={10} showValue={false} height={6} />
          </div>
          <div style={{ color: '#6b7fa0', fontSize: '12px', marginTop: '6px' }}>
            out of 10
            {scoreToTopPct(scores.investment_score) && (
              <span style={{ marginLeft: '8px', color: scoreColor(scores.investment_score), fontWeight: 600 }}>
                · {scoreToTopPct(scores.investment_score)} nationally
              </span>
            )}
          </div>
        </div>
        <div style={{ flex: 1, minWidth: '240px', color: '#9aafc8', fontSize: '16px', lineHeight: 1.75, paddingTop: '4px' }}>{insight}</div>
      </div>

      {/* Percentile rank bar */}
      {rank && (
        <div style={{ backgroundColor: '#151b27', border: '1px solid #28334a', borderRadius: '12px', padding: '20px 24px', marginBottom: '28px', boxShadow: '0 2px 12px rgba(0,0,0,0.45)' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '12px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ color: '#9aafc8', fontSize: '14px' }}>
              <strong style={{ color: '#cdd8e8' }}>#{rank.national_rank}</strong>
              <span style={{ color: '#6b7fa0' }}> of {rank.national_total.toLocaleString()} suburbs nationally</span>
              <span style={{ margin: '0 10px', color: '#28334a' }}>·</span>
              <strong style={{ color: '#cdd8e8' }}>#{rank.state_rank}</strong>
              <span style={{ color: '#6b7fa0' }}> of {rank.state_total.toLocaleString()} in {stateCode}</span>
            </div>
            <SeverityBadge
              level={rank.national_pct >= 75 ? 'good' : rank.national_pct >= 50 ? 'warn' : 'bad'}
              label={`Top ${(100 - rank.national_pct + 0.1).toFixed(0)}% nationally`}
            />
          </div>
          {/* Rank bar */}
          <div style={{ position: 'relative', height: '8px', backgroundColor: '#1e2638', borderRadius: '4px' }}>
            <div style={{
              position: 'absolute', left: 0, top: 0, height: '100%',
              width: `${rank.national_pct}%`,
              background: 'linear-gradient(to right, #fb7185, #fbbf24, #34d399)',
              borderRadius: '4px',
            }} />
            <div style={{
              position: 'absolute', top: '-3px',
              left: `calc(${rank.national_pct}% - 7px)`,
              width: '14px', height: '14px',
              backgroundColor: scoreColor(scores.investment_score),
              border: '2px solid #151b27',
              borderRadius: '50%',
            }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#36445e', marginTop: '4px' }}>
            <span>Lowest</span><span>Highest</span>
          </div>
        </div>
      )}

      {/* ── Market Snapshot ── */}
      {market_data && (
        <SectionPanel
          title="📊 Market Snapshot"
          subtitle={market_data.as_of
            ? `Data as of ${new Date(market_data.as_of).toLocaleDateString('en-AU', { month: 'short', year: 'numeric' })} · Source: PropRadar`
            : undefined}
        >
          {/* House vs Unit table */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
            {/* House */}
            <div style={{ backgroundColor: '#0d1117', borderRadius: '8px', padding: '16px' }}>
              <div style={{ fontSize: '12px', color: '#6b7fa0', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.07em' }}>🏠 House</div>
              {[
                ['Median price',   market_data.house_median_price ? `$${market_data.house_median_price.toLocaleString()}` : '—'],
                ['Weekly rent',    market_data.house_weekly_rent  ? `$${market_data.house_weekly_rent}/wk`  : '—'],
                ['Gross yield',    market_data.house_gross_yield_pct != null ? `${market_data.house_gross_yield_pct.toFixed(2)}%` : '—'],
                ['1yr growth',     market_data.house_1y_growth_pct != null ? `${market_data.house_1y_growth_pct > 0 ? '+' : ''}${market_data.house_1y_growth_pct.toFixed(1)}%` : '—'],
                ['3yr growth',     market_data.house_3y_growth_pct != null ? `+${market_data.house_3y_growth_pct.toFixed(1)}%` : '—'],
                ['5yr growth',     market_data.house_5y_growth_pct != null ? `+${market_data.house_5y_growth_pct.toFixed(1)}%` : '—'],
                ['Days on market', market_data.house_days_on_market != null ? `${market_data.house_days_on_market} days` : '—'],
                ['Sales (12mo)',   market_data.house_sales_12mo != null ? `${market_data.house_sales_12mo}` : '—'],
              ].map(([label, val]) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid #1e2638', fontSize: '13px' }}>
                  <span style={{ color: '#6b7fa0' }}>{label}</span>
                  <span style={{ color: '#cdd8e8', fontWeight: 600 }}>{val}</span>
                </div>
              ))}
            </div>
            {/* Unit */}
            <div style={{ backgroundColor: '#0d1117', borderRadius: '8px', padding: '16px' }}>
              <div style={{ fontSize: '12px', color: '#6b7fa0', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '0.07em' }}>🏢 Unit / Apartment</div>
              {[
                ['Median price',   market_data.unit_median_price ? `$${market_data.unit_median_price.toLocaleString()}` : '—'],
                ['Weekly rent',    market_data.unit_weekly_rent  ? `$${market_data.unit_weekly_rent}/wk`  : '—'],
                ['Gross yield',    market_data.unit_gross_yield_pct != null ? `${market_data.unit_gross_yield_pct.toFixed(2)}%` : '—'],
                ['1yr growth',     market_data.unit_1y_growth_pct != null ? `${market_data.unit_1y_growth_pct > 0 ? '+' : ''}${market_data.unit_1y_growth_pct.toFixed(1)}%` : '—'],
                ['3yr growth',     market_data.unit_3y_growth_pct != null ? `+${market_data.unit_3y_growth_pct.toFixed(1)}%` : '—'],
                ['5yr growth',     market_data.unit_5y_growth_pct != null ? `+${market_data.unit_5y_growth_pct.toFixed(1)}%` : '—'],
                ['Days on market', market_data.unit_days_on_market != null ? `${market_data.unit_days_on_market} days` : '—'],
                ['Sales (12mo)',   market_data.unit_sales_12mo != null ? `${market_data.unit_sales_12mo}` : '—'],
              ].map(([label, val]) => (
                <div key={label} style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid #1e2638', fontSize: '13px' }}>
                  <span style={{ color: '#6b7fa0' }}>{label}</span>
                  <span style={{ color: '#cdd8e8', fontWeight: 600 }}>{val}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Growth sparklines */}
          {(market_data.house_1y_growth_pct != null || market_data.house_3y_growth_pct != null || market_data.house_5y_growth_pct != null) && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
              {[
                { label: '🏠 House price growth', y1: market_data.house_1y_growth_pct, y3: market_data.house_3y_growth_pct, y5: market_data.house_5y_growth_pct },
                { label: '🏢 Unit price growth',  y1: market_data.unit_1y_growth_pct,  y3: market_data.unit_3y_growth_pct,  y5: market_data.unit_5y_growth_pct  },
              ].map(({ label, y1, y3, y5 }) => {
                const points = [y5, y3, y1].filter((v): v is number => v != null)
                const labels = [y5, y3, y1].map((v, i) => v != null ? (['5yr', '3yr', '1yr'][i]) : null).filter((l): l is string => l !== null)
                if (points.length < 2) return null
                const last = points[points.length - 1]
                const color = last >= 0 ? '#34d399' : '#fb7185'
                return (
                  <div key={label} style={{ backgroundColor: '#0d1117', borderRadius: '8px', padding: '12px 14px' }}>
                    <div style={{ fontSize: '11px', color: '#6b7fa0', marginBottom: '4px' }}>{label}</div>
                    <div style={{ fontSize: '20px', fontWeight: 700, color, marginBottom: '6px' }}>
                      {last > 0 ? '+' : ''}{last.toFixed(1)}% <span style={{ fontSize: '11px', color: '#36445e' }}>1yr</span>
                    </div>
                    <TrendSparkline data={points} labels={labels} color={color} height={36} showTooltip referenceValue={0} />
                    <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '10px', color: '#36445e', marginTop: '2px' }}>
                      <span>{labels[0]}</span><span>{labels[labels.length - 1]}</span>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Market indicators row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '10px' }}>
            {market_data.vacancy_rate_pct != null && (
              <div style={{ backgroundColor: '#0d1117', borderRadius: '8px', padding: '12px 14px' }}>
                <div style={{ fontSize: '11px', color: '#6b7fa0', marginBottom: '4px' }}>Vacancy rate</div>
                <div style={{ fontSize: '22px', fontWeight: 700,
                  color: market_data.vacancy_rate_pct < 2 ? '#34d399' : market_data.vacancy_rate_pct < 3 ? '#fbbf24' : '#fb7185' }}>
                  {market_data.vacancy_rate_pct.toFixed(1)}%
                </div>
                <div style={{ fontSize: '11px', color: '#36445e' }}>
                  {market_data.vacancy_rate_pct < 2 ? 'Very tight rental market' : market_data.vacancy_rate_pct < 3 ? 'Balanced' : 'Softer rental demand'}
                </div>
              </div>
            )}
            {market_data.house_heat_score != null && (
              <div style={{ backgroundColor: '#0d1117', borderRadius: '8px', padding: '12px 14px' }}>
                <div style={{ fontSize: '11px', color: '#6b7fa0', marginBottom: '4px' }}>Demand heat score</div>
                <div style={{ fontSize: '22px', fontWeight: 700,
                  color: market_data.house_heat_score >= 65 ? '#34d399' : market_data.house_heat_score >= 45 ? '#fbbf24' : '#fb7185' }}>
                  {market_data.house_heat_score.toFixed(0)}<span style={{ fontSize: '12px', color: '#6b7fa0' }}>/100</span>
                </div>
                <div style={{ fontSize: '11px', color: '#36445e' }}>
                  {market_data.house_heat_score >= 65 ? 'Strong buyer demand' : market_data.house_heat_score >= 45 ? 'Moderate demand' : 'Softer buyer market'}
                </div>
              </div>
            )}
            {market_data.sold_vs_asking_pct != null && (
              <div style={{ backgroundColor: '#0d1117', borderRadius: '8px', padding: '12px 14px' }}>
                <div style={{ fontSize: '11px', color: '#6b7fa0', marginBottom: '4px' }}>Sold vs asking</div>
                <div style={{ fontSize: '22px', fontWeight: 700, color: market_data.sold_vs_asking_pct > 0 ? '#34d399' : '#fb7185' }}>
                  {market_data.sold_vs_asking_pct > 0 ? '+' : ''}{market_data.sold_vs_asking_pct.toFixed(1)}%
                </div>
                <div style={{ fontSize: '11px', color: '#36445e' }}>
                  {market_data.sold_vs_asking_pct > 2 ? 'Selling above asking' : market_data.sold_vs_asking_pct > 0 ? 'Near asking price' : 'Below asking price'}
                </div>
              </div>
            )}
          </div>
        </SectionPanel>
      )}

      {/* Score Breakdown — clean cards */}
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '16px', color: '#cdd8e8', letterSpacing: '-0.01em' }}>Score Breakdown</h2>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: '14px', marginBottom: '48px' }}>
        <ScoreCard label="Liveability"     value={scores.liveability_score}    desc="Amenity access, transit, healthcare, parks" />
        <ScoreCard label="Growth"          value={scores.growth_score}          desc="Population growth, investment pipeline, gentrification" />
        <ScoreCard label="Education"       value={scores.education_score}       desc="School quality, coverage of all levels" />
        <ScoreCard label="Demographics"    value={scores.demographic_score}     desc="Income, SEIFA, workforce education" />
        <ScoreCard label="Housing Market"  value={scores.housing_score}         desc="Mortgage/rent stress, dwelling character" />
        <ScoreCard label="Infrastructure"  value={scores.infrastructure_score}  desc="Committed government investment pipeline" />
        <ScoreCard label="Gentrification"  value={scores.gentrification_index}  desc="Composite social uplift signal" />
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

      {/* Investment Intelligence */}
      <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '8px', color: '#cdd8e8', letterSpacing: '-0.01em' }}>Investment Intelligence</h2>
      <p style={{ color: '#6b7fa0', fontSize: '14px', marginBottom: '28px' }}>
        What each score means for your investment decision — and what the data is telling you.
      </p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <IntelPanel emoji="🏙️" label="Liveability"    dimKey="liveability_score"    score={scores.liveability_score}    sa2Breakdown={sa2_breakdown} isMulti={isMulti}>
          <LiveabilitySection score={scores.liveability_score} facts={facts} adjacentHasTrain={adjacent_has_train} adjacentTrainSuburbs={adjacent_train_suburbs} universitiesNearby={universities_nearby || []} hospitalsNearby={hospitals_nearby || []} shoppingNearby={shopping_nearby || []} commuteTimes={commute_times} cbdCity={cbd_city} />
        </IntelPanel>

        <IntelPanel emoji="📈" label="Growth"         dimKey="growth_score"          score={scores.growth_score}          sa2Breakdown={sa2_breakdown} isMulti={isMulti}>
          <GrowthSection score={scores.growth_score} facts={facts} intermediates={intermediates} />
        </IntelPanel>

        <IntelPanel emoji="🏫" label="Education"      dimKey="education_score"       score={scores.education_score}       sa2Breakdown={sa2_breakdown} isMulti={isMulti}>
          <EducationSection score={scores.education_score} schoolsIn={schools_in_suburb || []} schoolsAdj={schools_adjacent || []} />
        </IntelPanel>

        <IntelPanel emoji="👥" label="Demographics"   dimKey="demographic_score"     score={scores.demographic_score}     sa2Breakdown={sa2_breakdown} isMulti={isMulti}>
          <DemographicsSection score={scores.demographic_score} facts={facts} />
        </IntelPanel>

        <IntelPanel emoji="🏠" label="Housing Market" dimKey="housing_score"         score={scores.housing_score}         sa2Breakdown={sa2_breakdown} isMulti={isMulti}>
          <HousingSection score={scores.housing_score} facts={facts} />
        </IntelPanel>

        <IntelPanel emoji="🏗️" label="Infrastructure" dimKey="infrastructure_score"  score={scores.infrastructure_score}  sa2Breakdown={sa2_breakdown} isMulti={isMulti}>
          <InfrastructureSection score={scores.infrastructure_score} intermediates={intermediates} />
        </IntelPanel>

        <IntelPanel emoji="☕" label="Gentrification" dimKey="gentrification_index"  score={scores.gentrification_index}  sa2Breakdown={sa2_breakdown} isMulti={isMulti}>
          <GentrificationSection score={scores.gentrification_index} facts={facts} />
        </IntelPanel>
      </div>

      {/* Peer suburbs */}
      {peer_suburbs && peer_suburbs.length > 0 && (
        <div style={{ marginTop: '40px', marginBottom: '48px' }}>
          <h2 style={{ fontSize: '20px', fontWeight: 700, marginBottom: '8px', color: '#cdd8e8', letterSpacing: '-0.01em' }}>
            Similar Suburbs in {stateCode}
          </h2>
          <p style={{ color: '#6b7fa0', fontSize: '14px', marginBottom: '16px' }}>
            Suburbs with comparable investment profiles — useful for benchmarking or finding alternatives.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px' }}>
            {peer_suburbs.map(p => (
              <a key={p.suburb_id} href={`/suburb-group/${p.suburb_id}`} style={{ textDecoration: 'none' }}>
                <div style={{ backgroundColor: '#151b27', border: '1px solid #28334a', borderRadius: '12px', padding: '18px', cursor: 'pointer', transition: 'border-color 0.15s' }}>
                  <div style={{ fontWeight: 700, color: '#cdd8e8', fontSize: '15px', marginBottom: '2px' }}>{p.suburb_name}</div>
                  <div style={{ color: '#6b7fa0', fontSize: '12px', marginBottom: '12px' }}>{p.state}{p.population ? ` · ${p.population.toLocaleString()}` : ''}</div>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px', marginBottom: '10px' }}>
                    <span style={{ fontSize: '28px', fontWeight: 800, color: scoreColor(p.investment_score), letterSpacing: '-0.03em' }}>{fv(p.investment_score)}</span>
                    <span style={{ fontSize: '11px', color: '#6b7fa0' }}>/ 10</span>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    {([
                      { k: 'liveability_score', l: 'Liveability' },
                      { k: 'growth_score',      l: 'Growth' },
                      { k: 'education_score',   l: 'Education' },
                    ] as { k: keyof PeerSuburb; l: string }[]).map(({ k, l }) => {
                      const v = p[k] as number | null
                      if (v == null) return null
                      return (
                        <GaugeBar key={String(k)} value={v} max={10} label={l} height={4} />
                      )
                    })}
                  </div>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

    </>
  )
}
