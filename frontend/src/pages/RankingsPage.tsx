import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card } from '../components/primitives'
import { getRankings, type RankedSuburb, type RankingsResponse, type ScoreType } from '../lib/api'
import { colors, fonts } from '../lib/theme'

const SCORE_TABS: { value: ScoreType; label: string }[] = [
  { value: 'momentum_score', label: 'Momentum' },
  { value: 'scarcity_score', label: 'Supply Scarcity' },
  { value: 'investment_score', label: 'Investment' },
  { value: 'economic_score', label: 'Economic' },
  { value: 'demographic_score', label: 'Demographic' },
  { value: 'housing_pressure_score', label: 'Housing Pressure' },
  { value: 'resilience_score', label: 'Resilience' },
  { value: 'gov_investment_score', label: 'Gov. Investment' },
]

const QUADRANT_LABELS: Record<string, string> = {
  hot: 'Hot',
  growth_play: 'Growth play',
  cash_flow_play: 'Cash-flow play',
  avoid: 'Avoid',
}

type State =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; data: RankingsResponse }

export default function RankingsPage() {
  const [scoreType, setScoreType] = useState<ScoreType>('momentum_score')
  const [state, setState] = useState<State>({ status: 'loading' })

  useEffect(() => {
    setState({ status: 'loading' })
    getRankings(scoreType, 25)
      .then((data) => setState({ status: 'ready', data }))
      .catch((err) =>
        setState({ status: 'error', message: err instanceof Error ? err.message : 'Failed to load rankings.' }),
      )
  }, [scoreType])

  return (
    <div>
      {/* Header */}
      <div style={{ marginBottom: '28px' }}>
        <h1 style={{ fontSize: '26px', fontWeight: 700, margin: '0 0 4px 0', color: colors.textPrimary, letterSpacing: '-0.02em' }}>
          Top Suburbs
        </h1>
        <p style={{ color: colors.textMuted, fontSize: '14px', margin: 0 }}>
          Ranked by momentum, supply/demand pressure, or composite score. Click a suburb for the full report, or{' '}
          <Link to="/" style={{ color: colors.pink, fontWeight: 600, textDecoration: 'none' }}>
            Search
          </Link>{' '}
          to refine filters.
        </p>
      </div>

      {/* Score type tabs */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '24px' }}>
        {SCORE_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setScoreType(tab.value)}
            style={{
              padding: '8px 16px',
              fontSize: '13px',
              fontWeight: 500,
              borderRadius: '999px',
              border: `1px solid ${scoreType === tab.value ? colors.pink : colors.border}`,
              backgroundColor: scoreType === tab.value ? colors.pink : colors.cardBg,
              color: scoreType === tab.value ? '#ffffff' : colors.textSecondary,
              cursor: 'pointer',
              boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
              transition: 'all 0.15s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {state.status === 'loading' && (
        <p style={{ color: colors.textMuted }}>Loading rankings…</p>
      )}

      {state.status === 'error' && (
        <Card>
          <p style={{ color: '#b91c1c', margin: 0 }}>{state.message}</p>
        </Card>
      )}

      {state.status === 'ready' && (
        <>
          {state.data.rankings.length === 0 ? (
            <Card>
              <p style={{ color: colors.textMuted, margin: 0 }}>No ranked suburbs yet.</p>
            </Card>
          ) : (
            <div style={{ display: 'grid', gap: '10px' }}>
              {state.data.rankings.map((s) => (
                <RankRow key={s.sa2_code} suburb={s} scoreType={scoreType} />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}

function RankRow({ suburb, scoreType }: { suburb: RankedSuburb; scoreType: ScoreType }) {
  const score = suburb[scoreType]
  const isTop = suburb.rank === 1
  const isMomentum = scoreType === 'momentum_score'
  const scoreLabel = isMomentum && score != null && score > 0 ? `+${score.toFixed(1)}` : score?.toFixed(1)
  const scoreUnitLabel = isMomentum ? 'momentum' : scoreType === 'scarcity_score' ? 'scarcity' : 'score'

  return (
    <Link to={`/suburb/${suburb.sa2_code}`} style={{ textDecoration: 'none' }}>
      <div
        style={{
          backgroundColor: colors.cardBg,
          border: `1px solid ${isTop ? colors.pink : colors.border}`,
          borderRadius: '12px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.05)',
          padding: '16px 20px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: '16px',
          transition: 'border-color 0.15s, box-shadow 0.15s',
          cursor: 'pointer',
        }}
        onMouseEnter={(e) => {
          (e.currentTarget as HTMLDivElement).style.borderColor = colors.pink
          ;(e.currentTarget as HTMLDivElement).style.boxShadow = '0 4px 12px rgba(99,102,241,0.12)'
        }}
        onMouseLeave={(e) => {
          (e.currentTarget as HTMLDivElement).style.borderColor = isTop ? colors.pink : colors.border
          ;(e.currentTarget as HTMLDivElement).style.boxShadow = '0 1px 3px rgba(0,0,0,0.05)'
        }}
      >
        {/* Rank + suburb info */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flex: 1, minWidth: 0 }}>
          <span style={{
            fontSize: '14px',
            fontWeight: 700,
            fontFamily: fonts.mono,
            color: isTop ? colors.pink : colors.textMuted,
            width: '28px',
            textAlign: 'center',
            flexShrink: 0,
          }}>
            #{suburb.rank}
          </span>

          <div style={{ minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexWrap: 'wrap' }}>
              <h3 style={{ fontSize: '16px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
                {suburb.sa2_name}
              </h3>
              <span style={{
                fontSize: '10px',
                fontWeight: 700,
                color: colors.textMuted,
                backgroundColor: '#f1f5f9',
                padding: '2px 6px',
                borderRadius: '4px',
                letterSpacing: '0.04em',
              }}>
                {suburb.state}
              </span>
            </div>
            <p style={{ color: colors.textMuted, fontSize: '12px', margin: '2px 0 0 0', fontFamily: fonts.mono }}>
              {suburb.sa2_code}
              {suburb.distance_to_cbd_km != null && ` · ${suburb.distance_to_cbd_km.toFixed(1)} km to CBD`}
            </p>
            <div style={{ display: 'flex', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
              <MomentumBadge phase={suburb.momentum_phase} />
              {suburb.growth_yield_quadrant && (
                <QuadrantBadge quadrant={suburb.growth_yield_quadrant} />
              )}
            </div>
          </div>
        </div>

        {/* Divider */}
        <div style={{ width: '1px', height: '40px', backgroundColor: colors.border, flexShrink: 0, display: 'none' }} className="md-divider" />

        {/* Score */}
        <div style={{ textAlign: 'right', flexShrink: 0 }}>
          <div style={{ fontSize: '26px', fontWeight: 700, color: colors.pink, fontFamily: fonts.mono, lineHeight: 1 }}>
            {scoreLabel ?? '—'}
          </div>
          <span style={{ color: colors.textMuted, fontSize: '10px', fontWeight: 600, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            {scoreUnitLabel}
          </span>
        </div>
      </div>
    </Link>
  )
}

function MomentumBadge({ phase }: { phase: RankedSuburb['momentum_phase'] }) {
  if (!phase) return null
  const config: Record<string, { icon: string; label: string; bg: string; fg: string; border: string }> = {
    accelerating: {
      icon: '▲',
      label: 'Accelerating',
      bg: '#f0fdf4',
      fg: '#15803d',
      border: '#bbf7d0',
    },
    steady: {
      icon: '→',
      label: 'Steady',
      bg: '#f8fafc',
      fg: '#64748b',
      border: '#e2e8f0',
    },
    cooling: {
      icon: '▼',
      label: 'Cooling',
      bg: '#fffbeb',
      fg: '#b45309',
      border: '#fde68a',
    },
  }
  const c = config[phase]
  if (!c) return null
  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '4px',
      fontSize: '11px',
      fontWeight: 600,
      padding: '3px 9px',
      borderRadius: '999px',
      backgroundColor: c.bg,
      color: c.fg,
      border: `1px solid ${c.border}`,
    }}>
      {c.icon} {c.label}
    </span>
  )
}

function QuadrantBadge({ quadrant }: { quadrant: string }) {
  const label = QUADRANT_LABELS[quadrant]
  if (!label) return null

  const style: Record<string, { bg: string; fg: string; border: string }> = {
    hot: { bg: '#fff1f2', fg: '#be123c', border: '#fecdd3' },
    growth_play: { bg: '#eff6ff', fg: '#1d4ed8', border: '#bfdbfe' },
    cash_flow_play: { bg: '#f5f3ff', fg: '#6d28d9', border: '#ddd6fe' },
    avoid: { bg: '#f8fafc', fg: '#64748b', border: '#e2e8f0' },
  }
  const s = style[quadrant] ?? style.avoid

  return (
    <span style={{
      display: 'inline-block',
      fontSize: '11px',
      fontWeight: 600,
      padding: '3px 9px',
      borderRadius: '999px',
      backgroundColor: s.bg,
      color: s.fg,
      border: `1px solid ${s.border}`,
    }}>
      {label}
    </span>
  )
}
