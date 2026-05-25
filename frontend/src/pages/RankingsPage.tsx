export default function RankingsPage() {
  const topSuburbs = [
    { code: "47002", name: "Chermside QLD", score: 85, population: 28900 },
    { code: "48210", name: "Brisbane Waters QLD", score: 82, population: 12450 },
    { code: "22625", name: "Cronulla NSW", score: 79, population: 18750 },
    { code: "30150", name: "Altona Gardens VIC", score: 76, population: 8450 },
    { code: "34005", name: "Ashtabula QLD", score: 73, population: 6230 }
  ]

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '32px', marginBottom: '20px' }}>Top Suburbs by Investment Score</h2>
      
      <div style={{ display: 'flex', gap: '8px', marginBottom: '40px' }}>
        <button style={sortButtonStyle}>All Metrics</button>
        <button style={sortButtonStyle}>Most Popular</button>
        <button style={sortButtonStyle}>Highest Income</button>
      </div>

      <div style={{ display: 'grid', gap: '20px' }}>
        {topSuburbs.map((suburb, index) => (
          <a key={suburb.code} href={`/suburb/${suburb.code}`} style={{ textDecoration: 'none' }}>
            <div style={{ 
              backgroundColor: '#343b47', 
              borderRadius: '12px', 
              padding: '24px',
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              border: index === 0 ? '2px solid #f8f8f2' : 'none'
            }}>
              <div>
                <h3 style={{ fontSize: '24px', color: '#f8f8f2', marginBottom: '4px' }}>
                  #{index + 1} {suburb.name}
                </h3>
                <p style={{ color: '#9ca0aa' }}>SA2 Code: {suburb.code}</p>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '48px', fontWeight: 'bold', color: '#f8f8f2' }}>{suburb.score}</div>
                <span style={{ color: '#9ca0aa' }}>investment score</span>
              </div>
            </div>
          </a>
        ))}
      </div>

      <div style={{ 
        marginTop: '60px', 
        textAlign: 'center', 
        backgroundColor: '#343b47',
        padding: '48px',
        borderRadius: '12px'
      }}>
        <h2 style={{ fontSize: '32px', marginBottom: '20px' }}>See Full Rankings</h2>
        <p style={{ fontSize: '18px', color: '#9ca0aa', marginBottom: '24px' }}>
          Explore all {topSuburbs.length} suburbs ranked by investment potential
        </p>
        <button 
          style={{
            padding: '16px 48px',
            fontSize: '18px',
            backgroundColor: '#4b566a',
            color: '#f8f8f2',
            border: 'none',
            borderRadius: '8px',
            cursor: 'pointer'
          }}
        >
          View All Rankings
        </button>
      </div>
    </div>
  )
}

const sortButtonStyle = {
  padding: '10px 24px',
  backgroundColor: '#343b47',
  color: '#d1d5da',
  border: '1px solid #4b566a',
  borderRadius: '8px',
  cursor: 'pointer'
}
