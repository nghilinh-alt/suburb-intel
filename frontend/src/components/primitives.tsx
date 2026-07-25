// Shared, non-chart UI primitives used across SearchPage/RankingsPage/
// SuburbPage — promoted out of SuburbPage.tsx (which had its own Card/
// Section/StatGrid/Stat/Pill) so all three pages share one definition
// instead of drifting copies (Phase 3 Task 3.1).
import { ReactNode, useState } from 'react'
import { colors, fonts } from '../lib/theme'

/** Small eyebrow label framing Search/Rankings/Suburb as the analyst funnel
 * (macro filter -> shortlist -> deep-dive, WS2 §2) — a light affordance, not
 * a redesign (Phase 3 Task 3.4). */
export function FunnelStep({ step, total, label }: { step: number; total: number; label: string }) {
  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '6px',
        fontSize: '11px',
        fontWeight: 700,
        color: colors.pink,
        textTransform: 'uppercase',
        letterSpacing: '0.04em',
        marginBottom: '6px',
      }}
    >
      <span>
        Step {step} of {total}
      </span>
      <span style={{ color: colors.textMuted, fontWeight: 500, textTransform: 'none', letterSpacing: 'normal' }}>· {label}</span>
    </div>
  )
}

export function Card({
  children,
  style,
  hoverable = false,
}: {
  children: ReactNode
  style?: React.CSSProperties
  hoverable?: boolean
}) {
  const [isHover, setIsHover] = useState(false)
  return (
    <div
      onMouseEnter={() => hoverable && setIsHover(true)}
      onMouseLeave={() => hoverable && setIsHover(false)}
      style={{
        backgroundColor: colors.cardBg,
        border: `1px solid ${isHover ? colors.pink : colors.border}`,
        borderRadius: '12px',
        boxShadow: isHover ? '0 4px 12px rgba(0,0,0,0.08)' : '0 1px 2px rgba(0,0,0,0.04)',
        padding: '24px',
        ...style,
      }}
    >
      {children}
    </div>
  )
}

/** A short, auto-generated plain-English read of what a section's data is
 * doing, shown above the section's charts/stats (WS2 §3-4: HtAG leads every
 * section with this before a single chart; the research recommendation this
 * project is built on). Purely a display component — callers compute the
 * text from already-known data (see SuburbPage.tsx's summary generators). */
export function SectionSummary({ children }: { children: ReactNode }) {
  return (
    <p
      style={{
        fontSize: '13px',
        color: colors.textPrimary,
        backgroundColor: colors.pageBg,
        padding: '8px 12px',
        borderRadius: '8px',
        marginTop: 0,
        marginBottom: '16px',
        fontWeight: 500,
      }}
    >
      {children}
    </p>
  )
}

/** A label with a hover-for-definition affordance — generalises the ad-hoc
 * `title=` tooltip pattern already used on Section's data-vintage badge to
 * any metric label. Dotted underline signals "hover me" without needing an
 * icon. */
export function MetricWithInfo({ label, info }: { label: string; info: string }) {
  return (
    <span title={info} style={{ cursor: 'help', borderBottom: `1px dotted ${colors.textMuted}` }}>
      {label}
    </span>
  )
}

export function Section({
  title,
  subtitle,
  summary,
  dataVintage,
  children,
}: {
  title: string
  subtitle?: string
  summary?: ReactNode
  dataVintage?: string
  children: ReactNode
}) {
  return (
    <Card style={{ marginBottom: '20px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
        <h3 style={{ fontSize: '18px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
          {title}
        </h3>
        {dataVintage && (
          <span
            style={{
              fontSize: '11px',
              fontWeight: 600,
              color: colors.amber,
              backgroundColor: colors.amberLight,
              padding: '3px 9px',
              borderRadius: '999px',
            }}
            title="This section's figures are only as recent as this data source's last update."
          >
            {dataVintage}
          </span>
        )}
      </div>
      {subtitle && (
        <p style={{ fontSize: '13px', color: colors.textMuted, marginTop: '4px', marginBottom: summary ? '12px' : '16px' }}>
          {subtitle}
        </p>
      )}
      {summary && <SectionSummary>{summary}</SectionSummary>}
      <div style={{ marginTop: subtitle || summary ? 0 : '16px' }}>{children}</div>
    </Card>
  )
}

export function StatGrid({ children, compact = false }: { children: ReactNode; compact?: boolean }) {
  return (
    <div
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(auto-fill, minmax(${compact ? '130px' : '160px'}, 1fr))`,
        gap: compact ? '10px' : '16px',
      }}
    >
      {children}
    </div>
  )
}

export function Stat({ label, value, info }: { label: string; value: string; info?: string }) {
  return (
    <div>
      <div style={{ fontSize: '12px', color: colors.textMuted, marginBottom: '4px' }}>
        {info ? <MetricWithInfo label={label} info={info} /> : label}
      </div>
      <div style={{ fontSize: '20px', fontWeight: 600, color: colors.textPrimary, fontFamily: fonts.mono }}>
        {value}
      </div>
    </div>
  )
}

export function MiniStat({ label, value, info }: { label: string; value: string; info?: string }) {
  return (
    <div>
      <div style={{ fontSize: '11px', color: colors.textMuted }}>
        {info ? <MetricWithInfo label={label} info={info} /> : label}
      </div>
      <div style={{ fontSize: '14px', fontWeight: 600, color: colors.textPrimary, fontFamily: fonts.mono }}>
        {value}
      </div>
    </div>
  )
}

export function Pill({ children, tone = 'blue' }: { children: ReactNode; tone?: 'blue' | 'pink' | 'green' | 'amber' }) {
  const toneColors = {
    blue: { bg: colors.blueLight, fg: colors.blue },
    pink: { bg: colors.pinkLight, fg: colors.pink },
    green: { bg: colors.greenLight, fg: colors.green },
    amber: { bg: colors.amberLight, fg: colors.amber },
  }[tone]
  return (
    <span
      style={{
        display: 'inline-block',
        backgroundColor: toneColors.bg,
        color: toneColors.fg,
        padding: '6px 12px',
        borderRadius: '999px',
        fontSize: '13px',
        fontWeight: 500,
      }}
    >
      {children}
    </span>
  )
}
