interface PaywallProps {
  onUnlock: () => void
}

export default function Paywall({ onUnlock }: PaywallProps) {
  return (
    <div style={{
      backgroundColor: '#343b47',
      borderRadius: '12px',
      padding: '40px',
      textAlign: 'center',
      border: '2px solid #e74c3c'
    }}>
      <h2 style={{ fontSize: '32px', marginBottom: '16px' }}>🔒 Full Report Locked</h2>
      
      <p style={{ fontSize: '18px', color: '#d1d5da', marginBottom: '24px' }}>
        Unlock detailed suburb analysis including:
      </p>

      <div style={{ 
        display: 'grid', 
        gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', 
        gap: '16px',
        marginBottom: '32px'
      }}>
        <div style={{ padding: '16px', backgroundColor: '#4b566a', borderRadius: '8px' }}>
          <h4 style={{ margin: '0 0 8px 0', color: '#f8f8f2' }}>Historical Trends</h4>
          <p style={{ margin: 0, color: '#9ca0aa', fontSize: '14px' }}>5-year data analysis</p>
        </div>
        
        <div style={{ padding: '16px', backgroundColor: '#4b566a', borderRadius: '8px' }}>
          <h4 style={{ margin: '0 0 8px 0', color: '#f8f8f2' }}>Peer Comparison</h4>
          <p style={{ margin: 0, color: '#9ca0aa', fontSize: '14px' }}>Similar suburb analysis</p>
        </div>
        
        <div style={{ padding: '16px', backgroundColor: '#4b566a', borderRadius: '8px' }}>
          <h4 style={{ margin: '0 0 8px 0', color: '#f8f8f2' }}>Investment Calculator</h4>
          <p style={{ margin: 0, color: '#9ca0aa', fontSize: '14px' }}>ROI projections & payback</p>
        </div>
        
        <div style={{ padding: '16px', backgroundColor: '#4b566a', borderRadius: '8px' }}>
          <h4 style={{ margin: '0 0 8px 0', color: '#f8f8f2' }}>Risk Assessment</h4>
          <p style={{ margin: 0, color: '#9ca0aa', fontSize: '14px' }}>Detailed risk analysis</p>
        </div>
      </div>

      <button 
        onClick={onUnlock}
        style={{
          padding: '18px 64px',
          fontSize: '24px',
          fontWeight: 'bold',
          backgroundColor: '#e74c3c',
          color: 'white',
          border: 'none',
          borderRadius: '8px',
          cursor: 'pointer'
        }}
      >
        Unlock Full Report - $9
      </button>

      <p style={{ marginTop: '20px', fontSize: '14px', color: '#9ca0aa' }}>
        Secure payment via Stripe • No commitment required
      </p>
    </div>
  )
}
