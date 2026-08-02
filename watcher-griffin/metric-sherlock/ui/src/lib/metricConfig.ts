/* How a metric is PRESENTED — keyed by unit, not by metric name.
 *
 * WHY UNIT AND NOT METRIC
 * The backend already owns every metric-identity fact: `label`, `unit`, the plain-English
 * `meaning`, and the order metrics appear in all come from engine/ops_view.py and arrive on
 * each TreeNode. Today, adding a metric there makes it appear in this UI with zero front-end
 * changes. A config keyed by metric name (`revenue: { label: 'Revenue', ... }`) would undo
 * that: a new backend metric would silently vanish from the selector until someone
 * remembered to add an entry, and the labels would be a second copy of METRIC_LABELS in
 * format.ts that is free to drift from the server's.
 *
 * So the parts that genuinely vary by metric — how a value is written, whether a change is
 * measured in percentage points or percent, and what colour the signal is drawn in — are
 * derived from the metric's UNIT, which the server sends. Three units ('$', '%', '') cover
 * every metric that exists or is planned, and an unknown unit falls back to the plain-count
 * form rather than rendering nothing.
 *
 * WHERE THE OTHER CONFIG FIELDS WENT
 *   display name  -> node.label      (server)
 *   key           -> node.metric     (server)
 *   prefix/suffix -> implied by unit; metricValue() writes '$' before and '%' after
 *   formatter     -> formatValue below, delegating to the one formatter in format.ts
 *   decimals      -> deltaDecimals below; value decimals are magnitude-dependent and live
 *                    in metricValue(), which is deliberately the single place they exist
 *   chart colour  -> accentToken below, threaded into BandChart's `accent` prop
 *
 * ADDING A METRIC THAT NEEDS SOMETHING DIFFERENT
 * One entry in OVERRIDES, keyed by the metric identifier. It ships empty on purpose — an
 * empty override map is the evidence that nothing is hardcoded per metric today.
 */

import { metricValue, pp } from './format'
import type { TreeNode } from '../types'

/** How a change in this metric is expressed. */
export type DeltaMode = 'pp' | 'pct'

export interface MetricFormat {
  /** Renders a value of this metric. */
  formatValue: (v: number | null | undefined) => string
  /** Percentage POINTS for rates, percent for everything else. See formatDeviation. */
  deltaMode: DeltaMode
  /** Decimal places on the deviation figure. */
  deltaDecimals: number
  /** CSS custom-property NAME (not a value) for the chart's signal colour. */
  accentToken: string
}

/* Every metric draws in --series-1. That is not laziness: --series-2/3/4 are spoken for by
 * the owner badges (lib/status.ts OWNER_COLORS), and giving eCPM its own hue here would put
 * a second, meaningless colour language on a screen whose colour already means severity.
 * Only one chart is on screen at a time, so a per-metric hue would distinguish nothing. */
const BY_UNIT: Record<string, MetricFormat> = {
  $: {
    formatValue: (v) => metricValue(v, '$'),
    deltaMode: 'pct',
    deltaDecimals: 1,
    accentToken: '--series-1',
  },
  '%': {
    formatValue: (v) => metricValue(v, '%'),
    deltaMode: 'pp',
    deltaDecimals: 2,
    accentToken: '--series-1',
  },
  '': {
    formatValue: (v) => metricValue(v, ''),
    deltaMode: 'pct',
    deltaDecimals: 1,
    accentToken: '--series-1',
  },
}

/** Per-metric overrides. EMPTY BY DESIGN — see the header. Add an entry only when a metric
 *  genuinely needs presentation that differs from its unit's default. */
const OVERRIDES: Record<string, Partial<MetricFormat>> = {}

export function resolveMetricFormat(metric: string, unit: string): MetricFormat {
  const base = BY_UNIT[unit] ?? BY_UNIT['']
  const override = OVERRIDES[metric]
  return override ? { ...base, ...override } : base
}

/** The deviation figure shown beside "expected".
 *
 *  Rates are compared in percentage POINTS. Fill rate moving 78.05% -> 77.59% is a 0.46pp
 *  fall; calling it "-0.6%" describes a ratio of ratios and sounds ten times smaller than
 *  it is. Non-rates use the server's own pct_change rather than recomputing it here, so the
 *  UI can never disagree with the engine about the size of a move. */
export function formatDeviation(node: TreeNode, fmt: MetricFormat): string | null {
  if (node.value === null || node.center === null) return null
  if (fmt.deltaMode === 'pp') return pp(node.value, node.center, fmt.deltaDecimals)
  if (node.pct_change === null) return null
  const sign = node.pct_change >= 0 ? '+' : '−'
  return `${sign}${Math.abs(node.pct_change * 100).toFixed(fmt.deltaDecimals)}%`
}

/* Metric identifier -> unit.
 *
 * The exception to this file's own rule that presentation is keyed by unit and never by metric
 * name. It exists because /api/incidents sends `root_metric` but no unit -- unlike the ops
 * tree, which sends `unit` on every node -- so the choice here is a local map or an
 * unformatted number. Everything downstream still keys off the RESOLVED UNIT, not the metric,
 * so adding a metric that shares an existing unit needs one line here and nothing else.
 *
 * An unknown metric falls back to '' (plain count), which renders a number rather than
 * nothing. */
const METRIC_UNITS: Record<string, string> = {
  revenue: '$',
  ecpm: '$',
  rpr: '$',
  fill_rate: '%',
  render_rate: '%',
  ctr: '%',
  requests: '',
  fills: '',
  impressions: '',
  clicks: '',
}

export function unitForMetric(metric: string): string {
  return METRIC_UNITS[metric] ?? ''
}

/** How far a metric moved, from a raw observed/expected pair.
 *
 *  The incident list carries `value` and `center` but no `pct_change`, so this derives the
 *  move itself — and picks the right unit for it. Rates move in percentage POINTS: fill rate
 *  going 78.50% → 72.25% is a 6.25pp fall, and calling that "−8.0%" describes a ratio of
 *  ratios and understates it by an order of magnitude. Everything else is a plain percent. */
export function formatMove(
  metric: string,
  value: number | null | undefined,
  center: number | null | undefined,
): string | null {
  if (value === null || value === undefined || center === null || center === undefined) return null
  const fmt = resolveMetricFormat(metric, unitForMetric(metric))
  if (fmt.deltaMode === 'pp') return pp(value, center, fmt.deltaDecimals)
  if (!center) return null
  const change = (value - center) / center
  const sign = change >= 0 ? '+' : '−'
  return `${sign}${Math.abs(change * 100).toFixed(fmt.deltaDecimals)}%`
}
