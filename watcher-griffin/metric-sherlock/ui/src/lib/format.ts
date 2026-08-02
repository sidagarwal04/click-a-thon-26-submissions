/* Number and label formatting, in one place.
 *
 * This exists because the old UI formatted ad hoc: `maximumFractionDigits: 4` in six
 * separate call sites, `.toFixed(4)` / `.toFixed(2)` / `.toFixed(1)` scattered around,
 * revenue rendered without a currency symbol, and raw metric identifiers (`fill_rate`,
 * `ecpm`, `rpr`, `z=`) shown verbatim to an audience with no reason to know them.
 *
 * An ops reader should see "Fill rate 77.6%" and "$1,680.44", not "fill_rate 0.7759"
 * and "1680.4372881". Formatting is part of whether a number is trustworthy: a figure
 * shown to 7 decimal places reads as machine output nobody checked.
 */

/** Money. Always with a symbol, always 2dp, always grouped. */
export function usd(n: number | null | undefined, opts?: { sign?: boolean }): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  const s = Math.abs(n).toLocaleString(undefined, {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
  if (opts?.sign) return `${n < 0 ? '−' : '+'}${s}`
  return n < 0 ? `−${s}` : s
}

/** Compact money for dense rows: $1.7k, $670. */
export function usdCompact(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  const a = Math.abs(n)
  const sign = n < 0 ? '−' : ''
  if (a >= 1000) return `${sign}$${(a / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })}k`
  return `${sign}$${a.toLocaleString(undefined, { maximumFractionDigits: a < 10 ? 2 : 0 })}`
}

/** A rate stored as a fraction (0.7759) rendered as a percentage (77.59%). */
export function rate(n: number | null | undefined, dp = 2): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return `${(n * 100).toFixed(dp)}%`
}

/** A change already expressed as a fraction, with an explicit sign. */
export function delta(n: number | null | undefined, dp = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  const pct = n * 100
  return `${pct >= 0 ? '+' : '−'}${Math.abs(pct).toFixed(dp)}%`
}

/** Percentage-point difference between two rates — the correct unit for a fill-rate
 *  move. Reporting "fill rate fell 0.6%" when it went 78.05% → 77.59% is wrong by a
 *  factor of ~130; it fell 0.46 percentage points. */
export function pp(a: number | null | undefined, b: number | null | undefined, dp = 2): string {
  if (a === null || a === undefined || b === null || b === undefined) return '—'
  const d = (a - b) * 100
  return `${d >= 0 ? '+' : '−'}${Math.abs(d).toFixed(dp)}pp`
}

/** Whole counts, grouped. */
export function count(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  return Math.round(n).toLocaleString()
}

/** Compact counts for dense rows: 232.7k, 9.0M. */
export function countCompact(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—'
  const a = Math.abs(n)
  if (a >= 1_000_000) return `${(n / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 1 })}M`
  if (a >= 1000) return `${(n / 1000).toLocaleString(undefined, { maximumFractionDigits: 1 })}k`
  return Math.round(n).toLocaleString()
}

/** Formats a metric value according to its unit, so a caller never has to remember
 *  whether a given metric is a rate, money, or a count. */
export function metricValue(value: number | null | undefined, unit: string): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  if (unit === '%') return rate(value)
  if (unit === '$') return value >= 1000 ? usd(value) : `$${value.toFixed(value < 10 ? 4 : 2)}`
  return countCompact(value)
}

/** Band-widths from centre. Named in words rather than as a bare "z=" — an ops reader
 *  is not obliged to know what a z-score is. */
export function bandWidths(score: number | null | undefined): string {
  if (score === null || score === undefined || Number.isNaN(score)) return '—'
  return `${Math.abs(score).toFixed(1)}× band`
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString(undefined, {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
  })
}

export function dateOnly(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })
}

/** "3 days ago" — relative to the DATA's clock, not the browser's, which matters
 *  because this dataset is historical and the wall clock is far ahead of it. */
export function ago(iso: string | null | undefined, nowIso?: string | null): string {
  if (!iso) return '—'
  const then = new Date(iso).getTime()
  const now = nowIso ? new Date(nowIso).getTime() : Date.now()
  if (Number.isNaN(then) || Number.isNaN(now)) return '—'
  const mins = Math.round((now - then) / 60000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 48) return `${hrs}h ago`
  return `${Math.round(hrs / 24)}d ago`
}

/** Window duration in the grain's own terms. */
export function windowLabel(start: string | null, end: string | null): string {
  if (!start || !end) return '—'
  return `${dateTime(start)} → ${dateTime(end)}`
}

/** The same range with the clock times dropped: "Jul 11 → Aug 1".
 *
 *  For narrow columns. windowLabel carries hours and minutes, which is right in a page-wide
 *  meta line and wrong in a 180px cell, where it wraps to two rows and costs more height
 *  than the two midnight timestamps were ever worth. Incident windows start and end on
 *  grain boundaries, so for day-and-coarser grains the times are 00:00 anyway. */
export function dayRange(start: string | null, end: string | null): string {
  if (!start || !end) return '—'
  const fmt = (iso: string) => {
    const d = new Date(iso)
    if (Number.isNaN(d.getTime())) return '—'
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  }
  return `${fmt(start)} → ${fmt(end)}`
}

/** Human label for a scope entity: `APAC|JP|iPhone 14` → `APAC × JP × iPhone 14`,
 *  and the global scope's empty value → `overall`. */
export function scopeValue(v: string | null | undefined): string {
  if (v === null || v === undefined || v === '') return 'overall'
  return v.split('|').join(' × ')
}

export function scopeLabel(scopeType: string, value: string | null | undefined): string {
  if (!scopeType || scopeType === 'global') return 'Platform overall'
  return scopeValue(value)
}

/* Plain-language metric names. Shared, because the queue and the incident page were both
 * building their own version and the detail page was still rendering the raw column name —
 * a reader should never be shown `fill_rate` or `rpr`. */
const METRIC_LABELS: Record<string, string> = {
  revenue: 'Revenue',
  requests: 'Ad requests',
  fills: 'Fills',
  impressions: 'Impressions',
  clicks: 'Clicks',
  fill_rate: 'Fill rate',
  render_rate: 'Show rate',
  ctr: 'Click-through rate',
  ecpm: 'eCPM',
  rpr: 'Revenue per request',
}

export function metricLabel(metric: string): string {
  return METRIC_LABELS[metric] ?? metric
}

/** How a scope reads in a sentence: `os_family` → "OS family", `geo_cell` → "region and
 *  device". Keeps the interface in the reader's vocabulary rather than the schema's. */
const SCOPE_WORDS: Record<string, string> = {
  global: 'the whole platform',
  region: 'region',
  country: 'country',
  device_model: 'device',
  os_version: 'OS version',
  os_family: 'OS',
  ad_format: 'ad format',
  app: 'app',
  category: 'app category',
  publisher_tier: 'publisher tier',
  advertiser: 'advertiser',
  vertical: 'advertiser vertical',
  campaign_type: 'campaign type',
  geo_cell: 'region and device',
  os_family_region: 'OS and region',
  format_region: 'format and region',
}

export function scopeWord(scopeType: string): string {
  return SCOPE_WORDS[scopeType] ?? scopeType.replace(/_/g, ' ')
}
