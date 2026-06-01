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
  adjacent_has_train: boolean
  adjacent_train_suburbs: string[]
  cbd_distance_km: number | null
  cbd_city: string | null
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
  if (v == null) return '#9ca0aa'
  if (v >= 7) return '#2ecc71'
  if (v >= 5) return '#f39c12'
  return '#e74c3c'
}

function signalBadge(score: number | null) {
  if (score == null) return { label: 'No data', bg: '#3a3a4a', color: '#9ca0aa' }
  if (score >= 7.5) return { label: '✓ Strong signal', bg: '#1a3a1a', color: '#2ecc71' }
  if (score >= 6.0) return { label: '↗ Positive',      bg: '#2a3020', color: '#a8e063' }
  if (score >= 5.0) return { label: '→ Neutral',       bg: '#2a2a1a', color: '#f39c12' }
  if (score >= 3.5) return { label: '↘ Caution',       bg: '#3a2a1a', color: '#e67e22' }
  return                    { label: '✗ Risk factor',  bg: '#3a1a1a', color: '#e74c3c' }
}

// ── Components ─────────────────────────────────────────────────────────────

function ScoreCard({ label, value, desc }: { label: string; value: number | null; desc: string }) {
  const color = scoreColor(value)
  return (
    <div style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '20px' }}>
      <div style={{ fontSize: '12px', color: '#9ca0aa', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '6px' }}>{label}</div>
      <div style={{ fontSize: '42px', fontWeight: 700, color, lineHeight: 1 }}>{fv(value)}</div>
      <div style={{ height: '4px', backgroundColor: '#4b566a', borderRadius: '2px', margin: '10px 0 8px' }}>
        <div style={{ height: '100%', width: `${value != null ? (value / 10) * 100 : 0}%`, backgroundColor: color, borderRadius: '2px' }} />
      </div>
      <p style={{ color: '#9ca0aa', fontSize: '12px', margin: 0 }}>{desc}</p>
    </div>
  )
}

function IntelPanel({ emoji, label, score, children, sa2Breakdown, dimKey, isMulti }: {
  emoji: string; label: string; score: number | null
  children: React.ReactNode
  sa2Breakdown: SA2Entry[]; dimKey: string; isMulti: boolean
}) {
  const badge = signalBadge(score)
  const color = scoreColor(score)
  return (
    <div style={{ backgroundColor: '#2a3040', border: '1px solid #4b566a', borderRadius: '12px', padding: '28px', marginBottom: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', marginBottom: '18px', flexWrap: 'wrap' }}>
        <span style={{ fontSize: '22px' }}>{emoji}</span>
        <h3 style={{ margin: 0, fontSize: '20px', color: '#f8f8f2' }}>{label}</h3>
        <span style={{ fontSize: '28px', fontWeight: 800, color }}>{fv(score)}<span style={{ fontSize: '14px', color: '#9ca0aa', fontWeight: 400 }}>/10</span></span>
        <span style={{ padding: '4px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: 700, backgroundColor: badge.bg, color: badge.color }}>{badge.label}</span>
      </div>

      {/* Per-area comparison (multi-SA2 only) */}
      {isMulti && sa2Breakdown.length > 1 && (
        <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '14px 16px', marginBottom: '18px' }}>
          <div style={{ fontSize: '11px', color: '#9ca0aa', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '1px' }}>By area</div>
          {sa2Breakdown.map(sa2 => {
            const v = sa2.scores[dimKey as keyof Scores]
            const c = scoreColor(v)
            const shortName = sa2.sa2_name.replace(/^.+ - /, '')
            return (
              <div key={sa2.sa2_code} style={{ marginBottom: '10px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', marginBottom: '4px' }}>
                  <span style={{ color: '#d1d5da' }}>{shortName}{sa2.population ? ` · ${sa2.population.toLocaleString()} residents` : ''}</span>
                  <span style={{ color: c, fontWeight: 700 }}>{fv(v)}</span>
                </div>
                <div style={{ height: '5px', backgroundColor: '#4b566a', borderRadius: '3px' }}>
                  <div style={{ height: '100%', width: `${v != null ? (v / 10) * 100 : 0}%`, backgroundColor: c, borderRadius: '3px' }} />
                </div>
              </div>
            )
          })}
        </div>
      )}

      {children}
    </div>
  )
}

function Bullet({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ display: 'inline-block', padding: '5px 12px', backgroundColor: '#343b47', color: '#9ca0aa', borderRadius: '6px', fontSize: '13px', margin: '3px 6px 3px 0' }}>
      {children}
    </span>
  )
}

function Analysis({ children }: { children: React.ReactNode }) {
  return <p style={{ color: '#d1d5da', fontSize: '15px', lineHeight: 1.75, margin: '0 0 14px' }}>{children}</p>
}

// ── Intelligence sections ──────────────────────────────────────────────────

const PT_MODE_LABELS: Record<string, string> = {
  train: 'Train', tram: 'Tram', ferry: 'Ferry ⛴️',
  bus: 'Bus', limited: 'Limited PT',
}

function LiveabilitySection({ score, facts, adjacentHasTrain, adjacentTrainSuburbs, universitiesNearby, hospitalsNearby, commuteTimes, cbdCity }: {
  score: number | null
  facts: Record<string, number | null>
  adjacentHasTrain: boolean
  adjacentTrainSuburbs: string[]
  universitiesNearby: UniEntry[]
  hospitalsNearby: HospitalEntry[]
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
        <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '16px', marginBottom: '14px' }}>
          <div style={{ fontSize: '12px', color: '#9ca0aa', marginBottom: '10px', textTransform: 'uppercase', letterSpacing: '1px' }}>
            Registered Businesses <span style={{ fontSize: '10px', color: '#4b566a', textTransform: 'none' }}>(ABS Business Register, June 2025)</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: '8px' }}>
            {[
              { label: 'Food & Beverage', value: facts.biz_food_services, icon: '🍽️', note: 'cafes, restaurants, takeaway' },
              { label: 'Health & Medical', value: facts.biz_health_social, icon: '🏥', note: 'GPs, pharmacies, allied health' },
              { label: 'Retail', value: facts.biz_retail_trade, icon: '🛍️', note: 'shops of all types' },
              { label: 'Arts & Recreation', value: facts.biz_arts_recreation, icon: '🏋️', note: 'gyms, sport, entertainment' },
              { label: 'Other Services', value: facts.biz_other_services, icon: '🔧', note: 'mechanics, hair, laundry' },
            ].map(({ label, value, icon, note }) => value != null && value > 0 ? (
              <div key={label} style={{ backgroundColor: '#2a3040', borderRadius: '6px', padding: '10px 12px' }}>
                <div style={{ fontSize: '18px', marginBottom: '2px' }}>{icon} <span style={{ fontSize: '20px', fontWeight: 700, color: '#f8f8f2' }}>{value}</span></div>
                <div style={{ fontSize: '12px', color: '#d1d5da', fontWeight: 500 }}>{label}</div>
                <div style={{ fontSize: '11px', color: '#9ca0aa' }}>{note}</div>
              </div>
            ) : null)}
          </div>
          {facts.biz_total != null && (
            <div style={{ marginTop: '10px', fontSize: '12px', color: '#9ca0aa' }}>
              {facts.biz_total.toLocaleString()} total registered businesses in this SA2
            </div>
          )}
        </div>
      )}

      {/* Key Nearby Facilities */}
      {(universitiesNearby.length > 0 || hospitalsNearby.length > 0 || (facts.osm_shopping_centres ?? 0) > 0) && (
        <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '16px', marginBottom: '14px' }}>
          <div style={{ fontSize: '12px', color: '#9ca0aa', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>
            Key Nearby Facilities
          </div>

          {/* Universities / TAFE */}
          {universitiesNearby.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <div style={{ fontSize: '12px', color: '#7ec8e3', marginBottom: '6px', fontWeight: 600 }}>🎓 University / TAFE</div>
              {universitiesNearby.map((u, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #3a4050' }}>
                  <span style={{ color: '#d1d5da', fontSize: '13px' }}>{u.name}</span>
                  <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px',
                    backgroundColor: u.in_suburb ? '#1a3a1a' : '#2a3040',
                    color: u.in_suburb ? '#2ecc71' : '#9ca0aa' }}>
                    {u.in_suburb ? 'In suburb' : `${u.dist_km}km away`}
                  </span>
                </div>
              ))}
              <div style={{ fontSize: '11px', color: '#4b566a', marginTop: '4px', fontStyle: 'italic' }}>
                Access to university/TAFE expands the renter pool to students and academics — positive for rental demand.
              </div>
            </div>
          )}

          {/* Hospitals */}
          {hospitalsNearby.length > 0 && (
            <div style={{ marginBottom: '10px' }}>
              <div style={{ fontSize: '12px', color: '#e07070', marginBottom: '6px', fontWeight: 600 }}>🏥 Hospitals</div>
              {hospitalsNearby.slice(0, 6).map((h, i) => (
                <div key={i} style={{ display: 'flex', justifyContent: 'space-between', padding: '4px 0', borderBottom: '1px solid #3a4050' }}>
                  <span style={{ color: '#d1d5da', fontSize: '13px' }}>{h.name}</span>
                  <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px',
                    backgroundColor: h.dist_km <= 3 ? '#3a1a1a' : '#2a3040',
                    color: h.dist_km <= 3 ? '#e07070' : '#9ca0aa' }}>
                    {h.type} · {h.dist_km <= 1 ? 'In suburb' : `${h.dist_km}km`}
                  </span>
                </div>
              ))}
            </div>
          )}

          {/* Major shopping */}
          {(facts.osm_shopping_centres ?? 0) > 0 && (
            <div>
              <div style={{ fontSize: '12px', color: '#f39c12', marginBottom: '4px', fontWeight: 600 }}>🛍️ Major Shopping</div>
              <div style={{ color: '#d1d5da', fontSize: '13px' }}>
                {facts.osm_shopping_centres} major shopping centre{(facts.osm_shopping_centres ?? 0) > 1 ? 's' : ''} in this suburb
              </div>
            </div>
          )}
        </div>
      )}

      {/* Commute to CBD — standalone section */}
      {commuteTimes && cbdCity && (
        <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '16px', marginBottom: '14px' }}>
          <div style={{ fontSize: '12px', color: '#9ca0aa', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>
            🏙️ Commute to {cbdCity} CBD
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(140px, 1fr))', gap: '8px' }}>
            {/* Drive off-peak */}
            <div style={{ backgroundColor: '#2a3040', borderRadius: '6px', padding: '10px 12px' }}>
              <div style={{ fontSize: '11px', color: '#9ca0aa', marginBottom: '4px' }}>🚗 Drive off-peak</div>
              <div style={{ color: '#f8f8f2', fontSize: '20px', fontWeight: 700, lineHeight: 1 }}>
                {commuteTimes.drive_offpeak_min}<span style={{ fontSize: '12px', fontWeight: 400, color: '#9ca0aa' }}> min</span>
              </div>
              <div style={{ fontSize: '11px', color: '#4b566a', marginTop: '3px' }}>{commuteTimes.road_distance_km}km by road</div>
            </div>
            {/* Drive peak */}
            <div style={{ backgroundColor: '#2a3040', borderRadius: '6px', padding: '10px 12px' }}>
              <div style={{ fontSize: '11px', color: '#9ca0aa', marginBottom: '4px' }}>🚗 Drive peak hour</div>
              <div style={{ color: '#e67e22', fontSize: '20px', fontWeight: 700, lineHeight: 1 }}>
                {commuteTimes.drive_peak_min}<span style={{ fontSize: '12px', fontWeight: 400, color: '#9ca0aa' }}> min</span>
              </div>
              <div style={{ fontSize: '11px', color: '#4b566a', marginTop: '3px' }}>incl. congestion</div>
            </div>
            {/* PT */}
            <div style={{ backgroundColor: '#2a3040', borderRadius: '6px', padding: '10px 12px' }}>
              <div style={{ fontSize: '11px', color: '#9ca0aa', marginBottom: '4px' }}>
                {commuteTimes.pt_mode === 'ferry' ? '⛴️ By Ferry' :
                 commuteTimes.pt_mode === 'train' ? '🚆 By Train' :
                 commuteTimes.pt_mode === 'tram'  ? '🚊 By Tram'  : '🚌 By Bus'}
              </div>
              <div style={{ color: '#3498db', fontSize: '20px', fontWeight: 700, lineHeight: 1 }}>
                ~{commuteTimes.pt_min}<span style={{ fontSize: '12px', fontWeight: 400, color: '#9ca0aa' }}> min</span>
              </div>
              <div style={{ fontSize: '11px', color: '#4b566a', marginTop: '3px' }}>
                {commuteTimes.pt_mode === 'ferry' ? 'CityCat / ferry' :
                 commuteTimes.pt_mode === 'train' ? 'Via rail' :
                 commuteTimes.pt_mode === 'tram'  ? 'Via tram' : 'May need transfer'}
              </div>
            </div>
          </div>
          <div style={{ fontSize: '11px', color: '#4b566a', marginTop: '10px', fontStyle: 'italic' }}>
            Driving: OSRM road network (free-flow off-peak, estimated peak congestion). PT: estimate from distance and transit modes available — actual times vary.
          </div>
        </div>
      )}

      {/* Public transport stops */}
      <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '16px', marginBottom: '14px' }}>
        <div style={{ fontSize: '12px', color: '#9ca0aa', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>Public Transport</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>

          {/* Train */}
          <div style={{ padding: '8px 10px', borderRadius: '6px', backgroundColor: hasTrain ? '#1a3a1a' : '#2a3040' }}>
            <div style={{ fontSize: '18px', marginBottom: '2px' }}>🚆</div>
            {hasTrain ? (
              <div style={{ color: '#2ecc71', fontSize: '13px', fontWeight: 600 }}>
                {facts.pt_stop_train} train stop{(facts.pt_stop_train ?? 0) > 1 ? 's' : ''}
              </div>
            ) : adjacentHasTrain ? (
              <div>
                <div style={{ color: '#f39c12', fontSize: '13px', fontWeight: 600 }}>Train nearby</div>
                <div style={{ color: '#9ca0aa', fontSize: '11px' }}>{adjacentTrainSuburbs.slice(0,1).join(', ')}</div>
              </div>
            ) : (
              <div style={{ color: '#4b566a', fontSize: '13px' }}>No train access</div>
            )}
          </div>

          {/* Ferry */}
          {((facts.pt_stop_ferry ?? 0) > 0) ? (
            <div style={{ padding: '8px 10px', borderRadius: '6px', backgroundColor: '#1a2a3a' }}>
              <div style={{ fontSize: '18px', marginBottom: '2px' }}>⛴️</div>
              <div style={{ color: '#3498db', fontSize: '13px', fontWeight: 600 }}>
                {facts.pt_stop_ferry} ferry stop{(facts.pt_stop_ferry ?? 0) > 1 ? 's' : ''}
              </div>
              <div style={{ color: '#9ca0aa', fontSize: '11px' }}>CityCat / ferry service</div>
            </div>
          ) : (
            <div style={{ padding: '8px 10px', borderRadius: '6px', backgroundColor: '#2a3040' }}>
              <div style={{ fontSize: '18px', marginBottom: '2px' }}>⛴️</div>
              <div style={{ color: '#4b566a', fontSize: '13px' }}>No ferry access</div>
            </div>
          )}

          {/* Tram (only show if present — Brisbane has none) */}
          {(facts.pt_stop_tram ?? 0) > 0 && (
            <div style={{ padding: '8px 10px', borderRadius: '6px', backgroundColor: '#1a3a2a' }}>
              <div style={{ fontSize: '18px', marginBottom: '2px' }}>🚊</div>
              <div style={{ color: '#2ecc71', fontSize: '13px', fontWeight: 600 }}>
                {facts.pt_stop_tram} tram stop{(facts.pt_stop_tram ?? 0) > 1 ? 's' : ''}
              </div>
            </div>
          )}

          {/* Bus */}
          <div style={{ padding: '8px 10px', borderRadius: '6px', backgroundColor: (facts.pt_stop_bus ?? 0) > 10 ? '#2a2a1a' : '#2a3040' }}>
            <div style={{ fontSize: '18px', marginBottom: '2px' }}>🚌</div>
            {(facts.pt_stop_bus ?? 0) > 0 ? (
              <div style={{ color: (facts.pt_stop_bus ?? 0) > 20 ? '#f39c12' : '#9ca0aa', fontSize: '13px', fontWeight: 600 }}>
                {facts.pt_stop_bus} bus stops
              </div>
            ) : (
              <div style={{ color: '#4b566a', fontSize: '13px' }}>No bus stops</div>
            )}
            <div style={{ color: '#4b566a', fontSize: '11px' }}>Route count coming soon</div>
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
  const allSchools = [...schoolsIn, ...schoolsAdj]

  // Find the best schools by percentile
  const top5Schools  = allSchools.filter(s => s.icsea_percentile != null && s.icsea_percentile >= 95)
  const top10Schools = allSchools.filter(s => s.icsea_percentile != null && s.icsea_percentile >= 90 && s.icsea_percentile < 95)
  const top15Schools = allSchools.filter(s => s.icsea_percentile != null && s.icsea_percentile >= 85 && s.icsea_percentile < 90)
  const top25Schools = allSchools.filter(s => s.icsea_percentile != null && s.icsea_percentile >= 75 && s.icsea_percentile < 85)
  const bestSchools  = [...top5Schools, ...top10Schools, ...top15Schools, ...top25Schools]
  const bestInSuburb = schoolsIn.filter(s => s.icsea_percentile != null && s.icsea_percentile >= 75)
  const bestAdj      = schoolsAdj.filter(s => s.icsea_percentile != null && s.icsea_percentile >= 75)

  // Build investment analysis from actual school data, not just the score bucket
  let analysis = ''

  if (top5Schools.length > 0) {
    const names = top5Schools.map(s => s.name).join(' and ')
    const location = top5Schools.every(s => schoolsIn.includes(s)) ? 'in this suburb' : 'adjacent to this suburb'
    analysis = `Elite school catchment — ${names} ranks in the Top 5% of all Australian schools (ICSEA ${top5Schools[0].icsea?.toFixed(0)}). Being ${location} is a powerful and durable property value driver. Families commit to long-term home ownership to secure access to schools at this level, producing sustained demand and price resilience that outperforms the broader market.`
  } else if (top10Schools.length > 0) {
    const names = top10Schools.map(s => s.name).join(' and ')
    analysis = `Strong school catchment — ${names} places in the Top 10% nationally. This is a meaningful investment signal: quality school access reliably attracts family buyers willing to pay above-market prices to secure a catchment. Properties within the school zone typically trade at a measurable premium to the suburb median.`
  } else if (top15Schools.length > 0) {
    const names = top15Schools.slice(0, 2).map(s => s.name).join(' and ')
    analysis = `Above-average school access — ${names} ranks in the Top 15% nationally. School quality at this level is a genuine investment differentiator for the family buyer segment, which makes long-term residential decisions based on catchment access. Expect a catchment premium on properties within zone.`
  } else if (bestSchools.length > 0) {
    const n = bestSchools.length
    analysis = `This area has ${n} above-average school${n > 1 ? 's' : ''} (Top 25% nationally) within or adjacent to the suburb. Families with school-age children represent the most motivated and financially committed buyer segment — quality school access supports both demand and price stability.`
  } else if ((score ?? 0) >= 5.5) {
    analysis = `Schools nearby are around the national average. School quality is not a strong differentiator here — it won't deter buyers, but it's also not driving the premium that elite school catchments produce. Investors should focus on other fundamentals for this suburb.`
  } else {
    analysis = `Below-average school quality reduces demand from the most motivated buyer segment — families with school-age children. This limits the buyer pool and constrains capital growth compared to stronger school catchment suburbs. Rental demand may still be solid from professional renters who prioritise other factors.`
  }

  // Add context about in-suburb vs adjacent distinction
  if (bestAdj.length > 0 && bestInSuburb.length === 0 && top5Schools.length === 0 && top10Schools.length === 0) {
    const adjNames = bestAdj.slice(0, 2).map(s => s.name).join(', ')
    analysis += ` Note: the highest-rated schools (${adjNames}) are in adjacent suburbs — confirm zone boundaries before making catchment-based investment decisions.`
  }

  function sectorColor(sector: string | null) {
    if (sector === 'Government')   return { bg: '#1a3a4a', color: '#7ec8e3' }
    if (sector === 'Catholic')     return { bg: '#3a2a1a', color: '#e6a845' }
    if (sector === 'Independent')  return { bg: '#2a3a1a', color: '#90d870' }
    return { bg: '#343b47', color: '#9ca0aa' }
  }

  function ratingColor(rating: string | null) {
    if (!rating) return '#9ca0aa'
    const pct = parseInt(rating.replace(/[^0-9]/g, '') || '100')
    if (rating.startsWith('Top')) {
      if (pct <= 5)  return '#2ecc71'   // Top 5% — bright green
      if (pct <= 10) return '#27ae60'   // Top 10% — green
      if (pct <= 15) return '#a8e063'   // Top 15% — light green
      if (pct <= 25) return '#f1c40f'   // Top 25% — yellow
      if (pct <= 35) return '#f39c12'   // Top 35% — amber
      return '#e67e22'                   // Top 50% — orange
    }
    return '#e74c3c'                     // Bottom bands — red
  }

  const renderSchool = (s: SchoolEntry, i: number) => {
    const sc = sectorColor(s.sector)
    return (
      <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #3a4050', flexWrap: 'wrap', gap: '6px' }}>
        <div style={{ flex: 1, minWidth: '200px' }}>
          <div style={{ color: '#f8f8f2', fontSize: '14px', fontWeight: 500 }}>{s.name}</div>
          <div style={{ display: 'flex', gap: '6px', marginTop: '4px', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', backgroundColor: sc.bg, color: sc.color }}>{s.sector}</span>
            <span style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', backgroundColor: '#343b47', color: '#9ca0aa' }}>{s.school_type}</span>
            {s.total_enrolments && <span style={{ fontSize: '11px', color: '#9ca0aa' }}>{s.total_enrolments.toLocaleString()} students</span>}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          {s.rating && (
            <div style={{ fontSize: '13px', fontWeight: 700, color: ratingColor(s.rating) }}>{s.rating}</div>
          )}
          {s.icsea && <div style={{ fontSize: '11px', color: '#9ca0aa' }}>ICSEA {s.icsea.toFixed(0)}</div>}
        </div>
      </div>
    )
  }

  return (
    <>
      <Analysis>{analysis}</Analysis>
      {schoolsIn.length > 0 && (
        <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '16px', marginBottom: '14px' }}>
          <div style={{ fontSize: '12px', color: '#9ca0aa', marginBottom: '2px', textTransform: 'uppercase', letterSpacing: '1px' }}>Schools in this suburb</div>
          {schoolsIn.map(renderSchool)}
        </div>
      )}
      {schoolsAdj.length > 0 && (
        <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '16px' }}>
          <div style={{ fontSize: '12px', color: '#9ca0aa', marginBottom: '2px', textTransform: 'uppercase', letterSpacing: '1px' }}>Schools in adjacent suburbs</div>
          <div style={{ fontSize: '12px', color: '#4b566a', marginBottom: '8px' }}>These are within the broader catchment area</div>
          {schoolsAdj.map(renderSchool)}
        </div>
      )}
      {schoolsIn.length === 0 && schoolsAdj.length === 0 && (
        <p style={{ color: '#9ca0aa', fontSize: '14px' }}>School data not available for this suburb.</p>
      )}
      <div style={{ fontSize: '12px', color: '#4b566a', fontStyle: 'italic', marginTop: '8px' }}>
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
          <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '14px' }}>
            <div style={{ color: '#9ca0aa', fontSize: '12px', marginBottom: '4px' }}>Median age</div>
            <div style={{ color: '#f8f8f2', fontSize: '24px', fontWeight: 700 }}>{medianAge.toFixed(0)}</div>
          </div>
        )}
        {degree != null && (
          <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '14px' }}>
            <div style={{ color: '#9ca0aa', fontSize: '12px', marginBottom: '4px' }}>University degree</div>
            <div style={{ color: '#f8f8f2', fontSize: '24px', fontWeight: 700 }}>{degree.toFixed(1)}%</div>
          </div>
        )}
        {profess != null && (
          <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '14px' }}>
            <div style={{ color: '#9ca0aa', fontSize: '12px', marginBottom: '4px' }}>Professionals & managers</div>
            <div style={{ color: '#f8f8f2', fontSize: '24px', fontWeight: 700 }}>{profess.toFixed(1)}%</div>
          </div>
        )}
        {unemp != null && (
          <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '14px' }}>
            <div style={{ color: '#9ca0aa', fontSize: '12px', marginBottom: '4px' }}>Unemployment rate</div>
            <div style={{ color: unemp > 8 ? '#e74c3c' : unemp > 5 ? '#f39c12' : '#2ecc71', fontSize: '24px', fontWeight: 700 }}>{unemp.toFixed(1)}%</div>
          </div>
        )}
      </div>
      <div style={{ fontSize: '12px', color: '#4b566a', fontStyle: 'italic' }}>
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
      <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '16px', marginBottom: '14px' }}>
        <div style={{ fontSize: '12px', color: '#9ca0aa', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '1px' }}>Dwelling types</div>
        {[
          { label: 'Detached houses', value: houses, color: '#3498db' },
          { label: 'Townhouses / semi-detached', value: townhouse, color: '#9b59b6' },
          { label: 'Flats & apartments (total)', value: flats, color: '#e67e22' },
          { label: '  └ Low-rise (1–2 storey)', value: lowRise, color: '#d4995a', indent: true },
          { label: '  └ Mid-rise (3–8 storey)', value: midRise, color: '#c8804a', indent: true },
          { label: '  └ High-rise (9+ storey)', value: highRise, color: '#c06030', indent: true },
        ].filter(r => r.value != null && r.value > 0).map(({ label, value, color, indent }) => (
          <div key={label} style={{ marginBottom: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: indent ? '12px' : '13px', marginBottom: '3px' }}>
              <span style={{ color: indent ? '#9ca0aa' : '#d1d5da' }}>{label}</span>
              <span style={{ color, fontWeight: 600 }}>{value!.toFixed(1)}%</span>
            </div>
            <div style={{ height: indent ? '3px' : '5px', backgroundColor: '#4b566a', borderRadius: '2px' }}>
              <div style={{ height: '100%', width: `${value}%`, backgroundColor: color, borderRadius: '2px', opacity: indent ? 0.7 : 1 }} />
            </div>
          </div>
        ))}
      </div>

      {/* Financial stress */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', marginBottom: '14px' }}>
        {mortgageStress != null && (
          <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '12px 16px', flex: 1, minWidth: '140px' }}>
            <div style={{ color: '#9ca0aa', fontSize: '12px', marginBottom: '4px' }}>Mortgage stress</div>
            <div style={{ color: mortgageStress > 15 ? '#e74c3c' : mortgageStress > 10 ? '#f39c12' : '#2ecc71', fontSize: '22px', fontWeight: 700 }}>{mortgageStress.toFixed(1)}%</div>
          </div>
        )}
        {rentStress != null && (
          <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '12px 16px', flex: 1, minWidth: '140px' }}>
            <div style={{ color: '#9ca0aa', fontSize: '12px', marginBottom: '4px' }}>Rent stress</div>
            <div style={{ color: rentStress > 25 ? '#e74c3c' : rentStress > 15 ? '#f39c12' : '#2ecc71', fontSize: '22px', fontWeight: 700 }}>{rentStress.toFixed(1)}%</div>
          </div>
        )}
        {renters != null && (
          <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '12px 16px', flex: 1, minWidth: '140px' }}>
            <div style={{ color: '#9ca0aa', fontSize: '12px', marginBottom: '4px' }}>Renters</div>
            <div style={{ color: '#f8f8f2', fontSize: '22px', fontWeight: 700 }}>{renters.toFixed(1)}%</div>
          </div>
        )}
        {socialHousing != null && (
          <div style={{ backgroundColor: '#343b47', borderRadius: '8px', padding: '12px 16px', flex: 1, minWidth: '140px' }}>
            <div style={{ color: '#9ca0aa', fontSize: '12px', marginBottom: '4px' }}>Social housing</div>
            <div style={{ color: socialHousing > 15 ? '#e74c3c' : '#f8f8f2', fontSize: '22px', fontWeight: 700 }}>{socialHousing.toFixed(1)}%</div>
          </div>
        )}
      </div>
      <div style={{ fontSize: '12px', color: '#4b566a', fontStyle: 'italic' }}>
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

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '0 20px 80px' }}>
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

function ReadyView({ data, onNavigateSA2 }: { data: GroupReport; onNavigateSA2: (p: string) => void }) {
  const { suburb_name, state: stateCode, scores, facts, intermediates, insight, risk_flags, tags,
    sa2_count, sa2_names, sa2_codes, sa2_breakdown, population,
    schools_in_suburb, schools_adjacent, adjacent_has_train, adjacent_train_suburbs,
    universities_nearby, hospitals_nearby, cbd_distance_km, cbd_city, commute_times,
    rank, peer_suburbs } = data
  const isMulti = sa2_count > 1

  return (
    <>
      {/* Header */}
      <div style={{ marginBottom: '32px' }}>
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '12px', flexWrap: 'wrap' }}>
          <h1 style={{ fontSize: '42px', margin: 0 }}>{suburb_name}</h1>
          <span style={{ color: '#9ca0aa', fontSize: '22px' }}>{stateCode}</span>
        </div>
        <div style={{ display: 'flex', gap: '16px', alignItems: 'center', marginTop: '4px', flexWrap: 'wrap' }}>
          {population && <p style={{ color: '#9ca0aa', margin: 0, fontSize: '13px' }}>{population.toLocaleString()} residents</p>}
          {cbd_distance_km != null && cbd_city && (
            <p style={{ color: '#9ca0aa', margin: 0, fontSize: '13px' }}>
              📍 <span style={{ color: '#d1d5da' }}>{cbd_distance_km}km</span> from {cbd_city} CBD
            </p>
          )}
        </div>
        {tags.length > 0 && (
          <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginTop: '12px' }}>
            {tags.map(t => <span key={t} style={{ padding: '4px 12px', backgroundColor: '#2a3a4a', color: '#7ec8e3', borderRadius: '20px', fontSize: '12px', fontWeight: 600 }}>{t}</span>)}
          </div>
        )}
      </div>

      {/* ABS split notice */}
      {isMulti && (
        <div style={{ backgroundColor: '#2a3040', border: '1px solid #4b566a', borderRadius: '8px', padding: '12px 18px', marginBottom: '24px', display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
          <span>ℹ️</span>
          <div style={{ fontSize: '14px', color: '#d1d5da' }}>
            <strong>{suburb_name}</strong> spans {sa2_count} ABS statistical areas — scores are population-weighted averages. Each intelligence section shows individual area comparisons.
            <div style={{ display: 'flex', gap: '8px', marginTop: '8px', flexWrap: 'wrap' }}>
              {sa2_codes.map((code, i) => (
                <button key={code} onClick={() => onNavigateSA2(`/suburb/${code}`)}
                  style={{ padding: '3px 10px', backgroundColor: '#343b47', color: '#9ca0aa', border: '1px solid #4b566a', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' }}>
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
          <div style={{ fontSize: '72px', fontWeight: 800, color: scoreColor(scores.investment_score), lineHeight: 1 }}>{fv(scores.investment_score)}</div>
          <div style={{ color: '#9ca0aa', fontSize: '13px' }}>out of 10</div>
        </div>
        <div style={{ flex: 1, color: '#d1d5da', fontSize: '16px', lineHeight: 1.7 }}>{insight}</div>
      </div>

      {/* Percentile rank bar */}
      {rank && (
        <div style={{ backgroundColor: '#1e2530', border: '1px solid #4b566a', borderRadius: '10px', padding: '18px 24px', marginBottom: '24px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px', flexWrap: 'wrap', gap: '8px' }}>
            <div style={{ color: '#d1d5da', fontSize: '14px' }}>
              <strong style={{ color: '#f8f8f2' }}>#{rank.national_rank}</strong>
              <span style={{ color: '#9ca0aa' }}> of {rank.national_total.toLocaleString()} suburbs nationally</span>
              <span style={{ margin: '0 10px', color: '#4b566a' }}>·</span>
              <strong style={{ color: '#f8f8f2' }}>#{rank.state_rank}</strong>
              <span style={{ color: '#9ca0aa' }}> of {rank.state_total.toLocaleString()} in {stateCode}</span>
            </div>
            <span style={{
              padding: '3px 12px', borderRadius: '20px', fontSize: '12px', fontWeight: 700,
              backgroundColor: rank.national_pct >= 75 ? '#1a3a1a' : rank.national_pct >= 50 ? '#2a2a1a' : '#3a2a1a',
              color: rank.national_pct >= 75 ? '#2ecc71' : rank.national_pct >= 50 ? '#f39c12' : '#e67e22',
            }}>Top {(100 - rank.national_pct + 0.1).toFixed(0)}% nationally</span>
          </div>
          {/* Rank bar */}
          <div style={{ position: 'relative', height: '8px', backgroundColor: '#343b47', borderRadius: '4px' }}>
            <div style={{
              position: 'absolute', left: 0, top: 0, height: '100%',
              width: `${rank.national_pct}%`,
              background: 'linear-gradient(to right, #e74c3c, #f39c12, #2ecc71)',
              borderRadius: '4px',
            }} />
            <div style={{
              position: 'absolute', top: '-3px',
              left: `calc(${rank.national_pct}% - 7px)`,
              width: '14px', height: '14px',
              backgroundColor: scoreColor(scores.investment_score),
              border: '2px solid #1e2530',
              borderRadius: '50%',
            }} />
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: '#4b566a', marginTop: '4px' }}>
            <span>Lowest</span><span>Highest</span>
          </div>
        </div>
      )}

      {/* Score Breakdown — clean cards */}
      <h2 style={{ fontSize: '22px', marginBottom: '16px' }}>Score Breakdown</h2>
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
        <div style={{ marginBottom: '48px' }}>
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

      {/* Investment Intelligence */}
      <h2 style={{ fontSize: '22px', marginBottom: '8px' }}>Investment Intelligence</h2>
      <p style={{ color: '#9ca0aa', fontSize: '14px', marginBottom: '28px' }}>
        What each score means for your investment decision — and what the data is telling you.
      </p>

      <IntelPanel emoji="🏙️" label="Liveability"    dimKey="liveability_score"    score={scores.liveability_score}    sa2Breakdown={sa2_breakdown} isMulti={isMulti}>
        <LiveabilitySection score={scores.liveability_score} facts={facts} adjacentHasTrain={adjacent_has_train} adjacentTrainSuburbs={adjacent_train_suburbs} universitiesNearby={universities_nearby || []} hospitalsNearby={hospitals_nearby || []} commuteTimes={commute_times} cbdCity={cbd_city} />
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

      {/* Peer suburbs */}
      {peer_suburbs && peer_suburbs.length > 0 && (
        <div style={{ marginBottom: '48px' }}>
          <h2 style={{ fontSize: '22px', marginBottom: '8px' }}>Similar Suburbs in {stateCode}</h2>
          <p style={{ color: '#9ca0aa', fontSize: '14px', marginBottom: '16px' }}>
            Suburbs with comparable investment profiles — useful for benchmarking or finding alternatives.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px' }}>
            {peer_suburbs.map(p => (
              <a key={p.suburb_id} href={`/suburb-group/${p.suburb_id}`} style={{ textDecoration: 'none' }}>
                <div style={{ backgroundColor: '#343b47', border: '1px solid #4b566a', borderRadius: '10px', padding: '16px', cursor: 'pointer' }}>
                  <div style={{ fontWeight: 600, color: '#f8f8f2', fontSize: '15px', marginBottom: '4px' }}>{p.suburb_name}</div>
                  <div style={{ color: '#9ca0aa', fontSize: '12px', marginBottom: '10px' }}>{p.state}{p.population ? ` · ${p.population.toLocaleString()}` : ''}</div>
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <span style={{ fontSize: '22px', fontWeight: 800, color: scoreColor(p.investment_score) }}>{fv(p.investment_score)}</span>
                    <div style={{ flex: 1 }}>
                      {(['liveability_score', 'growth_score', 'education_score'] as const).map(k => (
                        <div key={k} style={{ display: 'flex', alignItems: 'center', gap: '4px', marginBottom: '2px' }}>
                          <div style={{ fontSize: '10px', color: '#9ca0aa', width: '54px' }}>{k.replace('_score','').replace('liveability','livab.').replace('education','educ.')}</div>
                          <div style={{ flex: 1, height: '3px', backgroundColor: '#4b566a', borderRadius: '2px' }}>
                            <div style={{ height: '100%', width: `${(p[k] ?? 0) * 10}%`, backgroundColor: scoreColor(p[k]), borderRadius: '2px' }} />
                          </div>
                          <div style={{ fontSize: '10px', color: scoreColor(p[k]), width: '22px', textAlign: 'right' }}>{fv(p[k])}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </a>
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
