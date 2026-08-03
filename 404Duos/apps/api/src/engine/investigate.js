import { asFloat, asString, queryMaps, quoteString, quoteTime } from './clickhouse.js'
import {
  appendCounterfactualCitation,
  buildCounterfactual,
  buildEvidenceLock,
  buildHypotheses,
  buildWaterfall,
  ctr,
  ecpm,
  enrichRuledOutWithSeasonality,
  evaluateSeasonality,
  fillRate,
  metricValue,
  renderRate,
} from './rca.js'
import {
  addUTCDays,
  formatFactorValue,
  formatNumber,
  formatPct,
  formatRFC3339,
  formatSignedPct,
  humanDimension,
  humanMetric,
  parseCHTime,
  parseFlexibleTime,
  pctChange,
  round1,
  truncateUTCHour,
} from './util.js'

// ── Investigation cache ──────────────────────────────────────────────

const investigationCache = new Map()

export function cacheGet(id) {
  return investigationCache.get(id) ?? null
}

export function cachePut(inv) {
  if (inv?.id) investigationCache.set(inv.id, inv)
  return inv
}

export function createInvestigationCache() {
  const byID = new Map()
  return {
    get(id) {
      return byID.get(id) ?? null
    },
    put(inv) {
      if (inv?.id) byID.set(inv.id, inv)
      return inv
    },
    clear() {
      byID.clear()
    },
  }
}

// ── metricBag helpers ────────────────────────────────────────────────

function emptyBag() {
  return { requests: 0, fills: 0, impressions: 0, clicks: 0, revenue: 0 }
}

function scaleBag(m, scale) {
  return {
    requests: m.requests * scale,
    fills: m.fills * scale,
    impressions: m.impressions * scale,
    clicks: m.clicks * scale,
    revenue: m.revenue * scale,
  }
}

// ── Core investigation ───────────────────────────────────────────────

export async function runInvestigation(client, req) {
  const trace = []
  const mark = (step, detail, started) => {
    trace.push({
      step,
      detail,
      durationMs: Date.now() - started,
    })
  }

  const t0 = Date.now()
  let alertID = normalizeAlertID(req.alertId || '')
  let live = null

  if (alertID && looksLikeUUID(alertID)) {
    live = await fetchAlertLive(client, alertID)
  }

  let windowStart
  let windowEnd
  let metric = req.metric || ''
  let advertiserID = req.advertiserId || ''
  let baselineKind = req.baselineKind || ''
  if (!baselineKind) baselineKind = 'same_hour_4w_seasonality'

  if (live) {
    windowStart = live.bucket
    windowEnd = new Date(live.bucket.getTime() + 3600 * 1000 - 1000)
    if (!metric) metric = live.metric
    if (!advertiserID) advertiserID = live.advertiserId
    alertID = live.alertId
    mark(
      'alerts_live',
      `Loaded alert ${alertID} advertiser=${advertiserID} metric=${metric} z=${live.zscore.toFixed(2)}`,
      t0,
    )
  } else {
    ;({ start: windowStart, end: windowEnd } = resolveWindow(req.windowStart, req.windowEnd))
    if (!metric) metric = 'revenue'
    mark(
      'window',
      `No alert id; using window ${formatRFC3339(windowStart)}..${formatRFC3339(windowEnd)}`,
      t0,
    )
  }

  const t1 = Date.now()
  const observed = await querySnapshotMetrics(client, advertiserID, windowStart, windowEnd)
  let baseline = await querySeasonalBaseline(client, advertiserID, windowStart, windowEnd, 4)
  if (live && metric === 'revenue' && live.expected > 0 && baseline.revenue === 0) {
    baseline = { ...baseline, revenue: live.expected }
  }
  // Naive trap baseline: mean of the prior 7 consecutive days (same clock window).
  // Mixes weekdays so normal weekend softness looks like a drop vs a flat average.
  let flat
  try {
    flat = await queryNaiveTrailingBaseline(client, advertiserID, windowStart, windowEnd, 7)
    if (flat.requests === 0 && flat.revenue === 0) {
      const flatStart = new Date(windowStart.getTime() - 24 * 3600 * 1000)
      const flatEnd = new Date(windowEnd.getTime() - 24 * 3600 * 1000)
      flat = await querySnapshotMetrics(client, advertiserID, flatStart, flatEnd)
    }
  } catch {
    flat = emptyBag()
  }
  mark(
    'baseline',
    `metric_hourly_snapshot vs ${baselineKind} (+ naive trailing-7d seasonality check)`,
    t1,
  )

  const t2 = Date.now()
  const decomp = decompose(baseline, observed)
  const culprit = pickCulprit(decomp, metric)
  mark('decompose', `Revenue identity walk; culprit=${culprit}`, t2)

  const t3 = Date.now()
  let segments = await fetchContributors(client, alertID, metric)
  if (segments.length === 0) {
    segments = await rankSegmentsFromSnapshot(client, advertiserID, windowStart, windowEnd, culprit)
    mark('slice', `Ranked dimensions from metric_hourly_snapshot (${segments.length})`, t3)
  } else {
    try {
      const extra = await rankSegmentsFromSnapshot(client, advertiserID, windowStart, windowEnd, culprit)
      segments = mergeSegments(segments, extra, 8)
    } catch {
      /* keep contributors-only */
    }
    mark('slice', `Loaded contributors + snapshot dims (${segments.length})`, t3)
  }

  const t4 = Date.now()
  // Like-for-like residual — never use alerts_live expected here (may be flat / non-DOW).
  const pct = pctChange(metricValue(observed, metric), metricValue(baseline, metric))
  let direction = 'down'
  if (pct > 0) direction = 'up'
  if (!alertID) {
    alertID = `alert-${metric}-${windowStart.toISOString().slice(0, 10)}`
  }
  const invID = `inv-${alertID}`
  const alert = {
    id: alertID,
    metric,
    direction,
    pctChange: round1(pct),
    windowStart: formatRFC3339(windowStart),
    windowEnd: formatRFC3339(windowEnd),
    baselineKind,
    severity: severityFrom(Math.abs(pct)),
    ...(advertiserID ? { advertiserId: advertiserID } : {}),
  }

  const observations = await fetchObservations(client, alertID)

  const tSeas = Date.now()
  const seasonality = evaluateSeasonality(metric, observed, baseline, flat, pct)
  mark('seasonality', seasonality.detail, tSeas)

  let ruledOut = buildRuledOut(culprit, baseline, observed, pct)
  ruledOut = enrichRuledOutWithSeasonality(ruledOut, seasonality)
  const waterfall = buildWaterfall(baseline, observed, decomp)
  const counterfactual = buildCounterfactual(culprit, baseline, observed)
  const hypotheses = buildHypotheses(decomp, culprit, segments)
  let diagnosis = buildDiagnosisFromInsightIQ(alert, decomp, culprit, segments, ruledOut, observations, live)
  diagnosis = appendCounterfactualCitation(diagnosis, counterfactual)
  mark('evidence', 'Packaged evidence + waterfall + counterfactual + hypotheses', t4)
  trace.push({
    step: 'narrate',
    detail: 'Narration deferred to Node/Gemini from evidence only',
    durationMs: 0,
  })

  let uiSegments = segments
  if (uiSegments.length > 6) uiSegments = uiSegments.slice(0, 6)

  const inv = {
    id: invID,
    status: 'complete',
    alert,
    decomposition: decomp,
    segments: uiSegments,
    ruledOut,
    diagnosis,
    trace,
    seasonality,
    waterfall,
    counterfactual,
    hypotheses,
  }
  if (seasonality.status === 'ruled_out_as_seasonality') {
    // Pure seasonality plant: clear as not-an-incident, do not alarm.
    inv.alert.severity = 'info'
    inv.alert.pctChange = round1(seasonality.seasonalDeltaPct)
    inv.alert.direction = seasonality.seasonalDeltaPct >= 0 ? 'up' : 'down'
    inv.diagnosis = {
      ...inv.diagnosis,
      text: `Not an incident — ruled out as seasonality. ${seasonality.detail}`,
    }
  } else if (seasonality.status === 'residual_remains' && live) {
    // Real residual: allow live z-score to inform severity banding.
    inv.alert.severity = severityFromZOrPct(live, Math.abs(pct))
  }
  inv.evidence = buildEvidenceLock(inv)
  return inv
}

export function normalizeAlertID(id) {
  id = String(id || '').trim()
  if (id.startsWith('inv-')) id = id.slice(4)
  return id
}

export function looksLikeUUID(s) {
  if (s.length !== 36) return false
  for (let i = 0; i < s.length; i++) {
    const c = s[i]
    if (i === 8 || i === 13 || i === 18 || i === 23) {
      if (c !== '-') return false
    } else if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') || (c >= 'A' && c <= 'F'))) {
      return false
    }
  }
  return true
}

async function fetchAlertLive(client, alertID) {
  const q = `
		SELECT
			toString(alert_id) AS id,
			advertiser_id,
			metric,
			toString(bucket) AS bucket,
			actual,
			expected,
			zscore
		FROM alerts_live
		WHERE alert_id = toUUID(${quoteString(alertID)})
		LIMIT 1
	`
  const rows = await queryMaps(client, q)
  if (rows.length === 0) throw new Error(`alert not found: ${alertID}`)
  const r = rows[0]
  return {
    alertId: asString(r.id),
    advertiserId: asString(r.advertiser_id),
    metric: asString(r.metric),
    bucket: parseCHTime(asString(r.bucket)),
    actual: asFloat(r.actual),
    expected: asFloat(r.expected),
    zscore: asFloat(r.zscore),
  }
}

async function fetchContributors(client, alertID, metric) {
  if (!alertID || !looksLikeUUID(alertID)) return []
  const q = `
		SELECT
			dimension,
			dimension_value,
			current_value,
			baseline_value,
			delta,
			contribution
		FROM alert_dimension_contributors
		WHERE alert_id = toUUID(${quoteString(alertID)})
		ORDER BY abs(delta) DESC
		LIMIT 8
	`
  const rows = await queryMaps(client, q)
  return rows.map((r) => {
    const base = asFloat(r.baseline_value)
    const cur = asFloat(r.current_value)
    let contrib = asFloat(r.contribution)
    if (Math.abs(contrib) <= 1.5) contrib *= 100
    return {
      dimension: asString(r.dimension),
      value: asString(r.dimension_value),
      metric,
      deltaPct: round1(pctChange(cur, base)),
      contributionPct: round1(contrib),
    }
  })
}

async function fetchObservations(client, alertID) {
  if (!alertID || !looksLikeUUID(alertID)) return []
  const q = `
		SELECT observation_order, observation_type, title, detail, impact
		FROM alert_observations
		WHERE alert_id = toUUID(${quoteString(alertID)})
		ORDER BY observation_order
		LIMIT 8
	`
  const rows = await queryMaps(client, q)
  return rows.map((r) => ({
    order: Math.trunc(asFloat(r.observation_order)),
    type: asString(r.observation_type),
    title: asString(r.title),
    detail: asString(r.detail),
    impact: asFloat(r.impact),
  }))
}

async function querySnapshotMetrics(client, advertiserID, start, end) {
  let where = `bucket >= ${quoteTime(start)} AND bucket <= ${quoteTime(end)}`
  if (advertiserID) {
    where += ` AND advertiser_id = ${quoteString(advertiserID)}`
  }
  const q = `
		SELECT
			sum(requests) AS requests,
			sum(fills) AS fills,
			sum(impressions) AS impressions,
			sum(clicks) AS clicks,
			sum(revenue) AS revenue
		FROM metric_hourly_snapshot
		WHERE ${where}
	`
  return scanMetricBag(client, q)
}

async function querySeasonalBaseline(client, advertiserID, windowStart, windowEnd, weeks) {
  const day = truncateUTCHour(windowStart)
  const dur = windowEnd.getTime() - windowStart.getTime()
  const sum = emptyBag()
  let n = 0
  // Same clock window on the same weekday: -7, -14, -21, -28 days.
  for (let i = 1; i <= weeks; i++) {
    const ws = addUTCDays(day, -7 * i)
    const we = new Date(ws.getTime() + dur)
    const m = await querySnapshotMetrics(client, advertiserID, ws, we)
    if (m.requests === 0 && m.revenue === 0) continue
    sum.requests += m.requests
    sum.fills += m.fills
    sum.impressions += m.impressions
    sum.clicks += m.clicks
    sum.revenue += m.revenue
    n++
  }
  if (n === 0) {
    if (advertiserID) {
      const q = `
				SELECT expected
				FROM baseline_hourly
				WHERE advertiser_id = ${quoteString(advertiserID)} AND metric = 'revenue' AND bucket = ${quoteTime(day)}
				LIMIT 1
			`
      try {
        const rows = await queryMaps(client, q)
        if (rows.length > 0) {
          return { ...emptyBag(), revenue: asFloat(rows[0].expected) }
        }
      } catch {
        /* fall through */
      }
    }
    throw new Error('no seasonal baseline rows in metric_hourly_snapshot')
  }
  return scaleBag(sum, 1 / n)
}

/** Mean of the prior N consecutive days (same clock window) — mixes DOW on purpose. */
async function queryNaiveTrailingBaseline(client, advertiserID, windowStart, windowEnd, days) {
  const day = truncateUTCHour(windowStart)
  const dur = windowEnd.getTime() - windowStart.getTime()
  const sum = emptyBag()
  let n = 0
  for (let i = 1; i <= days; i++) {
    const ws = addUTCDays(day, -i)
    const we = new Date(ws.getTime() + dur)
    const m = await querySnapshotMetrics(client, advertiserID, ws, we)
    if (m.requests === 0 && m.revenue === 0) continue
    sum.requests += m.requests
    sum.fills += m.fills
    sum.impressions += m.impressions
    sum.clicks += m.clicks
    sum.revenue += m.revenue
    n++
  }
  if (n === 0) return emptyBag()
  return scaleBag(sum, 1 / n)
}

async function rankSegmentsFromSnapshot(client, advertiserID, obsStart, obsEnd, culprit) {
  const dims = [
    'ad_format',
    'country',
    'os_version',
    'category',
    'vertical',
    'region',
    'campaign_type',
    'publisher_tier',
  ]
  const [metricExpr, weightExpr] = snapshotMetricSQL(culprit)
  let advFilter = ''
  if (advertiserID) {
    advFilter = ` AND advertiser_id = ${quoteString(advertiserID)}`
  }
  const day = truncateUTCHour(obsStart)
  const dur = obsEnd.getTime() - obsStart.getTime()
  const parts = []
  for (let i = 1; i <= 4; i++) {
    const ws = addUTCDays(day, -7 * i)
    const we = new Date(ws.getTime() + dur)
    parts.push(`(bucket >= ${quoteTime(ws)} AND bucket <= ${quoteTime(we)})`)
  }
  const basePred = parts.join(' OR ')

  const all = []
  for (const dim of dims) {
    const q = `
			WITH
			obs AS (
				SELECT ${dim} AS dim, ${metricExpr} AS metric, ${weightExpr} AS weight
				FROM metric_hourly_snapshot
				WHERE bucket >= ${quoteTime(obsStart)} AND bucket <= ${quoteTime(obsEnd)}${advFilter}
				GROUP BY dim
			),
			base AS (
				SELECT dim, avg(metric) AS metric, avg(weight) AS weight
				FROM (
					SELECT ${dim} AS dim, ${metricExpr} AS metric, ${weightExpr} AS weight, toDate(bucket) AS d
					FROM metric_hourly_snapshot
					WHERE (${basePred})${advFilter}
					GROUP BY dim, d
				)
				GROUP BY dim
			)
			SELECT
				toString(obs.dim) AS dim,
				obs.metric AS obs_metric,
				base.metric AS base_metric,
				obs.weight AS obs_weight
			FROM obs
			INNER JOIN base ON obs.dim = base.dim
			WHERE obs.dim IS NOT NULL AND toString(obs.dim) != ''
			ORDER BY abs(obs.metric - base.metric) * abs(obs.weight) DESC
			LIMIT 3
		`
    const rows = await queryMaps(client, q)
    let totalAbs = 0
    const raws = []
    for (const row of rows) {
      const r = {
        value: asString(row.dim),
        obsM: asFloat(row.obs_metric),
        baseM: asFloat(row.base_metric),
        wgt: asFloat(row.obs_weight),
      }
      totalAbs += Math.abs(r.obsM - r.baseM) * Math.max(Math.abs(r.wgt), 1)
      raws.push(r)
    }
    for (const r of raws) {
      let contrib = 0
      if (totalAbs > 0) {
        contrib = (Math.abs(r.obsM - r.baseM) * Math.max(Math.abs(r.wgt), 1) / totalAbs) * 100
      }
      all.push({
        dimension: dim,
        value: r.value,
        metric: culprit,
        deltaPct: round1(pctChange(r.obsM, r.baseM)),
        contributionPct: round1(contrib),
      })
    }
  }
  if (all.length > 8) {
    all.sort((a, b) => Math.abs(b.contributionPct) - Math.abs(a.contributionPct))
    return all.slice(0, 8)
  }
  return all
}

function snapshotMetricSQL(culprit) {
  switch (culprit) {
    case 'requests':
      return ['sum(requests)', 'sum(requests)']
    case 'fill_rate':
      return ['sum(fills) / nullIf(sum(requests),0)', 'sum(fills)']
    case 'render_rate':
      return ['sum(impressions) / nullIf(sum(fills),0)', 'sum(impressions)']
    case 'ecpm':
      return ['sum(revenue) / nullIf(sum(impressions),0) * 1000', 'sum(revenue)']
    case 'ctr':
      return ['sum(clicks) / nullIf(sum(impressions),0)', 'sum(clicks)']
    default:
      return ['sum(revenue)', 'sum(revenue)']
  }
}

async function scanMetricBag(client, q) {
  const rows = await queryMaps(client, q)
  if (rows.length === 0) return emptyBag()
  const r = rows[0]
  return {
    requests: asFloat(r.requests),
    fills: asFloat(r.fills),
    impressions: asFloat(r.impressions),
    clicks: asFloat(r.clicks),
    revenue: asFloat(r.revenue),
  }
}

function resolveWindow(startStr, endStr) {
  if (!startStr || !endStr) {
    const start = new Date('2026-06-21T16:00:00Z')
    const end = new Date(start.getTime() + 3600 * 1000 - 1000)
    return { start, end }
  }
  const start = parseFlexibleTime(startStr)
  const end = parseFlexibleTime(endStr)
  return { start, end }
}

function decompose(base, obs) {
  const mk = (factor, label, b, o) => ({
    factor,
    label,
    baseline: b,
    observed: o,
    deltaPct: round1(pctChange(o, b)),
    status: 'neutral',
  })
  return [
    mk('requests', 'Requests', base.requests, obs.requests),
    mk('fill_rate', 'Fill rate', fillRate(base), fillRate(obs)),
    mk('render_rate', 'Render rate', renderRate(base), renderRate(obs)),
    mk('ecpm', 'eCPM', ecpm(base), ecpm(obs)),
    mk('ctr', 'CTR', ctr(base), ctr(obs)),
  ]
}

function pickCulprit(factors, alertMetric) {
  if (
    alertMetric === 'ctr' ||
    alertMetric === 'fill_rate' ||
    alertMetric === 'ecpm' ||
    alertMetric === 'requests'
  ) {
    for (const f of factors) {
      if (f.factor === alertMetric) f.status = 'culprit'
      else if (Math.abs(f.deltaPct) < 3) f.status = 'ruled_out'
    }
    return alertMetric
  }
  let best = 'fill_rate'
  let bestAbs = -1
  for (const f of factors) {
    if (f.factor === 'ctr') continue
    if (Math.abs(f.deltaPct) > bestAbs) {
      bestAbs = Math.abs(f.deltaPct)
      best = f.factor
    }
  }
  for (const f of factors) {
    if (f.factor === best) f.status = 'culprit'
    else if (Math.abs(f.deltaPct) < 3) f.status = 'ruled_out'
    else f.status = 'neutral'
  }
  return best
}

function buildRuledOut(culprit, base, obs) {
  const out = []
  if (Math.abs(pctChange(obs.requests, base.requests)) < 3) {
    out.push({
      reason: 'Request volume',
      detail: `Requests changed only ${pctChange(obs.requests, base.requests).toFixed(1)}% vs baseline.`,
    })
  }
  if (Math.abs(pctChange(ecpm(obs), ecpm(base))) < 3 && culprit !== 'ecpm') {
    out.push({
      reason: 'eCPM / price',
      detail: `eCPM moved ${pctChange(ecpm(obs), ecpm(base)).toFixed(1)}%, too small to explain the move.`,
    })
  }
  if (culprit !== 'ctr') {
    out.push({
      reason: 'CTR',
      detail: `CTR ${pctChange(ctr(obs), ctr(base)).toFixed(1)}%; not a direct revenue factor in the CPM identity.`,
    })
  }
  return out
}

function buildDiagnosisFromInsightIQ(alert, decomp, culprit, segments, ruled, observations, live) {
  const citations = [
    { label: `${humanMetric(alert.metric)} change`, value: formatSignedPct(alert.pctChange) },
  ]
  if (live) {
    citations.push(
      { label: 'Actual', value: formatNumber(live.actual) },
      { label: 'Expected', value: formatNumber(live.expected) },
      { label: 'Z-score', value: live.zscore.toFixed(2) },
    )
  }

  let culpritFactor = null
  for (const f of decomp) {
    if (f.factor === culprit) {
      culpritFactor = f
      break
    }
  }

  let text = `${humanMetric(alert.metric)} ${alert.direction} ${formatPct(Math.abs(alert.pctChange))}`
  if (alert.advertiserId) {
    text = `${humanMetric(alert.metric)} for ${alert.advertiserId} ${alert.direction} ${formatPct(Math.abs(alert.pctChange))}`
  }
  if (culprit) {
    text += `, primarily driven by ${humanMetric(culprit)}`
    if (culpritFactor) {
      text += ` (${formatFactorValue(culprit, culpritFactor.baseline)} → ${formatFactorValue(culprit, culpritFactor.observed)}, ${formatSignedPct(culpritFactor.deltaPct)})`
      citations.push({
        label: `${culpritFactor.label} change`,
        value: formatSignedPct(culpritFactor.deltaPct),
      })
    }
  }

  let topSegs = segments
  if (topSegs.length > 3) topSegs = topSegs.slice(0, 3)
  if (topSegs.length > 0) {
    const parts = []
    for (const s of topSegs) {
      parts.push(
        `${humanDimension(s.dimension)}=${s.value} (${formatSignedPct(s.deltaPct)}, contrib ${formatPct(s.contributionPct)})`,
      )
      citations.push({
        label: `${humanDimension(s.dimension)}: ${s.value}`,
        value: `${formatSignedPct(s.deltaPct)} · contrib ${formatPct(s.contributionPct)}`,
      })
    }
    text += `. Top segments: ${parts.join('; ')}.`
  } else if (observations.length > 0) {
    const limit = Math.min(3, observations.length)
    const parts = []
    for (let i = 0; i < limit; i++) {
      const o = observations[i]
      parts.push(shortenObservationDetail(o.detail))
      citations.push({
        label: `${o.title} (${i + 1})`,
        value: shortenObservationDetail(o.detail),
      })
    }
    text += `. ${parts.join(' ')}`
  }

  if (ruled.length > 0) {
    text += ` Ruled out: ${ruled[0].reason}.`
  }
  return { text, citations }
}

function shortenObservationDetail(detail) {
  let d = String(detail || '').trim()
  if (d.includes('Dimension value "')) {
    d = d
      .replace(/Dimension value "/g, '')
      .replace(/" went from/g, ':')
      .replace(/ \(delta:/g, ' Δ')
      .replace(/, contribution:/g, ' ·')
  }
  if (d.length > 140) return `${d.slice(0, 137)}…`
  return d
}

function severityFromZOrPct(live, absPct) {
  if (live) {
    const z = Math.abs(live.zscore)
    if (z >= 10) return 'critical'
    if (z >= 5) return 'high'
    if (z >= 3) return 'medium'
    return 'low'
  }
  return severityFrom(absPct)
}

function severityFrom(absPct) {
  if (absPct >= 12) return 'critical'
  if (absPct >= 8) return 'high'
  if (absPct >= 4) return 'medium'
  return 'low'
}

/**
 * Parse inv-{uuid} or inv-{metric}-{YYYYMMDD} into an investigate request.
 * Throws on invalid id (matches Go).
 */
export function requestFromInvestigationID(id) {
  id = normalizeAlertID(id)
  if (looksLikeUUID(id)) {
    return { alertId: id }
  }
  // Legacy: inv-{metric}-{YYYYMMDD}
  const parts = id.split('-')
  if (parts.length < 2) {
    throw new Error('invalid investigation id')
  }
  const datePart = parts[parts.length - 1]
  let metric = parts.slice(0, -1).join('_')
  if (!metric) metric = 'revenue'
  if (!/^\d{8}$/.test(datePart)) {
    throw new Error('invalid investigation id')
  }
  const y = +datePart.slice(0, 4)
  const mo = +datePart.slice(4, 6)
  const d = +datePart.slice(6, 8)
  const day = new Date(Date.UTC(y, mo - 1, d, 0, 0, 0))
  if (Number.isNaN(day.getTime())) throw new Error('invalid investigation id')
  const ws = day
  const we = new Date(ws.getTime() + 24 * 3600 * 1000 - 1000)
  const dayStr = `${String(y).padStart(4, '0')}-${String(mo).padStart(2, '0')}-${String(d).padStart(2, '0')}`
  return {
    alertId: `alert-${metric}-${dayStr}`,
    metric,
    windowStart: formatRFC3339(ws),
    windowEnd: formatRFC3339(we),
    baselineKind: 'same_hour_4w_seasonality',
  }
}

// ── Alert wall ───────────────────────────────────────────────────────

const alertCategoryOrder = ['geo', 'os', 'campaign_type', 'ad_format', 'publisher_tier', 'content']

function categoryForDimension(dim) {
  switch (String(dim).toLowerCase()) {
    case 'country':
    case 'region':
      return 'geo'
    case 'os_version':
    case 'os':
      return 'os'
    case 'campaign_type':
      return 'campaign_type'
    case 'ad_format':
      return 'ad_format'
    case 'publisher_tier':
      return 'publisher_tier'
    case 'category':
    case 'vertical':
      return 'content'
    default:
      return ''
  }
}

function categorizeSegments(segments) {
  const seen = {}
  const bestByCat = {}
  for (const s of segments) {
    const cat = categoryForDimension(s.dimension)
    if (!cat) continue
    seen[cat] = true
    const prev = bestByCat[cat]
    if (!prev || Math.abs(s.contributionPct) > Math.abs(prev.contributionPct)) {
      bestByCat[cat] = s
    }
  }
  const ordered = []
  for (const c of alertCategoryOrder) {
    if (seen[c]) ordered.push(c)
  }
  const primary = ordered.length > 0 ? ordered[0] : ''
  const labels = ordered.map((c) => {
    const s = bestByCat[c]
    return {
      category: c,
      dimension: s.dimension,
      value: s.value,
      deltaPct: s.deltaPct,
      contributionPct: s.contributionPct,
    }
  })
  return { categories: ordered, primary, labels }
}

function mergeSegments(primary, extra, limit) {
  const seen = new Set()
  const out = []
  const key = (s) => `${s.dimension}|${s.value}`
  for (const s of primary) {
    const k = key(s)
    if (seen.has(k)) continue
    seen.add(k)
    out.push(s)
  }
  for (const s of extra) {
    if (!categoryForDimension(s.dimension)) continue
    const k = key(s)
    if (seen.has(k)) continue
    seen.add(k)
    out.push(s)
    if (out.length >= limit) break
  }
  if (out.length > limit) return out.slice(0, limit)
  return out
}

/**
 * Build the alert wall. granularity "day" (default) or "hour".
 * `cache` is accepted for API parity with Go but unused.
 */
export async function detectAlerts(client, _cache, granularity) {
  if (granularity !== 'hour') granularity = 'day'
  const rows = await selectAlertListRows(client, 28, granularity)
  if (rows.length === 0) return []

  const ids = rows.map((r) => r.alertId)
  const segsByAlert = await fetchContributorsBatch(client, ids, 8)
  let obsByAlert
  try {
    obsByAlert = await fetchObservationDetailsBatch(client, ids, 3)
  } catch {
    obsByAlert = {}
  }

  const out = []
  for (const r of rows) {
    let pct = 0
    if (r.expected !== 0) {
      pct = ((r.actual - r.expected) / Math.abs(r.expected)) * 100
    }
    let direction = 'down'
    if (pct > 0) direction = 'up'
    let metric = r.metric
    if (!metric) metric = 'revenue'
    const segments = segsByAlert[r.alertId] || []
    for (const s of segments) {
      if (!s.metric) s.metric = metric
    }
    const { categories, primary, labels } = categorizeSegments(segments)
    const live = {
      alertId: r.alertId,
      advertiserId: r.advertiserId,
      metric,
      bucket: r.bucket,
      actual: r.actual,
      expected: r.expected,
      zscore: r.zscore,
    }
    let windowStart
    let windowEnd
    let baselineKind = 'same_hour_4w_seasonality'
    if (granularity === 'day') {
      const day = new Date(Date.UTC(r.bucket.getUTCFullYear(), r.bucket.getUTCMonth(), r.bucket.getUTCDate(), 0, 0, 0))
      windowStart = day
      windowEnd = new Date(day.getTime() + 24 * 3600 * 1000 - 1000)
      baselineKind = 'daily_peak_hour'
    } else {
      windowStart = new Date(r.bucket.getTime())
      windowEnd = new Date(r.bucket.getTime() + 3600 * 1000 - 1000)
    }
    const summary = buildAlertListSummary(
      r.advertiserId,
      metric,
      direction,
      pct,
      segments,
      obsByAlert[r.alertId] || [],
    )
    out.push({
      id: r.alertId,
      metric,
      direction,
      pctChange: round1(pct),
      windowStart: formatRFC3339(windowStart),
      windowEnd: formatRFC3339(windowEnd),
      baselineKind,
      granularity,
      sourceBucket: formatRFC3339(r.bucket),
      severity: severityFromZOrPct(live, Math.abs(pct)),
      advertiserId: r.advertiserId,
      investigationId: `inv-${r.alertId}`,
      status: 'complete',
      summary,
      categories,
      primaryCategory: primary,
      categoryLabels: labels,
    })
  }
  return out
}

function buildAlertListSummary(advertiserID, metric, direction, pct, segments, obs) {
  let head = `${humanMetric(metric)} ${direction} ${formatPct(Math.abs(pct))}`
  if (advertiserID) {
    head = `${humanMetric(metric)} for ${advertiserID} ${direction} ${formatPct(Math.abs(pct))}`
  }
  if (obs.length > 0) return `${head}. ${obs.join(' ')}`
  if (segments.length === 0) return `${head}.`
  const parts = []
  for (let i = 0; i < segments.length && i < 3; i++) {
    const s = segments[i]
    parts.push(`${humanDimension(s.dimension)} ${s.value} (${formatSignedPct(s.deltaPct)})`)
  }
  return `${head}. Top segments: ${parts.join('; ')}.`
}

async function selectAlertListRows(client, limit, granularity) {
  if (limit <= 0) limit = 24
  if (granularity !== 'hour') granularity = 'day'
  const seen = new Set()
  const out = []

  const appendRows = (rows) => {
    for (const r of rows) {
      const id = asString(r.id)
      if (!id || seen.has(id)) continue
      let bucket
      try {
        bucket = parseCHTime(asString(r.bucket))
      } catch {
        continue
      }
      seen.add(id)
      out.push({
        alertId: id,
        advertiserId: asString(r.advertiser_id),
        metric: asString(r.metric),
        bucket,
        actual: asFloat(r.actual),
        expected: asFloat(r.expected),
        zscore: asFloat(r.zscore),
      })
      if (out.length >= limit) return
    }
  }

  const dailyPeaksCTE = `
		WITH daily_peaks AS (
			SELECT
				alert_id,
				advertiser_id,
				metric,
				bucket,
				actual,
				expected,
				zscore
			FROM (
				SELECT
					alert_id,
					advertiser_id,
					metric,
					bucket,
					actual,
					expected,
					zscore,
					row_number() OVER (
						PARTITION BY advertiser_id, metric, toDate(bucket)
						ORDER BY abs(zscore) DESC
					) AS day_rn
				FROM alerts_live
				WHERE abs(zscore) > 3
			)
			WHERE day_rn = 1
		)
	`

  let richLimit = Math.floor(limit / 3)
  if (richLimit < 6) richLimit = 6
  if (richLimit > limit) richLimit = limit

  let rich
  if (granularity === 'day') {
    rich = await queryMaps(
      client,
      `
			${dailyPeaksCTE}
			SELECT
				toString(alert_id) AS id,
				advertiser_id,
				metric,
				toString(bucket) AS bucket,
				actual,
				expected,
				zscore
			FROM daily_peaks
			WHERE alert_id IN (SELECT DISTINCT alert_id FROM alert_dimension_contributors)
			   OR alert_id IN (SELECT DISTINCT alert_id FROM alert_observations)
			ORDER BY abs(zscore) DESC
			LIMIT ${richLimit}
		`,
    )
  } else {
    rich = await queryMaps(
      client,
      `
			SELECT
				toString(a.alert_id) AS id,
				a.advertiser_id AS advertiser_id,
				a.metric AS metric,
				toString(a.bucket) AS bucket,
				a.actual AS actual,
				a.expected AS expected,
				a.zscore AS zscore
			FROM alerts_live AS a
			WHERE abs(a.zscore) > 3
			  AND (
				a.alert_id IN (SELECT DISTINCT alert_id FROM alert_dimension_contributors)
				OR a.alert_id IN (SELECT DISTINCT alert_id FROM alert_observations)
			  )
			ORDER BY abs(a.zscore) DESC
			LIMIT ${richLimit}
		`,
    )
  }
  appendRows(rich)
  if (out.length >= limit) return out

  const excludeIDs = out.map((r) => `toUUID(${quoteString(r.alertId)})`)
  let excludeIDClause = ''
  if (excludeIDs.length > 0) {
    excludeIDClause = ` AND alert_id NOT IN (${excludeIDs.join(',')})`
  }

  const excludeAds = []
  for (const r of out) {
    if (r.advertiserId) excludeAds.push(quoteString(r.advertiserId))
  }
  let excludeAdClause = ''
  if (excludeAds.length > 0) {
    excludeAdClause = ` AND advertiser_id NOT IN (${excludeAds.join(',')})`
  }

  let diverse
  if (granularity === 'day') {
    diverse = await queryMaps(
      client,
      `
			${dailyPeaksCTE}
			SELECT
				toString(alert_id) AS id,
				advertiser_id,
				metric,
				toString(bucket) AS bucket,
				actual,
				expected,
				zscore
			FROM (
				SELECT
					alert_id,
					advertiser_id,
					metric,
					bucket,
					actual,
					expected,
					zscore,
					row_number() OVER (
						PARTITION BY advertiser_id, toDate(bucket)
						ORDER BY abs(zscore) DESC
					) AS rn
				FROM daily_peaks
				WHERE 1=1${excludeIDClause}
			)
			WHERE rn = 1
			ORDER BY abs(zscore) DESC
			LIMIT ${limit - out.length}
		`,
    )
  } else {
    diverse = await queryMaps(
      client,
      `
			SELECT
				toString(alert_id) AS id,
				advertiser_id,
				metric,
				toString(bucket) AS bucket,
				actual,
				expected,
				zscore
			FROM (
				SELECT
					alert_id,
					advertiser_id,
					metric,
					bucket,
					actual,
					expected,
					zscore,
					row_number() OVER (PARTITION BY advertiser_id ORDER BY abs(zscore) DESC) AS rn
				FROM alerts_live
				WHERE abs(zscore) > 3${excludeAdClause}
			)
			WHERE rn = 1
			ORDER BY abs(zscore) DESC
			LIMIT ${limit - out.length}
		`,
    )
  }
  appendRows(diverse)
  return out
}

async function fetchContributorsBatch(client, alertIDs, perAlert) {
  const out = {}
  if (!alertIDs.length) return out
  if (perAlert <= 0) perAlert = 8
  const quoted = []
  for (const id of alertIDs) {
    if (!looksLikeUUID(id)) continue
    quoted.push(`toUUID(${quoteString(id)})`)
  }
  if (!quoted.length) return out
  const q = `
		SELECT
			toString(alert_id) AS alert_id,
			dimension,
			dimension_value,
			current_value,
			baseline_value,
			delta,
			contribution
		FROM (
			SELECT
				alert_id,
				dimension,
				dimension_value,
				current_value,
				baseline_value,
				delta,
				contribution,
				row_number() OVER (PARTITION BY alert_id ORDER BY abs(delta) DESC) AS rn
			FROM alert_dimension_contributors
			WHERE alert_id IN (${quoted.join(',')})
		)
		WHERE rn <= ${perAlert}
		ORDER BY alert_id, abs(delta) DESC
	`
  const rows = await queryMaps(client, q)
  for (const r of rows) {
    const id = asString(r.alert_id)
    const base = asFloat(r.baseline_value)
    const cur = asFloat(r.current_value)
    let contrib = asFloat(r.contribution)
    if (Math.abs(contrib) <= 1.5) contrib *= 100
    if (!out[id]) out[id] = []
    out[id].push({
      dimension: asString(r.dimension),
      value: asString(r.dimension_value),
      deltaPct: round1(pctChange(cur, base)),
      contributionPct: round1(contrib),
    })
  }
  return out
}

async function fetchObservationDetailsBatch(client, alertIDs, perAlert) {
  const out = {}
  if (!alertIDs.length) return out
  if (perAlert <= 0) perAlert = 3
  const quoted = []
  for (const id of alertIDs) {
    if (!looksLikeUUID(id)) continue
    quoted.push(`toUUID(${quoteString(id)})`)
  }
  if (!quoted.length) return out
  const q = `
		SELECT
			toString(alert_id) AS alert_id,
			detail
		FROM (
			SELECT
				alert_id,
				detail,
				row_number() OVER (PARTITION BY alert_id ORDER BY observation_order ASC) AS rn
			FROM alert_observations
			WHERE alert_id IN (${quoted.join(',')})
		)
		WHERE rn <= ${perAlert}
		ORDER BY alert_id, rn
	`
  const rows = await queryMaps(client, q)
  for (const r of rows) {
    const id = asString(r.alert_id)
    const detail = asString(r.detail).trim()
    if (!detail) continue
    if (!out[id]) out[id] = []
    out[id].push(detail)
  }
  return out
}

/** Export bundle shape from main.go GET /investigations/{id}/export */
export function buildExportBundle(inv) {
  return {
    exportedAt: formatRFC3339(new Date()),
    purpose: 'investigation-export',
    investigation: inv,
    immutableTrace: inv.trace,
    evidenceHash: inv.evidence?.hash,
    evidence: inv.evidence,
    seasonality: inv.seasonality,
    waterfall: inv.waterfall,
    counterfactual: inv.counterfactual,
    hypotheses: inv.hypotheses,
  }
}
