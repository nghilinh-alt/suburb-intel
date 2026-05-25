export default function SearchPage() {
  return (
    <div style={{ maxWidth: '800px', margin: '0 auto' }}>
      <h2 style={{ fontSize: '32px', marginBottom: '32px' }}>Search Suburbs</h2>
      
      <div style={{ marginBottom: '32px' }}>
        <input
          type="text"
          placeholder="Search by suburb name or enter SA2 code..."
          style={{
            width: '100%',
            padding: '16px',
            fontSize: '18px',
            backgroundColor: '#343b47',
            color: '#f8f8f2',
            border: '1px solid #4b566a',
            borderRadius: '8px',
            outline: 'none'
          }}
        />
      </div>
      
      <p style={{ color: '#9ca0aa', marginBottom: '20px' }}>
        Enter a suburb name (e.g., "Chermside") or SA2 code to get its investment report.
      </p>
      
      <h3 style={{ fontSize: '24px', marginBottom: '16px' }}>Recent Searches</h3>
      
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '10px' }}>
        {['Chermside QLD', 'Brisbane Waters QLD', 'Cronulla NSW'].map((suburb) => (
          <button
            key={suburb}
            style={{
              padding: '12px 20px',
              backgroundColor: '#4b566a',
              color: '#f8f8f2',
              border: 'none',
              borderRadius: '6px',
              cursor: 'pointer'
            }}
          >
            {suburb}
          </button>
        ))}
      </div>
    </div>
  )
}
