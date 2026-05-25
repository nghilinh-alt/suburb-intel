interface BreakdownProps {
  scores: {
    demographic_score?: number
    economic_score?: number
    housing_pressure_score?: number
    resilience_score?: number
    gov_investment_score?: number
  }
}

export default function Breakdown({ scores }: BreakdownProps) {
  const scoreData = [
    { name: 'Demographics', value: scores?.demographic_score || 0, weight: 25 },
    { name: 'Economy', value: scores?.economic_score || 0, weight: 20 },
    { name: 'Housing Pressure', value: scores?.housing_pressure_score || 0, weight: 20 },
    { name: 'Resilience', value: scores?.resilience_score || 0, weight: 15 },
    { name: 'Gov Investment', value: scores?.gov_investment_score || 0, weight: 20 }
  ]

  return (
    <div style={{ 
      backgroundColor: '#343b47', 
      borderRadius: '12px', 
      padding: '32px' 
    }}>
      <h3 style={{ fontSize: '24px', marginBottom: '24px' }}>Score Breakdown</h3>

      <div style={{ display: 'grid', gap: '16px' }}>
        {scoreData.map((item, index) => (
          <div key={index} style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <span style={{ flex: 1, color: '#9ca0aa', fontSize: '14px', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
              {item.name}
            </span>
            <div style={{ width: '200px' }}>
              <div style={{ 
                backgroundColor: '#4b566a', 
                height: '8px', 
                borderRadius: '4px',
                overflow: 'hidden'
              }}>
                <div style={{
                  width: `${(item.value / 100) * 100}%`,
                  backgroundColor: item.value >= 80 ? '#27ae60' : item.value >= 70 ? '#2ecc71' : item.value >= 60 ? '#f39c12' : '#e74c3c',
                  height: '100%',
                  transition: 'width 0.5s ease'
                }} />
              </div>
            </div>
            <span style={{ width: '80px', textAlign: 'right', color: '#f8f8f2', fontWeight: 'bold' }}>
              {Math.round(item.value)}
            </span>
            <span style={{ 
              width: '70px', 
              fontSize: '12px', 
              color: '#9ca0aa',
              textAlign: 'right'
            }}>
              ({item.weight}%)
            </span>
          </div>
        ))}
      </div>

      <p style={{ marginTop: '32px', fontSize: '14px', color: '#9ca0aa' }}>
        Score weights reflect the investment scoring methodology, with demographic momentum and government 
        investment playing the largest roles in determining overall investment potential.
      </p>
    </div>
  )
}
