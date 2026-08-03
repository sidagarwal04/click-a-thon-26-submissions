import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatMetricValue, metricLabel } from './config.js'

const COLORS = ['#3db8a0', '#e0a23a', '#5a9fd4', '#e85d4c']

function shortTick(t) {
  if (!t) return ''
  const d = new Date(t.includes('T') ? t : t.replace(' ', 'T') + 'Z')
  if (Number.isNaN(d.getTime())) return String(t).slice(5, 16)
  return d.toLocaleString('en-GB', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: 'UTC',
  })
}

export default function DashboardChart({
  meta,
  metricId,
  colorIndex = 0,
  timeseries = [],
  compareTimeseries = [],
  compareEnabled,
}) {
  const stroke = COLORS[colorIndex % COLORS.length]
  const data = timeseries.map((row, i) => {
    const point = {
      t: row.t,
      current: Number(row[metricId]) || 0,
    }
    if (compareEnabled && compareTimeseries[i]) {
      point.previous = Number(compareTimeseries[i][metricId]) || 0
    }
    return point
  })

  return (
    <div className="dash-chart panel">
      <div className="panel-header">
        <h2 className="panel-title">{metricLabel(meta, metricId)}</h2>
      </div>
      <div className="panel-body dash-chart-body">
        <ResponsiveContainer width="100%" height={220}>
          <LineChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke="rgba(39,50,68,0.8)" strokeDasharray="3 3" />
            <XAxis
              dataKey="t"
              tickFormatter={shortTick}
              minTickGap={28}
              stroke="#6a7a90"
              tick={{ fill: '#8b9bb0', fontSize: 11 }}
            />
            <YAxis
              stroke="#6a7a90"
              tick={{ fill: '#8b9bb0', fontSize: 11 }}
              tickFormatter={(v) => formatMetricValue(metricId, v)}
              width={64}
            />
            <Tooltip
              contentStyle={{
                background: '#171f2b',
                border: '1px solid #273244',
                borderRadius: 8,
              }}
              labelFormatter={shortTick}
              formatter={(value, name) => [
                formatMetricValue(metricId, value),
                name === 'current' ? 'Current' : 'Compare',
              ]}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="current"
              name="Current"
              stroke={stroke}
              strokeWidth={2}
              dot={false}
            />
            {compareEnabled ? (
              <Line
                type="monotone"
                dataKey="previous"
                name="Compare"
                stroke={COLORS[1]}
                strokeWidth={2}
                dot={false}
                strokeDasharray="4 4"
              />
            ) : null}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
