import {
  ResponsiveContainer,
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts'

const MAX_POINTS = 60
const CHART_TYPES = new Set(['bar', 'line', 'pie', 'horizontal_bar'])

const PIE_COLORS = [
  '#4f46e5',
  '#0891b2',
  '#059669',
  '#d97706',
  '#dc2626',
  '#7c3aed',
  '#0ea5e9',
  '#65a30d',
]

function fmtNum(n) {
  if (n == null || Number.isNaN(Number(n))) return String(n ?? '')
  return Number(n).toLocaleString()
}

function isNumericValue(v) {
  if (typeof v === 'number') return Number.isFinite(v)
  if (typeof v === 'string' && v.trim() !== '') return Number.isFinite(Number(v))
  return false
}

function columnLooksNumeric(data, key) {
  let seen = 0
  for (const row of data) {
    if (!row || row[key] == null || row[key] === '') continue
    seen += 1
    if (!isNumericValue(row[key])) return false
    if (seen >= 8) break
  }
  return seen > 0
}

function toNumber(v) {
  if (typeof v === 'number') return v
  if (typeof v === 'string' && v.trim() !== '') {
    const n = Number(v)
    return Number.isFinite(n) ? n : v
  }
  return v
}

/**
 * Agents sometimes swap x/y (esp. horizontal_bar, thinking in Cartesian axes).
 * Convention: x/label = category, y/value = numeric measure.
 */
function normalizeAxisKeys(type, data, x, y, label, value) {
  if (type === 'pie') {
    const labelNum = columnLooksNumeric(data, label)
    const valueNum = columnLooksNumeric(data, value)
    if (labelNum && !valueNum) return { x, y, label: value, value: label }
    return { x, y, label, value }
  }

  const xNum = columnLooksNumeric(data, x)
  const yNum = columnLooksNumeric(data, y)
  if (xNum && !yNum) return { x: y, y: x, label, value }
  return { x, y, label, value }
}

/**
 * Parse + validate an atlyschart fence body.
 * Returns { ok: true, spec } or { ok: false, error }.
 */
export function parseAtlysChart(raw) {
  let parsed
  try {
    parsed = JSON.parse(String(raw || '').trim())
  } catch {
    return { ok: false, error: 'Invalid chart JSON' }
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return { ok: false, error: 'Chart spec must be a JSON object' }
  }
  const type = String(parsed.type || '').toLowerCase()
  if (!CHART_TYPES.has(type)) {
    return { ok: false, error: `Unsupported chart type: ${parsed.type ?? '(missing)'}` }
  }
  if (!Array.isArray(parsed.data) || parsed.data.length === 0) {
    return { ok: false, error: 'Chart data must be a non-empty array' }
  }

  let x = parsed.x ? String(parsed.x) : 'x'
  let y = parsed.y ? String(parsed.y) : 'y'
  let label = parsed.label ? String(parsed.label) : (parsed.x ? String(parsed.x) : 'label')
  let value = parsed.value ? String(parsed.value) : (parsed.y ? String(parsed.y) : 'value')

  const rawData = parsed.data.slice(0, MAX_POINTS).map((row) => {
    if (!row || typeof row !== 'object') return {}
    return { ...row }
  })

  ;({ x, y, label, value } = normalizeAxisKeys(type, rawData, x, y, label, value))

  const measureKey = type === 'pie' ? value : y
  const data = rawData.map((row) => {
    if (!Object.prototype.hasOwnProperty.call(row, measureKey)) return row
    return { ...row, [measureKey]: toNumber(row[measureKey]) }
  })

  const clamped = parsed.data.length > MAX_POINTS
  return {
    ok: true,
    spec: {
      type,
      title: parsed.title ? String(parsed.title) : '',
      x,
      y,
      label,
      value,
      note: parsed.note ? String(parsed.note) : (clamped ? `Showing first ${MAX_POINTS} points` : ''),
      data,
      clamped,
    },
  }
}

function DataDisclosure({ spec }) {
  const keys = (() => {
    if (spec.type === 'pie') return [spec.label, spec.value]
    return [spec.x, spec.y]
  })()
  return (
    <details className="chat-chart-data">
      <summary>View data</summary>
      <div className="chat-chart-data-scroll">
        <table>
          <thead>
            <tr>
              {keys.map((k) => (
                <th key={k}>{k}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {spec.data.map((row, i) => (
              <tr key={i}>
                {keys.map((k) => (
                  <td key={k} className={k === spec.y || k === spec.value ? 'num' : undefined}>
                    {typeof row[k] === 'number' ? fmtNum(row[k]) : String(row[k] ?? '')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  )
}

function ChartBody({ spec }) {
  const tooltipStyle = {
    background: '#ffffff',
    border: '1px solid #e2e8f0',
    borderRadius: 8,
    fontSize: 12,
    color: '#0f172a',
  }
  const axisStroke = '#94a3b8'
  const gridStroke = '#e2e8f0'
  const barFill = '#4f46e5'
  const lineStroke = '#4f46e5'

  if (spec.type === 'pie') {
    return (
      <ResponsiveContainer width="100%" height={240}>
        <PieChart>
          <Pie
            data={spec.data}
            dataKey={spec.value}
            nameKey={spec.label}
            cx="50%"
            cy="50%"
            outerRadius={88}
            innerRadius={36}
            paddingAngle={2}
          >
            {spec.data.map((_, i) => (
              <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => fmtNum(v)} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
        </PieChart>
      </ResponsiveContainer>
    )
  }

  if (spec.type === 'line') {
    return (
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={spec.data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
          <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
          <XAxis dataKey={spec.x} tick={{ fill: axisStroke, fontSize: 11 }} stroke={axisStroke} />
          <YAxis tick={{ fill: axisStroke, fontSize: 11 }} stroke={axisStroke} />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => fmtNum(v)} />
          <Line
            type="monotone"
            dataKey={spec.y}
            stroke={lineStroke}
            strokeWidth={2}
            dot={{ r: 4, fill: lineStroke, stroke: '#ffffff', strokeWidth: 1.5 }}
            activeDot={{ r: 6 }}
          />
        </LineChart>
      </ResponsiveContainer>
    )
  }

  if (spec.type === 'horizontal_bar') {
    return (
      <ResponsiveContainer width="100%" height={Math.min(280, 48 + spec.data.length * 28)}>
        <BarChart
          data={spec.data}
          layout="vertical"
          margin={{ top: 8, right: 12, left: 8, bottom: 4 }}
        >
          <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
          <XAxis type="number" tick={{ fill: axisStroke, fontSize: 11 }} stroke={axisStroke} />
          <YAxis
            type="category"
            dataKey={spec.x}
            width={88}
            tick={{ fill: axisStroke, fontSize: 11 }}
            stroke={axisStroke}
          />
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => fmtNum(v)} />
          <Bar dataKey={spec.y} fill={barFill} radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
    )
  }

  // bar (default)
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={spec.data} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
        <CartesianGrid stroke={gridStroke} strokeDasharray="3 3" />
        <XAxis dataKey={spec.x} tick={{ fill: axisStroke, fontSize: 11 }} stroke={axisStroke} />
        <YAxis tick={{ fill: axisStroke, fontSize: 11 }} stroke={axisStroke} />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => fmtNum(v)} />
        <Bar dataKey={spec.y} fill={barFill} radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}

/**
 * Renders a validated atlyschart spec, or a graceful fallback.
 * @param {{ raw?: string, spec?: object }} props
 */
export default function ChatChart({ raw, spec: preparsed }) {
  const parsed = preparsed
    ? { ok: true, spec: preparsed }
    : parseAtlysChart(raw)

  if (!parsed.ok) {
    return (
      <div className="chat-chart chat-chart--error" role="note">
        Couldn’t render chart — {parsed.error}
      </div>
    )
  }

  const { spec } = parsed
  return (
    <figure className="chat-chart">
      {spec.title && <figcaption className="chat-chart-title">{spec.title}</figcaption>}
      <div className="chat-chart-canvas" aria-label={spec.title || 'Chart'}>
        <ChartBody spec={spec} />
      </div>
      {spec.note && <div className="chat-chart-note">{spec.note}</div>}
      <DataDisclosure spec={spec} />
    </figure>
  )
}
