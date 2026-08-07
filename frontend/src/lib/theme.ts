// Light theme for the suburb report page, matching picki.com.au's palette:
// white cards on a soft gray page background, pink as the primary/CTA accent,
// blue as secondary, green for positive indicators.
export const colors = {
  pageBg: '#F3F4F6',
  cardBg: '#FFFFFF',
  border: '#E5E7EB',
  textPrimary: '#111827',
  textSecondary: '#6B7280',
  textMuted: '#9CA3AF',
  pink: '#EC018C',
  pinkLight: '#FDE8F5',
  blue: '#2E58A6',
  blueLight: '#E7EDF8',
  green: '#00A94F',
  greenLight: '#E3F9EC',
  amber: '#B45309',
  amberLight: '#FEF3C7',
  rose: '#E11D48',
  roseLight: '#FDE4E8',
}

// Monospace stack for numeric figures (prices, percentages, scores) — tabular
// figures line up in dense grids/tables the way a proportional font can't.
// Falls back through common pre-installed monospace fonts rather than
// bundling a webfont (Phase 3 density pass, WS2 §4 "Bloomberg terminal"
// reference point).
export const fonts = {
  mono: "'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace",
}

// Spacing/sizing tokens for the denser variants introduced in the Phase 3
// density pass — used alongside (not instead of) the ad-hoc inline styles
// already in each page. Compact values are deliberately ~2/3 of the
// pre-existing defaults (24px card padding, 16px grid gap, 160px stat
// column), not an arbitrary redesign.
export const density = {
  cardPaddingCompact: '16px',
  gridGapCompact: '10px',
  statMinWidthCompact: '130px',
}
