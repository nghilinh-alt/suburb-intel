import { ResponsiveContainer, LineChart, Line, Tooltip, ReferenceLine } from 'recharts'

interface TrendSparklineProps {
  data: number[]
  labels?: string[]
  color?: string
  height?: number
  showTooltip?: boolean
  referenceValue?: number
}

export default function TrendSparkline({
  data,
  labels,
  color = '#2dd4bf',
  height = 48,
  showTooltip = false,
  referenceValue,
}: TrendSparklineProps) {
  if (!data || data.length < 2) return null

  const chartData = data.map((v, i) => ({ v, label: labels?.[i] ?? i }))

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={chartData} margin={{ top: 4, right: 4, left: 4, bottom: 4 }}>
        {referenceValue !== undefined && (
          <ReferenceLine y={referenceValue} stroke="#28334a" strokeDasharray="3 3" />
        )}
        {showTooltip && (
          <Tooltip
            contentStyle={{ backgroundColor: '#151b27', border: '1px solid #28334a', borderRadius: '8px', fontSize: '12px' }}
            itemStyle={{ color: '#cdd8e8' }}
            labelStyle={{ color: '#6b7fa0' }}
            formatter={(v: unknown) => [(v as number).toFixed(1), '']}
            labelFormatter={(i: unknown) => labels?.[i as number] ?? `#${(i as number) + 1}`}
          />
        )}
        <Line
          type="monotone"
          dataKey="v"
          stroke={color}
          strokeWidth={2}
          dot={false}
          activeDot={showTooltip ? { r: 3, fill: color } : false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}
