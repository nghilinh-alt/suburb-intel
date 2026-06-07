import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

interface SearchResult {
  // Suburb group fields (new primary format)
  suburb_id?: string
  suburb_name?: string
  sa2_count?: number
  is_aggregate?: boolean
  // Legacy SA2 fields (used for exact code lookups)
  sa2_code?: string
  sa2_name?: string
  postcode?: string
  state: string
  population: number | null
  investment_score?: number | null
}

const RECENT_KEY = 'suburb_recent_searches'

function getRecent(): SearchResult[] {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]')
  } catch {
    return []
  }
}

function saveRecent(result: SearchResult) {
  const existing = getRecent().filter(r => r.sa2_code !== result.sa2_code)
  localStorage.setItem(RECENT_KEY, JSON.stringify([result, ...existing].slice(0, 5)))
}

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [recent, setRecent] = useState<SearchResult[]>(getRecent)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    if (query.trim().length < 2) {
      setResults([])
      setError(null)
      return
    }
    debounceRef.current = setTimeout(async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(`/api/search/?query=${encodeURIComponent(query.trim())}&limit=10`)
        if (!res.ok) {
          const body = await res.json().catch(() => null)
          throw new Error(body?.detail || 'Search failed')
        }
        const data = await res.json()
        // API returns either an array (name search) or a single object (code lookup)
        setResults(Array.isArray(data) ? data : [data])
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Search error')
        setResults([])
      } finally {
        setLoading(false)
      }
    }, 300)
  }, [query])

  function handleSelect(r: SearchResult) {
    saveRecent(r)
    setRecent(getRecent())
    // Route to suburb-group page if we have a suburb_id, else fallback to SA2
    if (r.suburb_id) {
      navigate(`/suburb-group/${r.suburb_id}`)
    } else {
      navigate(`/suburb/${r.sa2_code}`)
    }
  }

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      {/* Hero */}
      <div style={{ marginBottom: '48px', textAlign: 'center' }}>
        <div style={{
          display: 'inline-block',
          padding: '4px 14px',
          borderRadius: '99px',
          backgroundColor: 'rgba(45,212,191,0.1)',
          border: '1px solid rgba(45,212,191,0.25)',
          fontSize: '12px',
          fontWeight: 600,
          color: '#2dd4bf',
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          marginBottom: '20px',
        }}>
          Intelligence done differently
        </div>
        <h1 style={{ fontSize: '40px', fontWeight: 800, color: '#cdd8e8', margin: '0 0 12px', letterSpacing: '-0.03em', lineHeight: 1.15 }}>
          Find your next suburb
        </h1>
        <p style={{ color: '#6b7fa0', fontSize: '16px', margin: 0, maxWidth: '520px', marginLeft: 'auto', marginRight: 'auto', lineHeight: 1.6 }}>
          Data-driven analysis for every Australian suburb — demographics, liveability, infrastructure, and investment signals in one place.
        </p>
      </div>

      {/* Search input */}
      <div style={{ position: 'relative', marginBottom: '8px' }}>
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Suburb name or postcode (e.g. Parramatta, Tarneit, 4115…)"
          autoFocus
          style={{
            width: '100%', boxSizing: 'border-box',
            padding: '18px 52px 18px 20px',
            fontSize: '18px',
            backgroundColor: '#151b27',
            color: '#cdd8e8',
            border: '1px solid #28334a',
            borderRadius: '12px',
            outline: 'none',
            boxShadow: '0 2px 12px rgba(0,0,0,0.4)',
          }}
        />
        {loading && (
          <span style={{ position: 'absolute', right: '16px', top: '50%', transform: 'translateY(-50%)', color: '#9ca0aa' }}>
            ⏳
          </span>
        )}
      </div>

      {error && (
        <p style={{ color: '#fb7185', marginBottom: '16px', fontSize: '14px' }}>{error}</p>
      )}

      {/* Live results */}
      {results.length > 0 && (
        <div style={{ marginBottom: '40px', borderRadius: '12px', overflow: 'hidden', border: '1px solid #28334a', boxShadow: '0 4px 20px rgba(0,0,0,0.5)' }}>
          {results.map(r => (
            <button
              key={r.suburb_id ?? r.sa2_code}
              onClick={() => handleSelect(r)}
              style={{
                width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '14px 20px', backgroundColor: '#151b27', border: 'none',
                borderBottom: '1px solid #1e2638', cursor: 'pointer', color: '#cdd8e8', textAlign: 'left',
              }}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: '16px' }}>{r.suburb_name ?? r.sa2_name}</div>
                <div style={{ color: '#6b7fa0', fontSize: '13px', display: 'flex', gap: '8px', alignItems: 'center', flexWrap: 'wrap', marginTop: '2px' }}>
                  {r.postcode && <span style={{ padding: '1px 8px', backgroundColor: 'rgba(56,189,248,0.1)', color: '#38bdf8', borderRadius: '4px', fontSize: '11px', border: '1px solid rgba(56,189,248,0.2)' }}>📮 {r.postcode}</span>}
                  {r.sa2_count && r.sa2_count > 1 ? <span>{r.sa2_count} areas</span> : null}
                  {r.sa2_code ? <span>SA2 {r.sa2_code}</span> : null}
                </div>
              </div>
              <div style={{ textAlign: 'right', color: '#6b7fa0', fontSize: '13px', flexShrink: 0, marginLeft: '16px' }}>
                <div style={{ color: '#9aafc8' }}>{r.state}</div>
                {r.population && <div>{r.population.toLocaleString()} residents</div>}
                {r.investment_score != null && (
                  <div style={{
                    color: r.investment_score >= 6.5 ? '#34d399' : r.investment_score >= 5 ? '#fbbf24' : '#fb7185',
                    fontWeight: 700,
                  }}>
                    ★ {r.investment_score.toFixed(1)}
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Recent searches */}
      {recent.length > 0 && results.length === 0 && (
        <>
          <h3 style={{ fontSize: '14px', fontWeight: 500, color: '#6b7fa0', marginBottom: '12px', textTransform: 'uppercase', letterSpacing: '0.07em' }}>Recent searches</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {recent.map(r => (
              <button
                key={r.suburb_id ?? r.sa2_code}
                onClick={() => handleSelect(r)}
                style={{
                  padding: '9px 16px', backgroundColor: '#151b27',
                  color: '#cdd8e8', border: '1px solid #28334a',
                  borderRadius: '8px', cursor: 'pointer', fontSize: '14px',
                }}
              >
                {r.sa2_name} <span style={{ color: '#6b7fa0' }}>{r.state}</span>
              </button>
            ))}
          </div>
        </>
      )}

      {/* Prompt when empty */}
      {!query && recent.length === 0 && (
        <div style={{ color: '#6b7fa0', fontSize: '14px' }}>
          <p style={{ marginBottom: '12px' }}>Try searching for:</p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
            {['Parramatta', 'Tarneit', 'Newstead', '4115', '3030', 'Subiaco'].map(s => (
              <button key={s} onClick={() => setQuery(s)}
                style={{ padding: '8px 16px', backgroundColor: '#151b27', color: '#9aafc8', border: '1px solid #28334a', borderRadius: '8px', cursor: 'pointer', fontSize: '14px' }}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
