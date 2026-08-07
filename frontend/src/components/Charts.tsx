// Lightweight dependency-free SVG/CSS chart primitives for the suburb report
// page. No charting library — these are simple enough (bars, a donut, a
// 3-point trend line) that a dependency would cost more than it saves.
import { colors } from '../lib/theme'

export interface BarItem {
  label: string
  value: number
  formattedValue?: string
  onClick?: () => void
  info?: string
}

/** Horizontal bar list — good for percentages, deciles, or counts where you
 * want to scan several labeled values at once. `max` defaults to the largest
 * item's value (or 100 if `isPercent` is set). An item with `onClick` renders
 * as a clickable row (e.g. to jump to a related section elsewhere on the page). */
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
        <div
          key={item.label}
          onClick={item.onClick}
          role={item.onClick ? 'button' : undefined}
          tabIndex={item.onClick ? 0 : undefined}
          onKeyDown={item.onClick ? (e) => (e.key === 'Enter' || e.key === ' ') && item.onClick!() : undefined}
          style={item.onClick ? { cursor: 'pointer' } : undefined}
        >
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              fontSize: '13px',
              marginBottom: '4px',
            }}
          >
            <span
              title={item.info}
              style={{
                color: item.onClick ? colors.pink : colors.textSecondary,
                textDecoration: item.onClick ? 'underline' : undefined,
                borderBottom: item.info ? `1px dotted ${colors.textMuted}` : undefined,
                cursor: item.info ? 'help' : undefined,
              }}
            >
              {item.label}
            </span>
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

/** Minimal inline trend line for dense contexts (table cells, stat card
 * corners) — no axis, dots, or labels, unlike TrendLine. Just the shape of
 * the trend. Colors green/amber by direction (last vs first point) unless a
 * fixed `color` is passed. */
export function Sparkline({
  values,
  color,
  width = 72,
  height = 24,
}: {
  values: number[]
  color?: string
  width?: number
  height?: number
}) {
  if (values.length < 2) return null

  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const stepX = width / (values.length - 1)
  const points = values
    .map((v, i) => `${i * stepX},${height - ((v - min) / range) * height}`)
    .join(' ')

  const lineColor = color ?? (values[values.length - 1] >= values[0] ? colors.green : colors.amber)

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ display: 'block' }}>
      <polyline points={points} fill="none" stroke={lineColor} strokeWidth={1.5} />
    </svg>
  )
}

/** DSR-style "Context Ruler" — places a value on a scale against a reference
 * baseline (e.g. the national median) so an unfamiliar number ("is 4.6
 * inventory-months good?") is instantly legible without memorising what's
 * normal. `higherIsBetter` colors the value marker (green/amber) relative to
 * the baseline; omit it (or pass null) for metrics with no inherent
 * direction. `min`/`max` set the track's display range — values outside it
 * clamp to the edge rather than overflowing. */
export function ContextRuler({
  value,
  baseline,
  min,
  max,
  label,
  formatValue = (v) => v.toLocaleString(),
  baselineLabel = 'national median',
  higherIsBetter = null,
}: {
  value: number
  baseline: number
  min: number
  max: number
  label?: string
  formatValue?: (v: number) => string
  baselineLabel?: string
  higherIsBetter?: boolean | null
}) {
  const clampPct = (v: number) => Math.max(0, Math.min(100, ((v - min) / (max - min || 1)) * 100))
  const valuePct = clampPct(value)
  const baselinePct = clampPct(baseline)

  // Good/bad only exists when the metric has a direction. `null` = neutral
  // (e.g. median price — dearer is neither good nor bad on its own).
  const isBetter =
    higherIsBetter == null ? null : higherIsBetter ? value >= baseline : value <= baseline
  const markerColor = isBetter == null ? colors.blue : isBetter ? colors.green : colors.amber
  const deltaColor = isBetter == null ? colors.textSecondary : isBetter ? colors.green : colors.amber

  // Plain-language comparison — the actual point of the ruler, e.g. "18% above
  // national median". Spelled out in words so the colour isn't load-bearing.
  const pctDiff = baseline ? ((value - baseline) / Math.abs(baseline)) * 100 : 0
  const deltaText =
    Math.abs(pctDiff) < 1
      ? `in line with ${baselineLabel}`
      : `${Math.abs(pctDiff).toFixed(0)}% ${value > baseline ? 'above' : 'below'} ${baselineLabel}`

  // Directional track: reddish (worse) → greenish (better), flipped when lower
  // is better; a neutral ramp when the metric has no inherent direction.
  const trackBackground =
    isBetter == null
      ? `linear-gradient(90deg, ${colors.blueLight}, ${colors.pageBg})`
      : higherIsBetter
        ? `linear-gradient(90deg, ${colors.roseLight}, ${colors.pageBg} 55%, ${colors.greenLight})`
        : `linear-gradient(90deg, ${colors.greenLight}, ${colors.pageBg} 45%, ${colors.roseLight})`

  // Keep the baseline caption on-screen when its tick sits near either edge.
  const captionLeft = baselinePct > 85 ? 'auto' : baselinePct < 15 ? '0' : `${baselinePct}%`
  const captionRight = baselinePct > 85 ? '0' : 'auto'
  const captionAlign: 'left' | 'center' | 'right' =
    baselinePct < 15 ? 'left' : baselinePct > 85 ? 'right' : 'center'
  const captionTransform = baselinePct >= 15 && baselinePct <= 85 ? 'translateX(-50%)' : 'none'

  return (
    <div style={{ width: '100%' }}>
      {label && (
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: '8px', fontSize: '13px' }}>
          <span style={{ color: colors.textSecondary }}>{label}</span>
          <span style={{ color: colors.textPrimary, fontWeight: 600 }}>{formatValue(value)}</span>
        </div>
      )}
      <div style={{ fontSize: '12px', fontWeight: 600, color: deltaColor, marginTop: '2px' }}>{deltaText}</div>
      <div
        style={{
          position: 'relative',
          height: '8px',
          borderRadius: '999px',
          background: trackBackground,
          border: `1px solid ${colors.border}`,
          marginTop: '10px',
        }}
      >
        {/* national-median reference tick */}
        <div
          title={`${baselineLabel}: ${formatValue(baseline)}`}
          style={{
            position: 'absolute',
            left: `${baselinePct}%`,
            top: '-4px',
            width: '2px',
            height: '16px',
            backgroundColor: colors.textSecondary,
            transform: 'translateX(-1px)',
          }}
        />
        {/* this-suburb marker */}
        <div
          title={`This suburb: ${formatValue(value)}`}
          style={{
            position: 'absolute',
            left: `${valuePct}%`,
            top: '-5px',
            width: '18px',
            height: '18px',
            borderRadius: '50%',
            backgroundColor: markerColor,
            border: '2px solid #FFFFFF',
            boxShadow: '0 1px 3px rgba(0,0,0,0.3)',
            transform: 'translateX(-9px)',
          }}
        />
      </div>
      {/* baseline caption, anchored under its tick */}
      <div style={{ position: 'relative', height: '14px', marginTop: '5px' }}>
        <span
          style={{
            position: 'absolute',
            left: captionLeft,
            right: captionRight,
            textAlign: captionAlign,
            transform: captionTransform,
            fontSize: '10px',
            color: colors.textMuted,
            whiteSpace: 'nowrap',
          }}
        >
          ▏{baselineLabel} {formatValue(baseline)}
        </span>
      </div>
      {/* scale endpoints + this-suburb legend */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          fontSize: '10px',
          color: colors.textMuted,
          marginTop: '2px',
        }}
      >
        <span>{formatValue(min)}</span>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <span style={{ width: '8px', height: '8px', borderRadius: '50%', backgroundColor: markerColor, display: 'inline-block' }} />
          this suburb
        </span>
        <span>{formatValue(max)}</span>
      </div>
    </div>
  )
}

export type CyclePosition =
  | 'start_of_recovery'
  | 'rising_market'
  | 'approaching_peak'
  | 'peak_of_market'
  | 'starting_to_decline'
  | 'declining_market'
  | 'approaching_bottom'
  | 'bottom_of_market'

// Clockwise from 12 o'clock, matching the classic property-cycle clock
// (Herron Todd White's is the best-known version) — each entry's index * 45°
// is its position on the ring, 0° = straight up.
const CYCLE_SEGMENTS: { key: CyclePosition; lines: [string, string] }[] = [
  { key: 'peak_of_market', lines: ['Peak of', 'Market'] },
  { key: 'starting_to_decline', lines: ['Starting to', 'decline'] },
  { key: 'declining_market', lines: ['Declining', 'Market'] },
  { key: 'approaching_bottom', lines: ['Approaching', 'Bottom of Market'] },
  { key: 'bottom_of_market', lines: ['Bottom of', 'Market'] },
  { key: 'start_of_recovery', lines: ['Start of', 'Recovery'] },
  { key: 'rising_market', lines: ['Rising', 'Market'] },
  { key: 'approaching_peak', lines: ['Approaching', 'Peak of Market'] },
]

/** The 8-position property cycle clock. `position` selects which segment is
 * highlighted; `confidence` (0-1) is shown as a caveat, since this is a
 * derived model (see app.core.momentum.classify_property_cycle_position),
 * not a measurement — a low confidence means the underlying signal is weak
 * or the suburb sits near a boundary between two phases. */
export function PropertyCycleClock({
  position,
  confidence,
  size = 420,
}: {
  position: CyclePosition | null
  confidence: number | null
  size?: number
}) {
  if (!position) return null

  // Fixed pixel budget rather than deriving from `size`: the longest label
  // ("Bottom of Market") needs roughly 55-60px of half-width at this font
  // size, so labelRadius needs at least that much clearance to the edge.
  const strokeWidth = 26
  const radius = 100
  const center = size / 2
  const circumference = 2 * Math.PI * radius
  const gapFraction = 0.02
  const dash = (1 / 8 - gapFraction) * circumference
  const gapDash = circumference - dash
  const labelRadius = radius + strokeWidth / 2 + 24

  const activeIndex = CYCLE_SEGMENTS.findIndex((s) => s.key === position)
  const activeSegment = CYCLE_SEGMENTS[activeIndex]

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        style={{ width: '100%', maxWidth: `${size}px`, height: 'auto', display: 'block' }}
      >
        <g style={{ transform: 'rotate(-90deg)', transformOrigin: `${center}px ${center}px` }}>
          {CYCLE_SEGMENTS.map((seg, i) => {
            const isActive = i === activeIndex
            const offset = -(i / 8) * circumference
            return (
              <circle
                key={seg.key}
                cx={center}
                cy={center}
                r={radius}
                fill="none"
                stroke={isActive ? colors.blue : colors.border}
                strokeWidth={isActive ? strokeWidth + 8 : strokeWidth}
                strokeDasharray={`${dash} ${gapDash}`}
                strokeDashoffset={offset}
              />
            )
          })}
        </g>

        {CYCLE_SEGMENTS.map((seg, i) => {
          const compassDeg = i * 45
          const rad = ((compassDeg - 90) * Math.PI) / 180
          const x = center + labelRadius * Math.cos(rad)
          const y = center + labelRadius * Math.sin(rad)
          const isActive = i === activeIndex
          return (
            <text
              key={seg.key}
              x={x}
              y={y}
              textAnchor="middle"
              fontSize="11"
              fontWeight={isActive ? 700 : 500}
              fill={isActive ? colors.blue : colors.textMuted}
            >
              <tspan x={x} dy="-4">{seg.lines[0]}</tspan>
              <tspan x={x} dy="13">{seg.lines[1]}</tspan>
            </text>
          )
        })}

        <text x={center} y={center - 8} textAnchor="middle" fontSize="16" fontWeight={700} fill={colors.textPrimary}>
          {activeSegment.lines[0]}
        </text>
        <text x={center} y={center + 12} textAnchor="middle" fontSize="16" fontWeight={700} fill={colors.textPrimary}>
          {activeSegment.lines[1]}
        </text>
        {confidence != null && (
          <text x={center} y={center + 32} textAnchor="middle" fontSize="11" fill={colors.textMuted}>
            {Math.round(confidence * 100)}% signal strength
          </text>
        )}
      </svg>
    </div>
  )
}
