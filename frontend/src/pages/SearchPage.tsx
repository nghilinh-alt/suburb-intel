import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

interface SearchResult {
  sa2_code: string
  sa2_name: string
  state: string
  population: number | null
  median_income: number | null
  median_age: number | null
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
        const res = await fetch(`/api/search?query=${encodeURIComponent(query.trim())}&limit=10`)
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
    navigate(`/suburb/${r.sa2_code}`)
  }

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '32px', marginBottom: '8px' }}>Search Suburbs</h2>
      <p style={{ color: '#9ca0aa', marginBottom: '32px' }}>
        Find any Australian suburb or SA2 region to view its investment profile.
      </p>

      {/* Search input */}
      <div style={{ position: 'relative', marginBottom: '8px' }}>
        <input
          type="text"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="Type a suburb name (e.g. Parramatta, Tarneit, Rhodes…)"
          autoFocus
          style={{
            width: '100%', boxSizing: 'border-box',
            padding: '16px 48px 16px 16px',
            fontSize: '18px',
            backgroundColor: '#343b47',
            color: '#f8f8f2',
            border: '1px solid #4b566a',
            borderRadius: '8px',
            outline: 'none',
          }}
        />
        {loading && (
          <span style={{ position: 'absolute', right: '16px', top: '50%', transform: 'translateY(-50%)', color: '#9ca0aa' }}>
            ⏳
          </span>
        )}
      </div>

      {error && (
        <p style={{ color: '#e74c3c', marginBottom: '16px', fontSize: '14px' }}>{error}</p>
      )}

      {/* Live results */}
      {results.length > 0 && (
        <div style={{ marginBottom: '40px', borderRadius: '8px', overflow: 'hidden', border: '1px solid #4b566a' }}>
          {results.map(r => (
            <button
              key={r.sa2_code}
              onClick={() => handleSelect(r)}
              style={{
                width: '100%', display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '14px 20px', backgroundColor: '#343b47', border: 'none',
                borderBottom: '1px solid #4b566a', cursor: 'pointer', color: '#f8f8f2', textAlign: 'left',
              }}
            >
              <div>
                <div style={{ fontWeight: 600, fontSize: '16px' }}>{r.sa2_name}</div>
                <div style={{ color: '#9ca0aa', fontSize: '13px' }}>SA2 {r.sa2_code}</div>
              </div>
              <div style={{ textAlign: 'right', color: '#9ca0aa', fontSize: '13px' }}>
                <div>{r.state}</div>
                {r.population && <div>{r.population.toLocaleString()} residents</div>}
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Recent searches */}
      {recent.length > 0 && results.length === 0 && (
        <>
          <h3 style={{ fontSize: '18px', color: '#9ca0aa', marginBottom: '16px' }}>Recent searches</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
            {recent.map(r => (
              <button
                key={r.sa2_code}
                onClick={() => handleSelect(r)}
                style={{
                  padding: '10px 18px', backgroundColor: '#343b47',
                  color: '#f8f8f2', border: '1px solid #4b566a',
                  borderRadius: '6px', cursor: 'pointer', fontSize: '14px',
                }}
              >
                {r.sa2_name} <span style={{ color: '#9ca0aa' }}>{r.state}</span>
              </button>
            ))}
          </div>
        </>
      )}

      {/* Prompt when empty */}
      {!query && recent.length === 0 && (
        <div style={{ color: '#9ca0aa', fontSize: '15px', lineHeight: 1.8 }}>
          <p>Try searching for:</p>
          {['Parramatta', 'Tarneit', 'Newstead', 'Rhodes', 'Subiaco'].map(s => (
            <button key={s} onClick={() => setQuery(s)}
              style={{ marginRight: '10px', marginBottom: '8px', padding: '8px 16px', backgroundColor: '#343b47', color: '#d1d5da', border: '1px solid #4b566a', borderRadius: '6px', cursor: 'pointer', fontSize: '14px' }}>
              {s}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
