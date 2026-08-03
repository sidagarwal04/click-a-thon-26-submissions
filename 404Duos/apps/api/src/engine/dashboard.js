import { asFloat, asString, queryMaps, quoteString, quoteTime } from './clickhouse.js'
import { formatRFC3339, parseCHTime, parseFlexibleTime, pctChange, round1 } from './util.js'

const dashboardMetricDefs = {
  revenue: { label: 'Revenue', expr: 'sum(revenue)' },
  requests: { label: 'Requests', expr: 'sum(requests)' },
  impressions: { label: 'Impressions', expr: 'sum(impressions)' },
  clicks: { label: 'Clicks', expr: 'sum(clicks)' },
  fills: { label: 'Fills', expr: 'sum(fills)' },
  fill_rate: { label: 'Fill rate', expr: 'sum(fills) / nullIf(sum(requests), 0)' },
  ctr: { label: 'CTR', expr: 'sum(clicks) / nullIf(sum(impressions), 0)' },
  ecpm: { label: 'eCPM', expr: 'sum(revenue) / nullIf(sum(impressions), 0) * 1000' },
  rpr: { label: 'RPR', expr: 'sum(revenue) / nullIf(sum(requests), 0)' },
}

const dashboardDimensions = [
  { id: 'ad_format', label: 'Ad format' },
  { id: 'region', label: 'Region' },
  { id: 'country', label: 'Country' },
  { id: 'os_version', label: 'OS' },
  { id: 'campaign_type', label: 'Campaign type' },
  { id: 'publisher_tier', label: 'Publisher tier' },
  { id: 'category', label: 'Category' },
  { id: 'vertical', label: 'Vertical' },
]

function dashboardMeta() {
  const metrics = Object.entries(dashboardMetricDefs)
    .map(([id, def]) => ({ id, label: def.label }))
    .sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0))
  const dimensions = dashboardDimensions.map((d) => ({ id: d.id, label: d.label }))
  return { metrics, dimensions }
}

async function queryDataRange(client) {
  const rows = await queryMaps(
    client,
    `
		SELECT
			min(bucket) AS min_bucket,
			max(bucket) AS max_bucket,
			count() AS buckets
		FROM agg_hourly
	`,
  )
  if (rows.length === 0) {
    return { min: null, max: null, buckets: 0 }
  }
  const buckets = Math.trunc(asFloat(rows[0].buckets))
  if (buckets === 0) {
    return { min: null, max: null, buckets: 0 }
  }
  let minB
  let maxB
  try {
    minB = parseCHTime(asString(rows[0].min_bucket))
    maxB = parseCHTime(asString(rows[0].max_bucket))
  } catch {
    return { min: null, max: null, buckets }
  }
  if (minB.getUTCFullYear() < 2000 || maxB.getUTCFullYear() < 2000) {
    return { min: null, max: null, buckets }
  }
  const truncated = new Date(
    Date.UTC(maxB.getUTCFullYear(), maxB.getUTCMonth(), maxB.getUTCDate(), maxB.getUTCHours(), 0, 0, 0),
  )
  const end = new Date(truncated.getTime() + 3600 * 1000 - 1000)
  return {
    min: formatRFC3339(minB),
    max: formatRFC3339(end),
    buckets,
  }
}

export async function getDashboardMeta(client) {
  const out = dashboardMeta()
  try {
    out.dataRange = await queryDataRange(client)
  } catch (err) {
    console.warn('dashboard dataRange:', err.message || err)
    out.dataRange = { min: null, max: null, buckets: 0, error: String(err.message || err) }
  }
  return out
}

export async function queryDashboard(client, body = {}) {
  const { start, end } = resolveDashboardWindow(body.start, body.end)
  let granularity = body.granularity
  if (granularity !== 'day') granularity = 'hour'
  const metrics = normalizeMetrics(body.metrics)
  const dims = normalizeDimensions(body.dimensions)
  let limit = body.limit
  if (!limit || limit <= 0 || limit > 100) limit = 10
  const filters = sanitizeFilters(body.filters)

  const { timeseries: currentTS, totals: currentTotals } = await queryTimeseries(
    client,
    start,
    end,
    granularity,
    metrics,
    filters,
  )

  const tables = {}
  for (const dim of dims) {
    tables[dim] = await queryDimensionTable(client, start, end, dim, metrics, filters, limit, null, null)
  }

  const out = {
    start: formatRFC3339(start),
    end: formatRFC3339(end),
    granularity,
    metrics,
    dimensions: dims,
    filters,
    timeseries: currentTS,
    totals: currentTotals,
    tables,
  }

  if (body.compare?.start && body.compare?.end) {
    const cmp = resolveDashboardWindow(body.compare.start, body.compare.end)
    const { timeseries: compareTS, totals: compareTotals } = await queryTimeseries(
      client,
      cmp.start,
      cmp.end,
      granularity,
      metrics,
      filters,
    )
    out.compareStart = formatRFC3339(cmp.start)
    out.compareEnd = formatRFC3339(cmp.end)
    out.compareTimeseries = compareTS
    out.compareTotals = compareTotals
    out.deltas = computeTotalsDelta(currentTotals, compareTotals)

    for (const dim of dims) {
      tables[dim] = await queryDimensionTable(
        client,
        start,
        end,
        dim,
        metrics,
        filters,
        limit,
        cmp.start,
        cmp.end,
      )
    }
    out.tables = tables
  }

  return out
}

export async function getDashboardFilters(client, query = {}) {
  const dim = query.dimension || ''
  const start = query.start || ''
  const end = query.end || ''
  const filters = query.filters || null
  const values = await queryFilterValues(client, dim, start, end, filters)
  return { dimension: dim, values }
}

async function queryFilterValues(client, dimension, startStr, endStr, filters) {
  let dimOK = false
  for (const d of dashboardDimensions) {
    if (d.id === dimension) {
      dimOK = true
      break
    }
  }
  if (!dimOK) throw new Error('unsupported dimension')
  const { start, end } = resolveDashboardWindow(startStr, endStr)
  const where = [
    `bucket >= ${quoteTime(start)}`,
    `bucket <= ${quoteTime(end)}`,
    `${dimension} != ''`,
  ]
  where.push(...filterPredicates(sanitizeFilters(filters), dimension))
  const q = `
		SELECT DISTINCT toString(${dimension}) AS value
		FROM metric_hourly_snapshot
		WHERE ${where.join(' AND ')}
		ORDER BY value
		LIMIT 200
	`
  const rows = await queryMaps(client, q)
  const out = []
  for (const r of rows) {
    const v = asString(r.value)
    if (v) out.push(v)
  }
  return out
}

function resolveDashboardWindow(startStr, endStr) {
  if (!startStr || !endStr) {
    throw new Error('start and end are required')
  }
  const start = parseFlexibleTime(startStr)
  let end = parseFlexibleTime(endStr)
  if (!String(endStr).includes('T') && !String(endStr).includes(' ')) {
    end = new Date(end.getTime() + 24 * 3600 * 1000 - 1000)
  }
  return { start, end }
}

function normalizeMetrics(inMetrics) {
  if (!inMetrics || inMetrics.length === 0) {
    return ['revenue', 'requests', 'fill_rate', 'ecpm']
  }
  const out = []
  const seen = new Set()
  for (let m of inMetrics) {
    m = String(m || '').trim()
    if (!dashboardMetricDefs[m] || seen.has(m)) continue
    seen.add(m)
    out.push(m)
  }
  if (out.length === 0) return ['revenue', 'requests']
  return out
}

function normalizeDimensions(inDims) {
  const allowed = new Set(dashboardDimensions.map((d) => d.id))
  if (!inDims || inDims.length === 0) {
    return ['ad_format', 'country', 'os_version', 'campaign_type', 'publisher_tier']
  }
  const out = []
  const seen = new Set()
  for (let d of inDims) {
    d = String(d || '').trim()
    if (!allowed.has(d) || seen.has(d)) continue
    seen.add(d)
    out.push(d)
  }
  return out
}

function sanitizeFilters(inFilters) {
  if (!inFilters || typeof inFilters !== 'object') return {}
  const allowed = new Set(dashboardDimensions.map((d) => d.id))
  const out = {}
  for (const [k, vals] of Object.entries(inFilters)) {
    if (!allowed.has(k) || !Array.isArray(vals) || vals.length === 0) continue
    const clean = []
    const seen = new Set()
    for (let v of vals) {
      v = String(v || '').trim()
      if (!v || seen.has(v)) continue
      seen.add(v)
      clean.push(v)
    }
    if (clean.length > 0) out[k] = clean
  }
  return out
}

function filterPredicates(filters, excludeDim) {
  const preds = []
  for (const [dim, vals] of Object.entries(filters || {})) {
    if (dim === excludeDim || !vals?.length) continue
    const quoted = vals.map((v) => quoteString(v))
    preds.push(`${dim} IN (${quoted.join(',')})`)
  }
  return preds
}

function metricAlias(metric) {
  return `m_${metric}`
}

function metricSelectSQL(metrics) {
  return metrics
    .map((m) => {
      const def = dashboardMetricDefs[m]
      return `${def.expr} AS ${metricAlias(m)}`
    })
    .join(',\n\t\t\t')
}

function metricOrderExpr(metric) {
  const def = dashboardMetricDefs[metric]
  if (!def) return metricAlias(metric)
  return def.expr
}

function readMetric(row, metric) {
  const alias = metricAlias(metric)
  if (row[alias] != null) return asFloat(row[alias])
  return asFloat(row[metric])
}

async function queryTimeseries(client, start, end, granularity, metrics, filters) {
  let bucketExpr = 'toStartOfHour(bucket)'
  if (granularity === 'day') bucketExpr = 'toStartOfDay(bucket)'
  const where = [`bucket >= ${quoteTime(start)}`, `bucket <= ${quoteTime(end)}`]
  where.push(...filterPredicates(filters, ''))

  const q = `
		SELECT
			toString(${bucketExpr}) AS t,
			${metricSelectSQL(metrics)}
		FROM metric_hourly_snapshot
		WHERE ${where.join(' AND ')}
		GROUP BY t
		ORDER BY t
	`
  const rows = await queryMaps(client, q)

  const totalsQ = `
		SELECT ${metricSelectSQL(metrics)}
		FROM metric_hourly_snapshot
		WHERE ${where.join(' AND ')}
	`
  const totalRows = await queryMaps(client, totalsQ)
  const totals = {}
  if (totalRows.length > 0) {
    for (const m of metrics) {
      totals[m] = readMetric(totalRows[0], m)
    }
  }

  const timeseries = rows.map((r) => {
    const point = { t: asString(r.t) }
    for (const m of metrics) {
      point[m] = readMetric(r, m)
    }
    return point
  })
  return { timeseries, totals }
}

async function queryDimensionTable(
  client,
  start,
  end,
  dimension,
  metrics,
  filters,
  limit,
  compareStart,
  compareEnd,
) {
  const where = [
    `bucket >= ${quoteTime(start)}`,
    `bucket <= ${quoteTime(end)}`,
    `${dimension} != ''`,
  ]
  where.push(...filterPredicates(filters, dimension))

  const primaryMetric = metrics[0]
  const q = `
		SELECT
			toString(${dimension}) AS dim_value,
			${metricSelectSQL(metrics)}
		FROM metric_hourly_snapshot
		WHERE ${where.join(' AND ')}
		GROUP BY dim_value
		ORDER BY ${metricOrderExpr(primaryMetric)} DESC
		LIMIT ${limit}
	`
  const rows = await queryMaps(client, q)

  let compareMap = null
  if (compareStart && compareEnd) {
    const cWhere = [
      `bucket >= ${quoteTime(compareStart)}`,
      `bucket <= ${quoteTime(compareEnd)}`,
      `${dimension} != ''`,
    ]
    cWhere.push(...filterPredicates(filters, dimension))
    const cq = `
			SELECT
				toString(${dimension}) AS dim_value,
				${metricSelectSQL(metrics)}
			FROM metric_hourly_snapshot
			WHERE ${cWhere.join(' AND ')}
			GROUP BY dim_value
		`
    const cRows = await queryMaps(client, cq)
    compareMap = {}
    for (const r of cRows) {
      const vals = {}
      for (const m of metrics) vals[m] = readMetric(r, m)
      compareMap[asString(r.dim_value)] = vals
    }
  }

  return rows.map((r) => {
    const value = asString(r.dim_value)
    const row = { value }
    for (const m of metrics) {
      const cur = readMetric(r, m)
      row[m] = cur
      if (compareMap) {
        const prev = compareMap[value]?.[m] ?? 0
        row[`${m}_prev`] = prev
        row[`${m}_delta`] = cur - prev
        row[`${m}_delta_pct`] = round1(pctChange(cur, prev))
      }
    }
    return row
  })
}

function computeTotalsDelta(current, compare) {
  const out = {}
  for (const [k, cur] of Object.entries(current)) {
    const prev = compare[k] ?? 0
    out[k] = {
      current: cur,
      previous: prev,
      delta: cur - prev,
      deltaPct: round1(pctChange(cur, prev)),
    }
  }
  return out
}
