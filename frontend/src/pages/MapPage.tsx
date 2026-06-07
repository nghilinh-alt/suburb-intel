import { useEffect, useState, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import 'leaflet/dist/leaflet.css'
import L from 'leaflet'
import { usePageTitle } from '../hooks/usePageTitle'

// Fix Leaflet default marker icon (broken in bundlers)
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

interface SA2Feature {
  type: 'Feature'
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: {
    sa2_code: string
    suburb_id: string | null
    sa2_name: string
    state: string
    investment_score: number | null
    liveability_score: number | null
    growth_score: number | null
  }
}

interface GeoJSONFeatureCollection {
  type: 'FeatureCollection'
  features: SA2Feature[]
}

const SCORE_LABELS: Record<string, string> = {
  investment_score:  'Overall Investment',
  liveability_score: 'Liveability',
  growth_score:      'Growth',
}

// DarkWave score colour ramp
function scoreToColor(score: number | null): string {
  if (score == null) return '#36445e'
  if (score >= 7.5)  return '#34d399'   // emerald
  if (score >= 6.5)  return '#6ee7b7'   // emerald-light
  if (score >= 5.5)  return '#fbbf24'   // amber
  if (score >= 4.5)  return '#f59e0b'   // amber-dark
  return '#fb7185'                       // rose
}

function scoreToRadius(score: number | null): number {
  if (score == null) return 5
  return 4 + (score / 10) * 6
}

const STATES = ['NSW', 'VIC', 'QLD', 'WA', 'SA', 'TAS', 'ACT', 'NT']

const STATE_BOUNDS: Record<string, [[number, number], [number, number]]> = {
  NSW: [[-37.5, 140.9], [-28.1, 153.7]],
  VIC: [[-39.2, 140.9], [-33.9, 150.0]],
  QLD: [[-29.2, 137.9], [-9.9,  153.6]],
  WA:  [[-35.1, 113.2], [-13.7, 129.0]],
  SA:  [[-38.1, 129.0], [-25.9, 141.0]],
  TAS: [[-43.7, 143.8], [-39.5, 148.5]],
  ACT: [[-35.9, 148.7], [-35.1, 149.4]],
  NT:  [[-26.0, 129.0], [-10.9, 138.1]],
}

const LEGEND = [
  { label: '7.5+',     color: '#34d399' },
  { label: '6.5–7.5',  color: '#6ee7b7' },
  { label: '5.5–6.5',  color: '#fbbf24' },
  { label: '4.5–5.5',  color: '#f59e0b' },
  { label: '<4.5',     color: '#fb7185' },
  { label: 'No data',  color: '#36445e' },
]

export default function MapPage() {
  const mapRef    = useRef<L.Map | null>(null)
  const layerRef  = useRef<L.LayerGroup | null>(null)
  const [data, setData]               = useState<GeoJSONFeatureCollection | null>(null)
  const [loading, setLoading]         = useState(true)
  const [scoreType, setScoreType]     = useState<keyof typeof SCORE_LABELS>('investment_score')
  const [stateFilter, setStateFilter] = useState('')
  const navigate = useNavigate()
  usePageTitle('Suburb Map')

  // Init map once
  useEffect(() => {
    if (mapRef.current) return
    const map = L.map('suburb-map', {
      center: [-27.0, 134.0],
      zoom: 4,
      zoomControl: true,
    })
    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      attribution: '© OpenStreetMap © CARTO',
      maxZoom: 18,
    }).addTo(map)
    mapRef.current  = map
    layerRef.current = L.layerGroup().addTo(map)
    return () => { map.remove(); mapRef.current = null }
  }, [])

  // Load centroids on mount
  useEffect(() => {
    setLoading(true)
    fetch('/api/map/centroids')
      .then(r => r.json())
      .then((d: GeoJSONFeatureCollection) => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  // Re-render circles when data, scoreType, or stateFilter changes
  useEffect(() => {
    if (!data || !layerRef.current || !mapRef.current) return
    layerRef.current.clearLayers()

    const visible = stateFilter
      ? data.features.filter(f => f.properties.state === stateFilter)
      : data.features

    visible.forEach(feat => {
      const [lon, lat] = feat.geometry.coordinates
      const props = feat.properties
      const score = props[scoreType as keyof typeof props] as number | null

      const circle = L.circleMarker([lat, lon], {
        radius:      scoreToRadius(score),
        fillColor:   scoreToColor(score),
        color:       '#0d1117',
        weight:      0.5,
        fillOpacity: 0.85,
      })

      circle.on('click', () => navigate(props.suburb_id ? `/suburb-group/${props.suburb_id}` : `/suburb/${props.sa2_code}`))
      circle.bindTooltip(
        `<b style="color:#cdd8e8">${props.sa2_name}</b> <span style="color:#6b7fa0">${props.state}</span><br/>
         <span style="color:#6b7fa0">${SCORE_LABELS[scoreType]}:</span> <b style="color:${scoreToColor(score)}">${score?.toFixed(1) ?? '—'}</b>`,
        { direction: 'top', offset: [0, -4], className: 'dw-tooltip' }
      )
      layerRef.current!.addLayer(circle)
    })

    if (stateFilter && STATE_BOUNDS[stateFilter] && mapRef.current) {
      mapRef.current.fitBounds(STATE_BOUNDS[stateFilter], { padding: [20, 20] })
    } else if (!stateFilter && mapRef.current) {
      mapRef.current.setView([-27.0, 134.0], 4)
    }
  }, [data, scoreType, stateFilter, navigate])

  return (
    <div style={{ maxWidth: '1280px', margin: '0 auto' }}>
      {/* Header row */}
      <div style={{ marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ fontSize: '28px', fontWeight: 800, margin: '0 0 4px', color: '#cdd8e8', letterSpacing: '-0.02em' }}>
            Suburb Map
          </h1>
          <p style={{ color: '#6b7fa0', margin: 0, fontSize: '14px' }}>
            {loading ? 'Loading…' : `${data?.features.length ?? 0} SA2 regions · click any dot to view report`}
          </p>
        </div>

        <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', alignItems: 'center' }}>
          {Object.entries(SCORE_LABELS).map(([key, label]) => (
            <button key={key} onClick={() => setScoreType(key)}
              style={{
                padding: '7px 14px', borderRadius: '8px', fontSize: '13px', cursor: 'pointer',
                backgroundColor: scoreType === key ? '#2dd4bf' : '#151b27',
                color:           scoreType === key ? '#0d1117'  : '#9aafc8',
                border:          scoreType === key ? 'none'     : '1px solid #28334a',
                fontWeight:      scoreType === key ? 700        : 400,
                transition: 'all 0.15s',
              }}>
              {label}
            </button>
          ))}
          <select value={stateFilter} onChange={e => setStateFilter(e.target.value)}
            style={{ padding: '7px 12px', backgroundColor: '#151b27', color: '#9aafc8', border: '1px solid #28334a', borderRadius: '8px', cursor: 'pointer', fontSize: '13px' }}>
            <option value="">All States</option>
            {STATES.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
        </div>
      </div>

      {/* Legend */}
      <div style={{ display: 'flex', gap: '16px', marginBottom: '12px', flexWrap: 'wrap' }}>
        {LEGEND.map(({ label, color }) => (
          <div key={label} style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: '#6b7fa0' }}>
            <div style={{ width: '10px', height: '10px', borderRadius: '50%', backgroundColor: color, flexShrink: 0 }} />
            {label}
          </div>
        ))}
      </div>

      {/* Map container */}
      <div id="suburb-map" style={{ height: '620px', borderRadius: '12px', overflow: 'hidden', border: '1px solid #28334a' }} />
    </div>
  )
}
