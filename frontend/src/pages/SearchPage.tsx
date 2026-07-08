import { FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  askSearch,
  searchSuburbs,
  type AskSearchResponse,
  type SuburbSearchResult,
} from '../lib/api'

const EXAMPLE_PROMPTS = [
  'Brisbane suburbs within 10km of CBD',
  'top 5 highest income suburbs in Sydney',
  'Melbourne suburbs closest to CBD',
]

type NameSearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; results: SuburbSearchResult[] }

type AskSearchState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: AskSearchResponse }

export default function SearchPage() {
  const [query, setQuery] = useState('')
  const [nameState, setNameState] = useState<NameSearchState>({ status: 'idle' })

  const [prompt, setPrompt] = useState('')
  const [askState, setAskState] = useState<AskSearchState>({ status: 'idle' })

  async function runNameSearch(q: string) {
    if (!q.trim()) return
    setNameState({ status: 'loading' })
    try {
      const data = await searchSuburbs(q)
      const results = Array.isArray(data) ? data : [data]
      setNameState({ status: 'ready', results })
    } catch (err) {
      setNameState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Search failed.',
      })
    }
  }

  async function runAskSearch(p: string) {
    if (!p.trim()) return
    setAskState({ status: 'loading' })
    try {
      const data = await askSearch(p)
      setAskState({ status: 'ready', data })
    } catch (err) {
      setAskState({
        status: 'error',
        message: err instanceof Error ? err.message : 'Search failed.',
      })
    }
  }

  function handleNameSubmit(e: FormEvent) {
    e.preventDefault()
    runNameSearch(query)
  }

  function handleAskSubmit(e: FormEvent) {
    e.preventDefault()
    runAskSearch(prompt)
  }

  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '32px', marginBottom: '32px' }}>Search Suburbs</h2>

      <form onSubmit={handleNameSubmit} style={{ marginBottom: '16px' }}>
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search by suburb name or enter SA2 code..."
          style={inputStyle}
        />
      </form>

      <p style={{ color: '#9ca0aa', marginBottom: '20px' }}>
        Enter a suburb name (e.g., "Chermside") or SA2 code to get its investment report.
      </p>

      <h3 style={{ fontSize: '24px', marginBottom: '16px' }}>Recent Searches</h3>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '20px' }}>
        {['Chermside', 'Brisbane Waters', 'Cronulla'].map((suburb) => (
          <button
            key={suburb}
            onClick={() => {
              setQuery(suburb)
              runNameSearch(suburb)
            }}
            style={quickButtonStyle}
          >
            {suburb}
          </button>
        ))}
      </div>

      {nameState.status === 'loading' && <p style={{ color: '#9ca0aa' }}>Searching...</p>}

      {nameState.status === 'error' && (
        <p style={{ color: '#f8d7da' }}>{nameState.message}</p>
      )}

      {nameState.status === 'ready' && (
        <div style={{ display: 'grid', gap: '12px', marginBottom: '20px' }}>
          {nameState.results.length === 0 && (
            <p style={{ color: '#9ca0aa' }}>No suburbs found.</p>
          )}
          {nameState.results.map((r) => (
            <Link
              key={r.sa2_code}
              to={`/suburb/${r.sa2_code}`}
              style={{ textDecoration: 'none', color: '#f8f8f2' }}
            >
              <div style={resultCardStyle}>
                <div>
                  <strong>{r.sa2_name}</strong>{' '}
                  <span style={{ color: '#9ca0aa' }}>{r.state}</span>
                </div>
                <div style={{ color: '#9ca0aa', fontSize: '14px' }}>
                  {[
                    r.population != null ? `Pop ${r.population.toLocaleString()}` : null,
                    r.distance_to_cbd_km != null ? `${r.distance_to_cbd_km.toFixed(1)} km to CBD` : null,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </div>
              </div>
            </Link>
          ))}
        </div>
      )}

      <div style={{ borderTop: '1px solid #4b566a', margin: '40px 0' }} />

      <h3 style={{ fontSize: '24px', marginBottom: '16px' }}>Ask in Plain English</h3>

      <form onSubmit={handleAskSubmit} style={{ marginBottom: '16px' }}>
        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder='e.g. "Brisbane suburbs within 10km of CBD"'
          rows={3}
          style={{ ...inputStyle, resize: 'vertical', fontFamily: 'inherit' }}
        />
        <button type="submit" style={{ ...quickButtonStyle, marginTop: '12px' }}>
          Search
        </button>
      </form>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px', marginBottom: '20px' }}>
        {EXAMPLE_PROMPTS.map((example) => (
          <button
            key={example}
            onClick={() => {
              setPrompt(example)
              runAskSearch(example)
            }}
            style={quickButtonStyle}
          >
            {example}
          </button>
        ))}
      </div>

      {askState.status === 'loading' && <p style={{ color: '#9ca0aa' }}>Searching...</p>}

      {askState.status === 'error' && (
        <p style={{ color: '#f8d7da' }}>{askState.message}</p>
      )}

      {askState.status === 'ready' && (
        <>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '16px' }}>
            {Object.entries(askState.data.parsed_filter)
              .filter(([, v]) => v !== null && v !== undefined)
              .map(([k, v]) => (
                <span key={k} style={chipStyle}>
                  {k}: {String(v)}
                </span>
              ))}
          </div>

          {askState.data.message && (
            <p style={{ color: '#9ca0aa' }}>{askState.data.message}</p>
          )}

          <div style={{ display: 'grid', gap: '12px' }}>
            {askState.data.results.map((r) => (
              <Link
                key={r.sa2_code}
                to={`/suburb/${r.sa2_code}`}
                style={{ textDecoration: 'none', color: '#f8f8f2' }}
              >
                <div style={resultCardStyle}>
                  <div>
                    <strong>{r.sa2_name}</strong>{' '}
                    <span style={{ color: '#9ca0aa' }}>{r.state}</span>
                  </div>
                  <div style={{ color: '#9ca0aa', fontSize: '14px' }}>
                    {[
                      r.distance_to_cbd_km != null ? `${r.distance_to_cbd_km.toFixed(1)} km to CBD` : null,
                      r.population != null ? `Pop ${r.population.toLocaleString()}` : null,
                      r.median_income != null ? `Income $${r.median_income.toLocaleString()}` : null,
                    ]
                      .filter(Boolean)
                      .join(' · ')}
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </>
      )}
    </div>
  )
}

const inputStyle = {
  width: '100%',
  padding: '16px',
  fontSize: '18px',
  backgroundColor: '#343b47',
  color: '#f8f8f2',
  border: '1px solid #4b566a',
  borderRadius: '8px',
  outline: 'none',
  boxSizing: 'border-box' as const,
}

const quickButtonStyle = {
  padding: '12px 20px',
  backgroundColor: '#4b566a',
  color: '#f8f8f2',
  border: 'none',
  borderRadius: '6px',
  cursor: 'pointer',
}

const resultCardStyle = {
  backgroundColor: '#343b47',
  border: '1px solid #4b566a',
  borderRadius: '8px',
  padding: '16px 20px',
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
}

const chipStyle = {
  backgroundColor: '#4b566a',
  color: '#d1d5da',
  padding: '6px 12px',
  borderRadius: '999px',
  fontSize: '13px',
}
