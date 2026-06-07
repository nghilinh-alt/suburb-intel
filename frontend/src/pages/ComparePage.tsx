import { useState, useEffect } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Legend, Tooltip
} from 'recharts'
import SeverityBadge from '../components/SeverityBadge'
import { usePageTitle } from '../hooks/usePageTitle'

// ── Types ──────────────────────────────────────────────────────────────────

interface SuburbReport {
  sa2_code: string
  sa2_name: string | null
  state: string | null
  scores: Record<string, number | null>
  facts: Record<string, number | null>
  intermediates: Record<string, number | null>
  risk_flags: string[]
  tags: string[]
  insight: string
}

interface CompareResponse {
  suburb_a: SuburbReport
  suburb_b: SuburbReport
  deltas: Record<string, number>
}

interface SearchResult {
  sa2_code: string
  sa2_name: string
  state: string
  population: number | null
}

const DIMENSIONS = [
  { key: 'investment_score',     label: 'Investment'    },
  { key: 'liveability_score',    label: 'Liveability'  },
  { key: 'growth_score',         label: 'Growth'       },
  { key: 'education_score',      label: 'Education'    },
  { key: 'demographic_score',    label: 'Demographics' },
  { key: 'housing_score',        label: 'Housing'      },
  { key: 'infrastructure_score', label: 'Infrastructure' },
]

function scoreColor(v: number | null): string {
  if (v == null) return '#6b7fa0'
  if (v >= 7) return '#34d399'
  if (v >= 5) return '#fbbf24'
  return '#fb7185'
}

// ── Sub-components ─────────────────────────────────────────────────────────

function SuburbPicker({
  label, value, onSelect,
}: { label: string; value: SearchResult | null; onSelect: (r: SearchResult) => void }) {
  const [query, setQuery]     = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [open, setOpen]       = useState(false)

  useEffect(() => {
    if (query.length < 2) { setResults([]); return }
    const timer = setTimeout(() => {
      fetch(`/api/search/?query=${encodeURIComponent(query)}&limit=8`)
        .then(r => r.json())
        .then(d => setResults(Array.isArray(d) ? d : [d]))
        .catch(() => setResults([]))
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  function pick(r: SearchResult) {
    onSelect(r)
    setQuery('')
    setResults([])
    setOpen(false)
  }

  return (
    <div style={{ flex: 1, minWidth: '240px', position: 'relative' }}>
      <div style={{ fontSize: '12px', color: '#6b7fa0', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.07em', fontWeight: 500 }}>
        {label}
      </div>
      {value ? (
        <div style={{ backgroundColor: '#151b27', border: '1px solid #28334a', borderRadius: '10px', padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 700, color: '#cdd8e8' }}>{value.sa2_name}</div>
            <div style={{ color: '#6b7fa0', fontSize: '13px' }}>{value.state} · SA2 {value.sa2_code}</div>
          </div>
          <button onClick={() => onSelect({ sa2_code: '', sa2_name: '', state: '', population: null })}
            style={{ background: 'none', border: 'none', color: '#6b7fa0', cursor: 'pointer', fontSize: '18px' }}>✕</button>
        </div>
      ) : (
        <div>
          <input value={query} onChange={e => { setQuery(e.target.value); setOpen(true) }}
            placeholder="Search suburb…"
            style={{ width: '100%', boxSizing: 'border-box', padding: '12px 16px', backgroundColor: '#151b27', color: '#cdd8e8', border: '1px solid #28334a', borderRadius: '10px', fontSize: '15px', outline: 'none' }} />
          {open && results.length > 0 && (
            <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100, backgroundColor: '#151b27', border: '1px solid #28334a', borderRadius: '10px', overflow: 'hidden', marginTop: '4px', boxShadow: '0 8px 24px rgba(0,0,0,0.5)' }}>
              {results.map(r => (
                <button key={r.sa2_code} onClick={() => pick(r)}
                  style={{ width: '100%', textAlign: 'left', padding: '10px 16px', backgroundColor: 'transparent', border: 'none', borderBottom: '1px solid #1e2638', color: '#cdd8e8', cursor: 'pointer' }}>
                  <span style={{ fontWeight: 600 }}>{r.sa2_name}</span>
                  <span style={{ color: '#6b7fa0', marginLeft: '8px', fontSize: '13px' }}>{r.state}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function DeltaBadge({ delta }: { delta: number }) {
  if (Math.abs(delta) < 0.05) return <span style={{ color: '#6b7fa0' }}>≈</span>
  const positive = delta > 0
  return (
    <span style={{ color: positive ? '#34d399' : '#fb7185', fontWeight: 700, fontSize: '12px' }}>
      {positive ? '▲' : '▼'} {Math.abs(delta).toFixed(1)}
    </span>
  )
}

function FactCompare({ label, a, b, fmt = (v: number | null) => v?.toFixed(1) ?? '—' }: {
  label: string
  a: number | null
  b: number | null
  fmt?: (v: number | null) => string
}) {
  const aWins = a != null && b != null && a > b
  const bWins = a != null && b != null && b > a
  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px 1fr', gap: '8px', padding: '9px 0', borderBottom: '1px solid #1e2638', alignItems: 'center' }}>
      <div style={{ textAlign: 'right', fontWeight: aWins ? 700 : 400, color: aWins ? '#cdd8e8' : '#6b7fa0' }}>{fmt(a)}</div>
      <div style={{ textAlign: 'center', color: '#6b7fa0', fontSize: '12px' }}>{label}</div>
      <div style={{ textAlign: 'left', fontWeight: bWins ? 700 : 400, color: bWins ? '#cdd8e8' : '#6b7fa0' }}>{fmt(b)}</div>
    </div>
  )
}

// ── Page ───────────────────────────────────────────────────────────────────

export default function ComparePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [suburbA, setSuburbA] = useState<SearchResult | null>(null)
  const [suburbB, setSuburbB] = useState<SearchResult | null>(null)
  const [data, setData]       = useState<CompareResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError]     = useState<string | null>(null)
  usePageTitle(data ? `${data.suburb_a.sa2_name} vs ${data.suburb_b.sa2_name}` : 'Compare Suburbs')

  useEffect(() => {
    const a = searchParams.get('a')
    const b = searchParams.get('b')
    if (a) setSuburbA({ sa2_code: a, sa2_name: a, state: '', population: null })
    if (b) setSuburbB({ sa2_code: b, sa2_name: b, state: '', population: null })
  }, [])

  useEffect(() => {
    if (!suburbA?.sa2_code || !suburbB?.sa2_code) { setData(null); return }
    setLoading(true)
    setError(null)
    setSearchParams({ a: suburbA.sa2_code, b: suburbB.sa2_code })
    fetch(`/api/compare/?a=${suburbA.sa2_code}&b=${suburbB.sa2_code}`)
      .then(async r => {
        if (!r.ok) throw new Error((await r.json().catch(() => null))?.detail || 'Compare failed')
        return r.json() as Promise<CompareResponse>
      })
      .then(d => {
        setSuburbA(prev => prev ? { ...prev, sa2_name: d.suburb_a.sa2_name ?? prev.sa2_name, state: d.suburb_a.state ?? '' } : null)
        setSuburbB(prev => prev ? { ...prev, sa2_name: d.suburb_b.sa2_name ?? prev.sa2_name, state: d.suburb_b.state ?? '' } : null)
        setData(d)
      })
      .catch(e => setError(e instanceof Error ? e.message : 'Error'))
      .finally(() => setLoading(false))
  }, [suburbA?.sa2_code, suburbB?.sa2_code])

  const radarData = data
    ? DIMENSIONS.map(d => ({
        dimension: d.label,
        [data.suburb_a.sa2_name ?? 'A']: data.suburb_a.scores[d.key] ?? 0,
        [data.suburb_b.sa2_name ?? 'B']: data.suburb_b.scores[d.key] ?? 0,
      }))
    : []

  const nameA = data?.suburb_a.sa2_name ?? 'Suburb A'
  const nameB = data?.suburb_b.sa2_name ?? 'Suburb B'

  const panel = (children: React.ReactNode, title?: string) => (
    <div style={{ backgroundColor: '#151b27', border: '1px solid #28334a', borderRadius: '12px', padding: '24px', marginBottom: '24px', boxShadow: '0 2px 12px rgba(0,0,0,0.45)' }}>
      {title && <h3 style={{ fontSize: '16px', fontWeight: 700, marginTop: 0, marginBottom: '16px', color: '#cdd8e8' }}>{title}</h3>}
      {children}
    </div>
  )

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '36px', fontWeight: 800, marginBottom: '8px', color: '#cdd8e8', letterSpacing: '-0.03em' }}>Compare Suburbs</h1>
      <p style={{ color: '#6b7fa0', marginBottom: '28px', fontSize: '15px' }}>
        Side-by-side investment profile comparison across all 7 scoring dimensions.
      </p>

      {/* Pickers */}
      <div style={{ display: 'flex', gap: '24px', marginBottom: '32px', flexWrap: 'wrap', alignItems: 'center' }}>
        <SuburbPicker label="Suburb A" value={suburbA} onSelect={r => r.sa2_code ? setSuburbA(r) : setSuburbA(null)} />
        <div style={{ color: '#6b7fa0', fontSize: '20px', fontWeight: 700, paddingTop: '22px' }}>vs</div>
        <SuburbPicker label="Suburb B" value={suburbB} onSelect={r => r.sa2_code ? setSuburbB(r) : setSuburbB(null)} />
      </div>

      {loading && <p style={{ color: '#6b7fa0' }}>Comparing…</p>}
      {error   && <p style={{ color: '#fb7185' }}>{error}</p>}

      {!suburbA && !suburbB && (
        <div style={{ backgroundColor: '#151b27', borderRadius: '12px', border: '1px solid #28334a', padding: '40px 32px', textAlign: 'center' }}>
          <p style={{ color: '#6b7fa0', fontSize: '15px', marginBottom: '24px', marginTop: 0 }}>
            Search and select two suburbs above to compare their investment profiles.
          </p>
          <div style={{ fontSize: '13px', color: '#6b7fa0', marginBottom: '12px' }}>Try these pairs:</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', justifyContent: 'center' }}>
            {[
              { a: '301011072', b: '305031293', label: 'Tarneit vs Werribee' },
              { a: '129011426', b: '121041253', label: 'Parramatta vs Surry Hills' },
              { a: '305021243', b: '305031292', label: 'Footscray vs Sunshine' },
            ].map(({ a, b, label }) => (
              <button key={label} onClick={() => {
                setSuburbA({ sa2_code: a, sa2_name: a, state: '', population: null })
                setSuburbB({ sa2_code: b, sa2_name: b, state: '', population: null })
              }} style={{
                padding: '9px 18px', backgroundColor: '#1e2638', color: '#9aafc8',
                border: '1px solid #28334a', borderRadius: '8px', cursor: 'pointer', fontSize: '13px',
              }}>
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {data && !loading && (
        <>
          {/* Score header */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: '16px', marginBottom: '24px' }}>
            {[data.suburb_a, data.suburb_b].map((s, i) => (
              <div key={i} style={{ backgroundColor: '#151b27', border: '1px solid #28334a', borderRadius: '12px', padding: '20px 24px', textAlign: i === 0 ? 'right' : 'left', boxShadow: '0 2px 12px rgba(0,0,0,0.45)' }}>
                <div style={{ fontWeight: 700, fontSize: '18px', color: '#cdd8e8' }}>{s.sa2_name}</div>
                <div style={{ color: '#6b7fa0', fontSize: '13px', marginBottom: '10px' }}>{s.state}</div>
                <div style={{ fontSize: '52px', fontWeight: 800, color: scoreColor(s.scores.investment_score ?? null), letterSpacing: '-0.04em', lineHeight: 1 }}>
                  {s.scores.investment_score?.toFixed(1) ?? '—'}
                </div>
                <div style={{ color: '#6b7fa0', fontSize: '12px', marginTop: '4px', marginBottom: '8px' }}>investment score</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px', justifyContent: i === 0 ? 'flex-end' : 'flex-start' }}>
                  {s.tags.slice(0, 2).map(t => (
                    <span key={t} style={{ padding: '3px 10px', backgroundColor: 'rgba(45,212,191,0.1)', color: '#2dd4bf', borderRadius: '99px', fontSize: '11px', fontWeight: 600, border: '1px solid rgba(45,212,191,0.2)' }}>{t}</span>
                  ))}
                </div>
              </div>
            ))}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#6b7fa0', fontSize: '20px', fontWeight: 700 }}>vs</div>
          </div>

          {/* Radar chart */}
          {panel(
            <>
              <ResponsiveContainer width="100%" height={380}>
                <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
                  <PolarGrid stroke="#28334a" />
                  <PolarAngleAxis dataKey="dimension" tick={{ fill: '#6b7fa0', fontSize: 12 }} />
                  <PolarRadiusAxis domain={[0, 10]} tick={false} axisLine={false} />
                  <Radar name={nameA} dataKey={nameA} stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.2} />
                  <Radar name={nameB} dataKey={nameB} stroke="#fb7185" fill="#fb7185" fillOpacity={0.2} />
                  <Legend wrapperStyle={{ color: '#9aafc8', fontSize: '13px' }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#151b27', border: '1px solid #28334a', borderRadius: '8px', color: '#cdd8e8', fontSize: '12px' }}
                    formatter={(v: unknown) => (v as number).toFixed(1)}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </>,
            'Dimension Comparison'
          )}

          {/* Score table */}
          {panel(
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 160px 1fr', gap: '8px', marginBottom: '8px', fontSize: '12px', color: '#6b7fa0', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                <div style={{ textAlign: 'right' }}>{nameA}</div>
                <div style={{ textAlign: 'center' }}>Dimension</div>
                <div>{nameB}</div>
              </div>
              {DIMENSIONS.map(dim => {
                const va = data.suburb_a.scores[dim.key]
                const vb = data.suburb_b.scores[dim.key]
                const delta = data.deltas[dim.key] ?? 0
                const aWins = (va ?? 0) > (vb ?? 0)
                return (
                  <div key={dim.key} style={{ display: 'grid', gridTemplateColumns: '1fr 160px 1fr', gap: '8px', padding: '10px 0', borderBottom: '1px solid #1e2638', alignItems: 'center' }}>
                    <div style={{ textAlign: 'right', fontWeight: aWins ? 700 : 400, color: aWins ? '#38bdf8' : '#6b7fa0', fontSize: '18px' }}>
                      {va?.toFixed(1) ?? '—'}
                    </div>
                    <div style={{ textAlign: 'center' }}>
                      <div style={{ color: '#9aafc8', fontSize: '13px', marginBottom: '2px' }}>{dim.label}</div>
                      <DeltaBadge delta={delta} />
                    </div>
                    <div style={{ textAlign: 'left', fontWeight: !aWins ? 700 : 400, color: !aWins ? '#fb7185' : '#6b7fa0', fontSize: '18px' }}>
                      {vb?.toFixed(1) ?? '—'}
                    </div>
                  </div>
                )
              })}
            </>,
            'Score Breakdown'
          )}

          {/* Facts comparison */}
          {panel(
            <>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px 1fr', gap: '8px', marginBottom: '10px', fontSize: '12px', color: '#6b7fa0', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
                <div style={{ textAlign: 'right' }}>{nameA}</div>
                <div style={{ textAlign: 'center' }}></div>
                <div>{nameB}</div>
              </div>
              <FactCompare label="Population" a={data.suburb_a.facts.population} b={data.suburb_b.facts.population}
                fmt={v => v ? v.toLocaleString() : '—'} />
              <FactCompare label="Median income" a={data.suburb_a.facts.median_income} b={data.suburb_b.facts.median_income}
                fmt={v => v ? `$${Math.round(v).toLocaleString()}` : '—'} />
              <FactCompare label="Unemployment %" a={data.suburb_a.facts.unemployment_pct} b={data.suburb_b.facts.unemployment_pct} />
              <FactCompare label="Uni degree %" a={data.suburb_a.facts.uni_degree_pct} b={data.suburb_b.facts.uni_degree_pct} />
              <FactCompare label="Pop. growth to 2031 %" a={data.suburb_a.facts.pop_growth_proj_pct} b={data.suburb_b.facts.pop_growth_proj_pct} />
              <FactCompare label="Avg ICSEA (schools)" a={data.suburb_a.intermediates.edu_avg_icsea} b={data.suburb_b.intermediates.edu_avg_icsea}
                fmt={v => v ? v.toFixed(0) : '—'} />
              <FactCompare label="Hospital access score" a={data.suburb_a.intermediates.health_hospital_score} b={data.suburb_b.intermediates.health_hospital_score} />
            </>,
            'Key Facts'
          )}

          {/* Risk flags */}
          {(data.suburb_a.risk_flags.length > 0 || data.suburb_b.risk_flags.length > 0) && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              {[{ s: data.suburb_a, accent: '#38bdf8' }, { s: data.suburb_b, accent: '#fb7185' }].map(({ s, accent }) => (
                s.risk_flags.length > 0 ? (
                  <div key={s.sa2_code} style={{ backgroundColor: '#151b27', border: '1px solid #28334a', borderRadius: '12px', padding: '16px' }}>
                    <div style={{ fontSize: '13px', color: accent, marginBottom: '8px', fontWeight: 600 }}>{s.sa2_name} — Risk Flags</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {s.risk_flags.map(f => (
                        <SeverityBadge key={f} level="bad" label={f.replace(/_/g, ' ')} />
                      ))}
                    </div>
                  </div>
                ) : <div key={s.sa2_code} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
