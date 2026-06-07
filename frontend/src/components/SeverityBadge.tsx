type Severity = 'good' | 'warn' | 'bad' | 'info' | 'low' | 'medium' | 'high' | 'critical'

interface SeverityBadgeProps {
  level: Severity
  label?: string
}

const SEVERITY_MAP: Record<Severity, { bg: string; color: string; defaultLabel: string }> = {
  good:     { bg: 'rgba(52,211,153,0.15)',  color: '#34d399', defaultLabel: 'Good'     },
  low:      { bg: 'rgba(52,211,153,0.15)',  color: '#34d399', defaultLabel: 'Low'      },
  info:     { bg: 'rgba(56,189,248,0.15)',  color: '#38bdf8', defaultLabel: 'Info'     },
  warn:     { bg: 'rgba(251,191,36,0.15)',  color: '#fbbf24', defaultLabel: 'Moderate' },
  medium:   { bg: 'rgba(251,191,36,0.15)',  color: '#fbbf24', defaultLabel: 'Medium'   },
  bad:      { bg: 'rgba(251,113,133,0.15)', color: '#fb7185', defaultLabel: 'High'     },
  high:     { bg: 'rgba(251,113,133,0.15)', color: '#fb7185', defaultLabel: 'High'     },
  critical: { bg: 'rgba(244,63,94,0.18)',   color: '#f43f5e', defaultLabel: 'Critical' },
}

export default function SeverityBadge({ level, label }: SeverityBadgeProps) {
  const { bg, color, defaultLabel } = SEVERITY_MAP[level]
  return (
    <span
      style={{
        display: 'inline-block',
        padding: '2px 10px',
        borderRadius: '6px',
        fontSize: '12px',
        fontWeight: 600,
        letterSpacing: '0.04em',
        backgroundColor: bg,
        color,
        border: `1px solid ${color}33`,
      }}
    >
      {label ?? defaultLabel}
    </span>
  )
}
