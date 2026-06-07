interface MetricBlockProps {
  label: string
  value: string | number
  sub?: string
  trend?: 'up' | 'down' | 'flat'
  sentiment?: 'good' | 'warn' | 'bad' | 'neutral'
  className?: string
}

const SENTIMENT_COLOR: Record<string, string> = {
  good:    '#34d399',
  warn:    '#fbbf24',
  bad:     '#fb7185',
  neutral: '#9aafc8',
}

const TREND_ICON: Record<string, string> = {
  up:   '↑',
  down: '↓',
  flat: '→',
}

export default function MetricBlock({
  label,
  value,
  sub,
  trend,
  sentiment = 'neutral',
  className = '',
}: MetricBlockProps) {
  const color = SENTIMENT_COLOR[sentiment]

  return (
    <div
      className={className}
      style={{
        backgroundColor: '#151b27',
        border: '1px solid #28334a',
        borderRadius: '12px',
        padding: '20px 24px',
        display: 'flex',
        flexDirection: 'column',
        gap: '6px',
        boxShadow: '0 2px 12px rgba(0,0,0,0.45)',
      }}
    >
      <span style={{ fontSize: '12px', fontWeight: 500, color: '#6b7fa0', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
        {label}
      </span>
      <span style={{ fontSize: '28px', fontWeight: 700, color, lineHeight: 1.1 }}>
        {value}
        {trend && (
          <span style={{ fontSize: '16px', marginLeft: '6px', opacity: 0.8 }}>
            {TREND_ICON[trend]}
          </span>
        )}
      </span>
      {sub && (
        <span style={{ fontSize: '13px', color: '#6b7fa0' }}>{sub}</span>
      )}
    </div>
  )
}
