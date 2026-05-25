interface ScoreCardProps {
  label: string
  value: string
  description: string
}

export default function ScoreCard({ label, value, description }: ScoreCardProps) {
  return (
    <div style={{ 
      backgroundColor: '#343b47', 
      borderRadius: '12px', 
      padding: '24px' 
    }}>
      <h4 style={{ fontSize: '14px', color: '#9ca0aa', textTransform: 'uppercase', letterSpacing: '1px', marginBottom: '8px' }}>
        {label}
      </h4>
      <div style={{ fontSize: '56px', fontWeight: 'bold', color: '#f8f8f2' }}>{value}</div>
      <p style={{ color: '#9ca0aa', fontSize: '14px', marginTop: '8px' }}>{description}</p>
    </div>
  )
}
