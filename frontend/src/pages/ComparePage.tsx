import { useState, useEffect, useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'
import {
  RadarChart, Radar, PolarGrid, PolarAngleAxis, PolarRadiusAxis,
  ResponsiveContainer, Legend, Tooltip
} from 'recharts'

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
  { key: 'investment_score',    label: 'Investment'    },
  { key: 'liveability_score',   label: 'Liveability'  },
  { key: 'growth_score',        label: 'Growth'       },
  { key: 'education_score',     label: 'Education'    },
  { key: 'demographic_score',   label: 'Demographics' },
  { key: 'housing_score',       label: 'Housing'      },
  { key: 'infrastructure_score', label: 'Infrastructure' },
]

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
      <div style={{ fontSize: '12px', color: '#9ca0aa', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '1px' }}>
        {label}
      </div>
      {value ? (
        <div style={{ backgroundColor: '#343b47', border: '1px solid #4b566a', borderRadius: '8px', padding: '12px 16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <div style={{ fontWeight: 600 }}>{value.sa2_name}</div>
            <div style={{ color: '#9ca0aa', fontSize: '13px' }}>{value.state} · SA2 {value.sa2_code}</div>
          </div>
          <button onClick={() => onSelect({ sa2_code: '', sa2_name: '', state: '', population: null })}
            style={{ background: 'none', border: 'none', color: '#9ca0aa', cursor: 'pointer', fontSize: '18px' }}>✕</button>
        </div>
      ) : (
        <div>
          <input value={query} onChange={e => { setQuery(e.target.value); setOpen(true) }}
            placeholder="Search suburb…"
            style={{ width: '100%', boxSizing: 'border-box', padding: '12px 16px', backgroundColor: '#343b47', color: '#f8f8f2', border: '1px solid #4b566a', borderRadius: '8px', fontSize: '15px', outline: 'none' }} />
          {open && results.length > 0 && (
            <div style={{ position: 'absolute', top: '100%', left: 0, right: 0, zIndex: 100, backgroundColor: '#343b47', border: '1px solid #4b566a', borderRadius: '8px', overflow: 'hidden', marginTop: '2px' }}>
              {results.map(r => (
                <button key={r.sa2_code} onClick={() => pick(r)}
                  style={{ width: '100%', textAlign: 'left', padding: '10px 16px', backgroundColor: 'transparent', border: 'none', borderBottom: '1px solid #4b566a', color: '#f8f8f2', cursor: 'pointer' }}>
                  <span style={{ fontWeight: 600 }}>{r.sa2_name}</span>
                  <span style={{ color: '#9ca0aa', marginLeft: '8px', fontSize: '13px' }}>{r.state}</span>
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
  if (Math.abs(delta) < 0.05) return <span style={{ color: '#9ca0aa' }}>≈</span>
  const positive = delta > 0
  return (
    <span style={{ color: positive ? '#2ecc71' : '#e74c3c', fontWeight: 700, fontSize: '13px' }}>
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
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px 1fr', gap: '8px', padding: '8px 0', borderBottom: '1px solid #3a4050', alignItems: 'center' }}>
      <div style={{ textAlign: 'right', fontWeight: aWins ? 700 : 400, color: aWins ? '#f8f8f2' : '#9ca0aa' }}>{fmt(a)}</div>
      <div style={{ textAlign: 'center', color: '#9ca0aa', fontSize: '12px' }}>{label}</div>
      <div style={{ textAlign: 'left', fontWeight: bWins ? 700 : 400, color: bWins ? '#f8f8f2' : '#9ca0aa' }}>{fmt(b)}</div>
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

  // Restore from URL params on load
  useEffect(() => {
    const a = searchParams.get('a')
    const b = searchParams.get('b')
    if (a) setSuburbA({ sa2_code: a, sa2_name: a, state: '', population: null })
    if (b) setSuburbB({ sa2_code: b, sa2_name: b, state: '', population: null })
  }, [])

  // Fetch comparison when both are set
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
        // Update picker labels with real names
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

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '28px', marginBottom: '8px' }}>Compare Suburbs</h2>
      <p style={{ color: '#9ca0aa', marginBottom: '28px', fontSize: '14px' }}>
        Side-by-side investment profile comparison across all 7 scoring dimensions.
      </p>

      {/* Pickers */}
      <div style={{ display: 'flex', gap: '24px', marginBottom: '32px', flexWrap: 'wrap' }}>
        <SuburbPicker label="Suburb A" value={suburbA} onSelect={r => r.sa2_code ? setSuburbA(r) : setSuburbA(null)} />
        <div style={{ display: 'flex', alignItems: 'center', color: '#9ca0aa', fontSize: '24px', paddingTop: '24px' }}>vs</div>
        <SuburbPicker label="Suburb B" value={suburbB} onSelect={r => r.sa2_code ? setSuburbB(r) : setSuburbB(null)} />
      </div>

      {loading && <p style={{ color: '#9ca0aa' }}>Comparing…</p>}
      {error   && <p style={{ color: '#e74c3c' }}>{error}</p>}

      {!suburbA && !suburbB && (
        <div style={{ color: '#9ca0aa', fontSize: '15px', textAlign: 'center', padding: '60px', backgroundColor: '#343b47', borderRadius: '10px' }}>
          Search and select two suburbs above to compare their investment profiles.
        </div>
      )}

      {data && !loading && (
        <>
          {/* Score header */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr auto 1fr', gap: '16px', marginBottom: '32px' }}>
            {[data.suburb_a, data.suburb_b].map((s, i) => (
              <div key={i} style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '20px 24px', textAlign: i === 0 ? 'right' : 'left' }}>
                <div style={{ fontWeight: 700, fontSize: '18px' }}>{s.sa2_name}</div>
                <div style={{ color: '#9ca0aa', fontSize: '13px', marginBottom: '8px' }}>{s.state}</div>
                <div style={{ fontSize: '48px', fontWeight: 800, color: (s.scores.investment_score ?? 0) >= 6.5 ? '#2ecc71' : '#f39c12' }}>
                  {s.scores.investment_score?.toFixed(1) ?? '—'}
                </div>
                <div style={{ color: '#9ca0aa', fontSize: '12px' }}>investment score</div>
                {s.tags.slice(0, 2).map(t => (
                  <span key={t} style={{ display: 'inline-block', marginTop: '6px', marginRight: '6px', padding: '3px 10px', backgroundColor: '#2a3a4a', color: '#7ec8e3', borderRadius: '20px', fontSize: '11px' }}>{t}</span>
                ))}
              </div>
            ))}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#9ca0aa', fontSize: '20px', fontWeight: 700 }}>vs</div>
          </div>

          {/* Radar chart */}
          <div style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '24px', marginBottom: '32px' }}>
            <h3 style={{ fontSize: '16px', marginTop: 0, marginBottom: '16px' }}>Dimension Comparison</h3>
            <ResponsiveContainer width="100%" height={380}>
              <RadarChart data={radarData} margin={{ top: 10, right: 30, bottom: 10, left: 30 }}>
                <PolarGrid stroke="#4b566a" />
                <PolarAngleAxis dataKey="dimension" tick={{ fill: '#9ca0aa', fontSize: 12 }} />
                <PolarRadiusAxis domain={[0, 10]} tick={false} axisLine={false} />
                <Radar name={nameA} dataKey={nameA} stroke="#3498db" fill="#3498db" fillOpacity={0.25} />
                <Radar name={nameB} dataKey={nameB} stroke="#e74c3c" fill="#e74c3c" fillOpacity={0.25} />
                <Legend wrapperStyle={{ color: '#d1d5da', fontSize: '13px' }} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#343b47', border: '1px solid #4b566a', borderRadius: '6px', color: '#f8f8f2' }}
                  formatter={(v: number) => v.toFixed(1)}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>

          {/* Score table */}
          <div style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '24px', marginBottom: '32px' }}>
            <h3 style={{ fontSize: '16px', marginTop: 0, marginBottom: '16px' }}>Score Breakdown</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 160px 1fr', gap: '8px', marginBottom: '8px', fontSize: '12px', color: '#9ca0aa', textTransform: 'uppercase', letterSpacing: '1px' }}>
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
                <div key={dim.key} style={{ display: 'grid', gridTemplateColumns: '1fr 160px 1fr', gap: '8px', padding: '10px 0', borderBottom: '1px solid #3a4050', alignItems: 'center' }}>
                  <div style={{ textAlign: 'right', fontWeight: aWins ? 700 : 400, color: aWins ? '#3498db' : '#9ca0aa', fontSize: '18px' }}>
                    {va?.toFixed(1) ?? '—'}
                  </div>
                  <div style={{ textAlign: 'center' }}>
                    <div style={{ color: '#d1d5da', fontSize: '13px' }}>{dim.label}</div>
                    <DeltaBadge delta={delta} />
                  </div>
                  <div style={{ textAlign: 'left', fontWeight: !aWins ? 700 : 400, color: !aWins ? '#e74c3c' : '#9ca0aa', fontSize: '18px' }}>
                    {vb?.toFixed(1) ?? '—'}
                  </div>
                </div>
              )
            })}
          </div>

          {/* Facts comparison */}
          <div style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '24px', marginBottom: '32px' }}>
            <h3 style={{ fontSize: '16px', marginTop: 0, marginBottom: '16px' }}>Key Facts</h3>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 200px 1fr', gap: '8px', marginBottom: '8px', fontSize: '12px', color: '#9ca0aa', textTransform: 'uppercase', letterSpacing: '1px' }}>
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
          </div>

          {/* Risk flags */}
          {(data.suburb_a.risk_flags.length > 0 || data.suburb_b.risk_flags.length > 0) && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
              {[{ s: data.suburb_a, color: '#3498db' }, { s: data.suburb_b, color: '#e74c3c' }].map(({ s, color }) => (
                s.risk_flags.length > 0 ? (
                  <div key={s.sa2_code} style={{ backgroundColor: '#343b47', borderRadius: '10px', padding: '16px' }}>
                    <div style={{ fontSize: '13px', color, marginBottom: '8px', fontWeight: 600 }}>{s.sa2_name} — Risk Flags</div>
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                      {s.risk_flags.map(f => (
                        <span key={f} style={{ padding: '4px 10px', backgroundColor: '#4a3030', color: '#e07070', borderRadius: '4px', fontSize: '12px' }}>
                          {f.replace(/_/g, ' ')}
                        </span>
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
