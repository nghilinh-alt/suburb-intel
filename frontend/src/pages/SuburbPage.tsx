import { Link, useParams } from 'react-router-dom'

interface ScoreCardProps {
  label: string
  value: string
  description: string
}

function ScoreCard({ label, value, description }: ScoreCardProps) {
  return (
    <div style={{ backgroundColor: '#343b47', borderRadius: '12px', padding: '24px' }}>
      <h4 style={{ fontSize: '14px', color: '#9ca0aa', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
        {label}
      </h4>
      <div style={{ fontSize: '56px', fontWeight: 'bold', color: '#f8f8f2' }}>{value}</div>
      <p style={{ color: '#9ca0aa', fontSize: '14px', marginTop: '8px' }}>{description}</p>
    </div>
  )
}

export default function SuburbPage() {
  // React Router supplies route params via useParams, not via a `params` prop.
  const { id: sa2Code = '' } = useParams<{ id: string }>()
  const suburbName = 'Chermside QLD' // TODO: fetch from /suburb/{sa2Code}

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
          ← Back to Search
        </Link>
      </div>

      <h1 style={{ fontSize: '48px', marginBottom: '20px' }}>{suburbName}</h1>

      <p style={{ color: '#9ca0aa', fontSize: '18px', marginBottom: '60px' }}>
        SA2 Code: {sa2Code}
      </p>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
          gap: '24px',
          marginBottom: '60px',
        }}
      >
        <ScoreCard label="Investment Score" value="78" description="Overall investment potential (0-100)" />
        <ScoreCard label="Demographics" value="82" description="Population growth & young population" />
        <ScoreCard label="Economy" value="74" description="Income levels & employment diversity" />
        <ScoreCard label="Housing" value="69" description="Rental pressure analysis" />
        <ScoreCard label="Resilience" value="71" description="Industry diversification" />
        <ScoreCard label="Gov Investment" value="85" description="Government projects pipeline" />
      </div>

      <div style={{ backgroundColor: '#343b47', borderRadius: '12px', padding: '32px', marginBottom: '60px' }}>
        <h2 style={{ fontSize: '28px', marginBottom: '16px' }}>Key Insight</h2>
        <p style={{ fontSize: '20px', color: '#d1d5da', lineHeight: '1.6' }}>
          Strong early growth suburb driven by infrastructure and demographic momentum.
          Government investment uplift indicates promising future trajectory.
        </p>
      </div>

      <h3 style={{ fontSize: '24px', marginBottom: '20px' }}>Risk Flags</h3>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px', marginBottom: '40px' }}>
        {['Moderate retail dependency', 'Rising rental pressure volatility'].map((flag) => (
          <span key={flag} style={{ backgroundColor: '#4b566a', padding: '10px 16px', borderRadius: '6px' }}>
            {flag}
          </span>
        ))}
      </div>

      <h3 style={{ fontSize: '24px', marginBottom: '20px' }}>Tags</h3>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '16px' }}>
        {['Early Growth Zone', 'Infrastructure-Driven Suburb'].map((tag) => (
          <span
            key={tag}
            style={{ backgroundColor: '#4b566a', padding: '8px 14px', borderRadius: '4px', fontSize: '14px' }}
          >
            {tag}
          </span>
        ))}
      </div>

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
    </div>
  )
}
