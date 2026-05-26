import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

interface SuburbScores {
  investment_score: number
  demographic_score: number
  economic_score: number
  housing_pressure_score: number
  resilience_score: number
  gov_investment_score: number
}

interface SuburbReport {
  sa2_code: string
  sa2_name: string | null
  state: string | null
  scores: SuburbScores
  insight: string
  risk_flags: string[]
  tags: string[]
  census_year: number
  population: number | null
  median_income: number | null
  median_age: number | null
}

type FetchState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: SuburbReport }

interface ScoreCardProps {
  label: string
  value: number | string
  description: string
}

function ScoreCard({ label, value, description }: ScoreCardProps) {
  return (
    <div style={{ backgroundColor: '#343b47', borderRadius: '12px', padding: '24px' }}>
      <h4
        style={{
          fontSize: '14px',
          color: '#9ca0aa',
          textTransform: 'uppercase',
          letterSpacing: '1px',
          marginBottom: '8px',
        }}
      >
        {label}
      </h4>
      <div style={{ fontSize: '56px', fontWeight: 'bold', color: '#f8f8f2' }}>{value}</div>
      <p style={{ color: '#9ca0aa', fontSize: '14px', marginTop: '8px' }}>{description}</p>
    </div>
  )
}

function fmtScore(n: number | undefined): string {
  if (n === undefined || n === null || Number.isNaN(n)) return '—'
  return Math.round(n).toString()
}

export default function SuburbPage() {
  const { id: sa2Code = '' } = useParams<{ id: string }>()
  const [state, setState] = useState<FetchState>({ status: 'loading' })

  useEffect(() => {
    if (!sa2Code) {
      setState({ status: 'error', message: 'Missing SA2 code in URL.' })
      return
    }

    let cancelled = false
    setState({ status: 'loading' })

    fetch(`/api/suburb/${encodeURIComponent(sa2Code)}`)
      .then(async (response) => {
        if (!response.ok) {
          const body = await response.json().catch(() => null)
          const detail = body && typeof body.detail === 'string' ? body.detail : response.statusText
          throw new Error(`${response.status}: ${detail}`)
        }
        return (await response.json()) as SuburbReport
      })
      .then((data) => {
        if (!cancelled) setState({ status: 'ready', data })
      })
      .catch((err: unknown) => {
        if (cancelled) return
        const message = err instanceof Error ? err.message : 'Unknown error fetching suburb.'
        setState({ status: 'error', message })
      })

    return () => {
      cancelled = true
    }
  }, [sa2Code])

  return (
    <div style={{ padding: '40px' }}>
      <div style={{ marginBottom: '20px' }}>
        <Link
          to="/"
          style={{
            display: 'inline-block',
            backgroundColor: '#343b47',
            color: '#f8f8f2',
            border: '1px solid #4b566a',
            padding: '8px 16px',
            borderRadius: '6px',
            cursor: 'pointer',
            textDecoration: 'none',
          }}
        >
          Back to Search
        </Link>
      </div>

      {state.status === 'loading' && (
        <p style={{ color: '#9ca0aa', fontSize: '18px' }}>Loading suburb {sa2Code}...</p>
      )}

      {state.status === 'error' && (
        <div
          style={{
            backgroundColor: '#3b2a2a',
            border: '1px solid #6b3b3b',
            borderRadius: '12px',
            padding: '20px',
            color: '#f8d7da',
          }}
        >
          <h2 style={{ marginTop: 0 }}>Could not load suburb {sa2Code}</h2>
          <p style={{ marginBottom: 0 }}>{state.message}</p>
        </div>
      )}

      {state.status === 'ready' && <ReadyView data={state.data} />}
    </div>
  )
}

function ReadyView({ data }: { data: SuburbReport }) {
  const { sa2_code, sa2_name, state, scores, insight, risk_flags, tags } = data

  return (
    <>
      <h1 style={{ fontSize: '48px', marginBottom: '20px' }}>
        {sa2_name ?? `Suburb ${sa2_code}`}
        {state ? <span style={{ color: '#9ca0aa', fontSize: '24px', marginLeft: '12px' }}>{state}</span> : null}
      </h1>

      <p style={{ color: '#9ca0aa', fontSize: '18px', marginBottom: '60px' }}>SA2 Code: {sa2_code}</p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px',
          marginBottom: '60px',
        }}
      >
        <ScoreCard
          label="Investment Score"
          value={fmtScore(scores.investment_score)}
          description="Overall investment potential (0-100)"
        />
        <ScoreCard
          label="Demographics"
          value={fmtScore(scores.demographic_score)}
          description="Population growth & young population"
        />
        <ScoreCard
          label="Economy"
          value={fmtScore(scores.economic_score)}
          description="Income levels & employment diversity"
        />
        <ScoreCard
          label="Housing"
          value={fmtScore(scores.housing_pressure_score)}
          description="Rental pressure analysis"
        />
        <ScoreCard
          label="Resilience"
          value={fmtScore(scores.resilience_score)}
          description="Industry diversification"
        />
        <ScoreCard
          label="Gov Investment"
          value={fmtScore(scores.gov_investment_score)}
          description="Government projects pipeline"
        />
      </div>

      <div
        style={{
          backgroundColor: '#343b47',
          borderRadius: '12px',
          padding: '32px',
          marginBottom: '60px',
        }}
      >
        <h2 style={{ fontSize: '28px', marginBottom: '16px' }}>Key Insight</h2>
        <p style={{ fontSize: '20px', color: '#d1d5da', lineHeight: 1.6 }}>{insight}</p>
      </div>

      {risk_flags.length > 0 && (
        <>
          <h3 style={{ fontSize: '24px', marginBottom: '20px' }}>Risk Flags</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', marginBottom: '40px' }}>
            {risk_flags.map((flag) => (
              <span
                key={flag}
                style={{ backgroundColor: '#4b566a', padding: '10px 16px', borderRadius: '6px' }}
              >
                {flag}
              </span>
            ))}
          </div>
        </>
      )}

      {tags.length > 0 && (
        <>
          <h3 style={{ fontSize: '24px', marginBottom: '20px' }}>Tags</h3>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
            {tags.map((tag) => (
              <span
                key={tag}
                style={{
                  backgroundColor: '#4b566a',
                  padding: '8px 14px',
                  borderRadius: '4px',
                  fontSize: '14px',
                }}
              >
                {tag}
              </span>
            ))}
          </div>
        </>
      )}

      <div
        style={{
          marginTop: '40px',
          textAlign: 'center',
          backgroundColor: '#343b47',
          padding: '40px',
          borderRadius: '12px',
        }}
      >
        <h2 style={{ fontSize: '32px', marginBottom: '20px' }}>Unlock Full Report</h2>
        <p style={{ fontSize: '18px', color: '#9ca0aa', marginBottom: '24px' }}>
          Get detailed analysis, peer comparisons, and actionable investment advice
        </p>
        <button
          style={{
            padding: '16px 48px',
            fontSize: '20px',
            fontWeight: 'bold',
            backgroundColor: '#e74c3c',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer',
          }}
        >
          Unlock for $9
        </button>
      </div>
    </>
  )
}
