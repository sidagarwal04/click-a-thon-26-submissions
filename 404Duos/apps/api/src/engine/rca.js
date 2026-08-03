import { createHash } from 'node:crypto'
import {
  formatNumber,
  formatPct,
  formatSignedPct,
  humanDimension,
  humanMetric,
  pctChange,
  round1,
  roundMoney,
} from './util.js'

export function revenueIdentity(m) {
  return m.requests * fillRate(m) * renderRate(m) * (ecpm(m) / 1000)
}

export function fillRate(m) {
  if (!m.requests) return 0
  return m.fills / m.requests
}

export function renderRate(m) {
  if (!m.fills) return 0
  return m.impressions / m.fills
}

export function ctr(m) {
  if (!m.impressions) return 0
  return m.clicks / m.impressions
}

export function ecpm(m) {
  if (!m.impressions) return 0
  return (m.revenue / m.impressions) * 1000
}

export function rpr(m) {
  if (!m.requests) return 0
  return m.revenue / m.requests
}

export function metricValue(m, metric) {
  switch (metric) {
    case 'fill_rate':
      return fillRate(m)
    case 'requests':
      return m.requests
    case 'impressions':
      return m.impressions
    case 'ctr':
      return ctr(m)
    case 'ecpm':
      return ecpm(m)
    case 'rpr':
      return rpr(m)
    default:
      return m.revenue
  }
}

/**
 * Compare a naive (non–day-of-week) baseline vs a like-for-like seasonal baseline
 * (same weekday / same hour × trailing weeks).
 *
 * Always compute the residual from the seasonal bag — never trust a caller-supplied
 * pct that may come from alerts_live / a flat expectation (that is what makes every
 * weekend look like an anomaly).
 *
 * If the naive view looks anomalous but the seasonal residual is small,
 * mark as seasonality (not an incident).
 */
export function evaluateSeasonality(metric, observed, seasonal, flat, _unusedSeasonalPct) {
  const obsV = metricValue(observed, metric)
  const flatPct = pctChange(obsV, metricValue(flat, metric))
  const seasPct = pctChange(obsV, metricValue(seasonal, metric))

  if (Math.abs(flatPct) >= 5 && Math.abs(seasPct) < 3) {
    return {
      status: 'ruled_out_as_seasonality',
      flatDeltaPct: round1(flatPct),
      seasonalDeltaPct: round1(seasPct),
      detail: `Vs a naive trailing average (mixed weekdays) this looked like ${formatSignedPct(round1(flatPct))}, but vs same weekday/hour × 4 weeks residual is only ${formatSignedPct(round1(seasPct))} — consistent with daily/weekly seasonality, not a new incident.`,
    }
  }
  if (Math.abs(seasPct) >= 5) {
    return {
      status: 'residual_remains',
      flatDeltaPct: round1(flatPct),
      seasonalDeltaPct: round1(seasPct),
      detail: `Same weekday/hour × 4-week seasonality applied (naive trailing average was ${formatSignedPct(round1(flatPct))}). Residual vs like-for-like baseline is ${formatSignedPct(round1(seasPct))} — still anomalous.`,
    }
  }
  return {
    status: 'skipped',
    flatDeltaPct: round1(flatPct),
    seasonalDeltaPct: round1(seasPct),
    detail: 'Movement within noise after like-for-like seasonality adjustment.',
  }
}

export function buildWaterfall(base, obs, decomp) {
  const order = ['requests', 'fill_rate', 'render_rate', 'ecpm']
  const labels = {
    requests: 'Requests',
    fill_rate: 'Fill rate',
    render_rate: 'Render rate',
    ecpm: 'eCPM',
  }
  const statusBy = {}
  for (const f of decomp) {
    statusBy[f.factor] = f.status
  }

  let cur = { ...base }
  const baseRev = revenueIdentity(base)
  const steps = []
  const impacts = []

  function apply(bag, factor) {
    const out = { ...bag }
    switch (factor) {
      case 'requests':
        out.requests = obs.requests
        break
      case 'fill_rate':
        out.fills = fillRate(obs) * out.requests
        break
      case 'render_rate':
        out.impressions = renderRate(obs) * out.fills
        break
      case 'ecpm':
        if (out.impressions > 0) {
          out.revenue = (ecpm(obs) / 1000) * out.impressions
        }
        break
      default:
        break
    }
    return out
  }

  let prevRev = baseRev
  for (const factor of order) {
    let next = apply(cur, factor)
    if (factor === 'fill_rate' || factor === 'render_rate' || factor === 'requests') {
      next.revenue = revenueIdentity(next)
    }
    if (factor === 'ecpm') {
      next.revenue = (ecpm(obs) / 1000) * next.impressions
    }
    let rev = next.revenue
    if (factor !== 'ecpm') {
      rev = revenueIdentity(next)
    }
    const impact = rev - prevRev
    impacts.push(impact)
    let st = statusBy[factor]
    if (!st) st = 'neutral'
    steps.push({
      factor,
      label: labels[factor],
      revenueImpact: roundMoney(impact),
      sharePct: 0,
      status: st,
    })
    cur = next
    prevRev = rev
  }

  let totalAbs = 0
  for (const v of impacts) totalAbs += Math.abs(v)
  for (let i = 0; i < steps.length; i++) {
    if (totalAbs > 0) {
      steps[i].sharePct = round1((Math.abs(impacts[i]) / totalAbs) * 100)
    }
  }
  return steps
}

export function buildCounterfactual(culprit, base, obs) {
  const cf = { ...obs }
  switch (culprit) {
    case 'requests':
      cf.requests = base.requests
      cf.fills = fillRate(obs) * cf.requests
      cf.impressions = renderRate(obs) * cf.fills
      cf.revenue = (ecpm(obs) / 1000) * cf.impressions
      break
    case 'fill_rate':
      cf.fills = fillRate(base) * obs.requests
      cf.impressions = renderRate(obs) * cf.fills
      cf.revenue = (ecpm(obs) / 1000) * cf.impressions
      break
    case 'render_rate':
      cf.impressions = renderRate(base) * obs.fills
      cf.revenue = (ecpm(obs) / 1000) * cf.impressions
      break
    case 'ecpm':
      cf.revenue = (ecpm(base) / 1000) * obs.impressions
      break
    default:
      cf.revenue = revenueIdentity(base)
      break
  }

  let obsRev = obs.revenue
  if (obsRev === 0) obsRev = revenueIdentity(obs)
  let baseRev = base.revenue
  if (baseRev === 0) baseRev = revenueIdentity(base)
  const cfRev = cf.revenue
  const gap = baseRev - obsRev
  let recovered = cfRev - obsRev
  let recPct = 0
  if (Math.abs(gap) > 1e-9) {
    recPct = (recovered / gap) * 100
  }

  const detail = `If ${humanMetric(culprit)} had stayed at baseline, estimated revenue would be ${formatNumber(roundMoney(cfRev))} instead of ${formatNumber(roundMoney(obsRev))} (recover ${formatPct(round1(recPct))} of the gap).`

  return {
    culprit,
    observedRevenue: roundMoney(obsRev),
    counterfactualRevenue: roundMoney(cfRev),
    recoveredRevenue: roundMoney(recovered),
    recoveredPctOfGap: round1(recPct),
    detail,
  }
}

function pctChangeForFactor(decomp, factor) {
  for (const f of decomp) {
    if (f.factor === factor) return f.deltaPct
  }
  return 0
}

export function buildHypotheses(decomp, culprit, segments) {
  const items = []
  for (const f of decomp) {
    if (f.factor === 'ctr') continue
    items.push({
      factor: f.factor,
      label: f.label,
      score: Math.abs(f.deltaPct),
      status: f.status,
    })
  }
  items.sort((a, b) => b.score - a.score)
  let total = 0
  for (const it of items) total += it.score

  const out = []
  for (let i = 0; i < items.length && i < 2; i++) {
    const it = items[i]
    let conf = 0
    if (total > 0) conf = (it.score / total) * 100
    let why = `${it.label} moved ${formatSignedPct(round1(pctChangeForFactor(decomp, it.factor)))} vs baseline.`
    if (i === 0 && segments.length > 0) {
      why += ` Top slice: ${humanDimension(segments[0].dimension)}=${segments[0].value} (${formatPct(segments[0].contributionPct)} contribution).`
    }
    if (i === 1) {
      why += ' Demoted because absolute % move is smaller than the primary factor.'
    }
    if (it.factor === culprit) {
      why = `Selected as primary culprit from revenue-identity walk. ${why}`
    }
    out.push({
      rank: i + 1,
      factor: it.factor,
      label: it.label,
      confidencePct: round1(conf),
      why,
    })
  }
  return out
}

export function buildEvidenceLock(inv) {
  // Go marshals map[string]any with sorted keys; nested structs keep field order.
  const payload = {
    id: inv.id,
    alert: inv.alert,
    decomposition: inv.decomposition,
    segments: inv.segments,
    ruledOut: inv.ruledOut,
    waterfall: inv.waterfall,
    counterfactual: inv.counterfactual,
    seasonality: inv.seasonality,
    hypotheses: inv.hypotheses,
    diagnosis: inv.diagnosis,
    trace: inv.trace,
  }
  const keys = Object.keys(payload).sort()
  const b = `{${keys.map((k) => `${JSON.stringify(k)}:${JSON.stringify(payload[k])}`).join(',')}}`
  const hash = createHash('sha256').update(b).digest('hex')
  return {
    hash,
    generatedAt: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'),
    sources: [
      'insightiq.alerts_live',
      'insightiq.metric_hourly_snapshot',
      'insightiq.alert_dimension_contributors',
      'insightiq.alert_observations',
    ],
  }
}

export function enrichRuledOutWithSeasonality(ruled, season) {
  const out = []
  for (const r of ruled) {
    if (String(r.reason).toLowerCase() === 'seasonality check') continue
    out.push(r)
  }
  switch (season.status) {
    case 'ruled_out_as_seasonality':
      out.unshift({
        reason: 'Seasonality (not an incident)',
        detail: season.detail,
      })
      break
    case 'residual_remains':
      out.push({
        reason: 'Seasonality checked — residual remains',
        detail: season.detail,
      })
      break
    default:
      break
  }
  return out
}

export function appendCounterfactualCitation(d, cf) {
  const citations = [
    ...(d.citations || []),
    {
      label: 'Counterfactual recovery',
      value: `${formatNumber(cf.recoveredRevenue)} recovered (${formatPct(cf.recoveredPctOfGap)} of gap) if ${humanMetric(cf.culprit)} held`,
    },
  ]
  let text = d.text || ''
  if (cf.culprit && !text.includes('Counterfactual')) {
    text = `${text.trim()} Counterfactual: holding ${humanMetric(cf.culprit)} recovers ${formatPct(cf.recoveredPctOfGap)} of the gap.`
  }
  return { text, citations }
}
