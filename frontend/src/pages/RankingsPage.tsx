import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { Card, FunnelStep } from '../components/primitives'
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
  { value: 'gov_investment_score', label: 'Government Investment' },
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
    <div
      style={{
        backgroundColor: colors.pageBg,
        backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(15,23,42,0.06) 1px, transparent 0)',
        backgroundSize: '18px 18px',
        margin: '-20px',
        padding: '20px',
        minHeight: 'calc(100vh - 40px)',
      }}
    >
      <div style={{ maxWidth: '900px', margin: '0 auto' }}>
        <div style={{ marginBottom: '24px' }}>
          <FunnelStep step={2} total={3} label="Shortlist" />
          <h1 style={{ fontSize: '32px', margin: 0, color: colors.textPrimary }}>Top Suburbs</h1>
          <p style={{ color: colors.textMuted, fontSize: '14px', marginTop: '6px' }}>
            Ranked by momentum, supply/demand pressure, or composite score — every row shows acceleration and growth/yield
            positioning regardless of which you sort by. Click a suburb for the full deep-dive report, or head back to{' '}
            <Link to="/" style={{ color: colors.pink, fontWeight: 600 }}>
              Search
            </Link>{' '}
            to refine the macro filters.
          </p>
        </div>

        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginBottom: '24px' }}>
          {SCORE_TABS.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setScoreType(tab.value)}
              style={{
                padding: '10px 18px',
                fontSize: '13px',
                fontWeight: 600,
                borderRadius: '999px',
                border: `1px solid ${scoreType === tab.value ? colors.pink : colors.border}`,
                backgroundColor: scoreType === tab.value ? colors.pinkLight : colors.cardBg,
                color: scoreType === tab.value ? colors.pink : colors.textSecondary,
                cursor: 'pointer',
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {state.status === 'loading' && <p style={{ color: colors.textMuted }}>Loading rankings...</p>}

        {state.status === 'error' && (
          <Card>
            <p style={{ color: '#B91C1C', margin: 0 }}>{state.message}</p>
          </Card>
        )}

        {state.status === 'ready' && (
          <>
            {state.data.rankings.length === 0 ? (
              <Card>
                <p style={{ color: colors.textMuted, margin: 0 }}>No ranked suburbs yet.</p>
              </Card>
            ) : (
              <div style={{ display: 'grid', gap: '12px' }}>
                {state.data.rankings.map((s) => (
                  <RankRow key={s.sa2_code} suburb={s} scoreType={scoreType} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
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
      <Card
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '20px 24px',
          border: `1px solid ${isTop ? colors.pink : colors.border}`,
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <span
            style={{
              fontSize: '15px',
              fontWeight: 700,
              fontFamily: fonts.mono,
              color: isTop ? colors.pink : colors.textMuted,
              width: '32px',
              textAlign: 'center',
            }}
          >
            #{suburb.rank}
          </span>
          <div>
            <h3 style={{ fontSize: '17px', fontWeight: 600, color: colors.textPrimary, margin: 0 }}>
              {suburb.sa2_name}
              <span style={{ color: colors.textMuted, fontWeight: 400, fontSize: '13px', marginLeft: '8px' }}>
                {suburb.state}
              </span>
            </h3>
            <p style={{ color: colors.textMuted, fontSize: '12px', margin: '2px 0 0 0' }}>
              SA2: {suburb.sa2_code}
              {suburb.distance_to_cbd_km != null && ` · ${suburb.distance_to_cbd_km.toFixed(1)} km to CBD`}
            </p>
            <div style={{ display: 'flex', gap: '6px', marginTop: '8px', flexWrap: 'wrap' }}>
              <MomentumBadge phase={suburb.momentum_phase} />
              {suburb.growth_yield_quadrant && (
                <Badge tone="neutral">{QUADRANT_LABELS[suburb.growth_yield_quadrant]}</Badge>
              )}
            </div>
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: '28px', fontWeight: 700, color: colors.textPrimary, fontFamily: fonts.mono }}>{scoreLabel ?? '—'}</div>
          <span style={{ color: colors.textMuted, fontSize: '11px' }}>{scoreUnitLabel}</span>
        </div>
      </Card>
    </Link>
  )
}

function MomentumBadge({ phase }: { phase: RankedSuburb['momentum_phase'] }) {
  if (!phase) return null
  const config = {
    accelerating: { arrow: '▲', label: 'Accelerating', tone: 'positive' as const },
    steady: { arrow: '→', label: 'Steady', tone: 'neutral' as const },
    cooling: { arrow: '▼', label: 'Cooling', tone: 'negative' as const },
  }[phase]
  return (
    <Badge tone={config.tone}>
      {config.arrow} {config.label}
    </Badge>
  )
}

function Badge({ children, tone }: { children: React.ReactNode; tone: 'positive' | 'negative' | 'neutral' }) {
  const toneColors = {
    positive: { bg: colors.greenLight, fg: colors.green },
    negative: { bg: colors.amberLight, fg: colors.amber },
    neutral: { bg: colors.blueLight, fg: colors.blue },
  }[tone]
  return (
    <span
      style={{
        display: 'inline-block',
        fontSize: '11px',
        fontWeight: 600,
        padding: '3px 9px',
        borderRadius: '999px',
        backgroundColor: toneColors.bg,
        color: toneColors.fg,
      }}
    >
      {children}
    </span>
  )
}

