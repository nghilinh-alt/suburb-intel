// Lightweight dependency-free SVG/CSS chart primitives for the suburb report
// page. No charting library — these are simple enough (bars, a donut, a
// 3-point trend line) that a dependency would cost more than it saves.
import { colors } from '../lib/theme'

export interface BarItem {
  label: string
  value: number
  formattedValue?: string
}

/** Horizontal bar list — good for percentages, deciles, or counts where you
 * want to scan several labeled values at once. `max` defaults to the largest
 * item's value (or 100 if `isPercent` is set). */
export function HorizontalBars({
  items,
  max,
  isPercent = false,
  color = colors.blue,
}: {
  items: BarItem[]
  max?: number
  isPercent?: boolean
  color?: string
}) {
  const effectiveMax = max ?? (isPercent ? 100 : Math.max(...items.map((i) => i.value), 1))
  return (
    <div style={{ display: 'grid', gap: '12px' }}>
      {items.map((item) => (
        <div key={item.label}>
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '13px',
              marginBottom: '4px',
            }}
          >
            <span style={{ color: colors.textSecondary }}>{item.label}</span>
            <span style={{ color: colors.textPrimary, fontWeight: 600 }}>
              {item.formattedValue ?? item.value}
            </span>
          </div>
          <div
            style={{
              height: '8px',
              borderRadius: '999px',
              backgroundColor: colors.pageBg,
              overflow: 'hidden',
            }}
          >
            <div
              style={{
                height: '100%',
                width: `${Math.min((item.value / effectiveMax) * 100, 100)}%`,
                backgroundColor: color,
                borderRadius: '999px',
              }}
            />
          </div>
        </div>
      ))}
    </div>
  )
}

export interface DonutSegment {
  label: string
  value: number
  color: string
}

/** Donut chart via stroke-dasharray segments on concentric circles — no path
 * math needed. Good for splits that should visually sum to a whole (tenure,
 * dwelling type, commute mode). */
export function DonutChart({ segments, size = 140 }: { segments: DonutSegment[]; size?: number }) {
  const total = segments.reduce((sum, s) => sum + s.value, 0)
  if (total <= 0) return null

  const strokeWidth = 22
  const radius = (size - strokeWidth) / 2
  const circumference = 2 * Math.PI * radius

  let cumulative = 0
  const arcs = segments.map((s) => {
    const fraction = s.value / total
    const dash = fraction * circumference
    const offset = -cumulative * circumference
    cumulative += fraction
    return { ...s, dash, offset, fraction }
  })

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '20px', flexWrap: 'wrap' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ transform: 'rotate(-90deg)' }}>
        {arcs.map((a) => (
          <circle
            key={a.label}
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={a.color}
            strokeWidth={strokeWidth}
            strokeDasharray={`${a.dash} ${circumference - a.dash}`}
            strokeDashoffset={a.offset}
          />
        ))}
      </svg>
      <div style={{ display: 'grid', gap: '6px' }}>
        {arcs.map((a) => (
          <div key={a.label} style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
            <span
              style={{
                width: '10px',
                height: '10px',
                borderRadius: '3px',
                backgroundColor: a.color,
                display: 'inline-block',
              }}
            />
            <span style={{ color: colors.textSecondary }}>{a.label}</span>
            <span style={{ color: colors.textPrimary, fontWeight: 600 }}>
              {(a.fraction * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

export interface TrendPoint {
  label: string
  value: number
}

/** Line chart for ordered points — a handful (e.g. population now vs
 * projected) or a denser monthly series (e.g. price history). For dense
 * series, pass `maxLabels` to thin out which points get a label/dot so the
 * chart stays readable; the line itself always uses every point. */
export function TrendLine({
  points,
  color = colors.pink,
  width = 400,
  height = 140,
  maxLabels = 8,
}: {
  points: TrendPoint[]
  color?: string
  width?: number
  height?: number
  maxLabels?: number
}) {
  if (points.length < 2) return null

  const padding = 32
  const values = points.map((p) => p.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1

  const stepX = (width - padding * 2) / (points.length - 1)
  const coords = points.map((p, i) => {
    const x = padding + i * stepX
    const y = height - padding - ((p.value - min) / range) * (height - padding * 2)
    return { x, y, ...p }
  })

  const linePath = coords.map((c) => `${c.x},${c.y}`).join(' ')

  const labelEvery = Math.max(1, Math.ceil(coords.length / maxLabels))
  const labeledCoords = coords.filter(
    (_, i) => i % labelEvery === 0 || i === coords.length - 1
  )

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      style={{ width: '100%', maxWidth: `${width}px`, height: 'auto', display: 'block' }}
    >
      <polyline points={linePath} fill="none" stroke={color} strokeWidth={2.5} />
      {labeledCoords.map((c) => (
        <g key={c.label}>
          <circle cx={c.x} cy={c.y} r={4} fill={color} />
          <text x={c.x} y={c.y - 12} textAnchor="middle" fontSize="12" fill={colors.textPrimary} fontWeight={600}>
            {c.value.toLocaleString()}
          </text>
          <text x={c.x} y={height - padding + 20} textAnchor="middle" fontSize="12" fill={colors.textMuted}>
            {c.label}
          </text>
        </g>
      ))}
    </svg>
  )
}
