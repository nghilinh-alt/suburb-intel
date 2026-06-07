interface GaugeBarProps {
  value: number
  max?: number
  label?: string
  showValue?: boolean
  height?: number
}

function scoreColor(pct: number): string {
  if (pct >= 0.7) return '#34d399'
  if (pct >= 0.45) return '#fbbf24'
  return '#fb7185'
}

export default function GaugeBar({
  value,
  max = 10,
  label,
  showValue = true,
  height = 8,
}: GaugeBarProps) {
  const pct = Math.min(Math.max(value / max, 0), 1)
  const color = scoreColor(pct)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      {(label || showValue) && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
          {label && (
            <span style={{ fontSize: '13px', color: '#9aafc8' }}>{label}</span>
          )}
          {showValue && (
            <span style={{ fontSize: '13px', fontWeight: 600, color }}>{value.toFixed(1)}</span>
          )}
        </div>
      )}
      <div
        style={{
          width: '100%',
          height: `${height}px`,
          backgroundColor: '#28334a',
          borderRadius: `${height}px`,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            width: `${pct * 100}%`,
            height: '100%',
            backgroundColor: color,
            borderRadius: `${height}px`,
            transition: 'width 0.4s ease',
          }}
        />
      </div>
    </div>
  )
}
