/** Dashboard metric / dimension catalog + date helpers */

export const DEFAULT_METRICS = ['revenue', 'requests', 'fill_rate', 'ecpm']
export const DEFAULT_DIMENSIONS = [
  'ad_format',
  'country',
  'os_version',
  'campaign_type',
  'publisher_tier',
]

export const FALLBACK_META = {
  metrics: [
    { id: 'revenue', label: 'Revenue' },
    { id: 'requests', label: 'Requests' },
    { id: 'impressions', label: 'Impressions' },
    { id: 'clicks', label: 'Clicks' },
    { id: 'fill_rate', label: 'Fill rate' },
    { id: 'ctr', label: 'CTR' },
    { id: 'ecpm', label: 'eCPM' },
    { id: 'rpr', label: 'RPR' },
  ],
  dimensions: [
    { id: 'ad_format', label: 'Ad format' },
    { id: 'region', label: 'Region' },
    { id: 'country', label: 'Country' },
    { id: 'os_version', label: 'OS' },
    { id: 'campaign_type', label: 'Campaign type' },
    { id: 'publisher_tier', label: 'Publisher tier' },
    { id: 'category', label: 'Category' },
    { id: 'vertical', label: 'Vertical' },
  ],
}

export const DATE_PRESETS = [
  { id: 'day', label: 'Single day' },
  { id: 'last_7', label: 'Last 7 days' },
  { id: 'june', label: 'Full month' },
  { id: 'custom', label: 'Custom' },
]

/** Preset windows aligned to the loaded snapshot range (2026-06-01 .. 2026-07-05). */
export function rangeFromPreset(presetId) {
  if (presetId === 'last_7') {
    return {
      start: '2026-06-15T00:00:00Z',
      end: '2026-06-21T23:59:59Z',
    }
  }
  if (presetId === 'june') {
    return {
      start: '2026-06-01T00:00:00Z',
      end: '2026-06-30T23:59:59Z',
    }
  }
  return {
    start: '2026-06-21T00:00:00Z',
    end: '2026-06-21T23:59:59Z',
  }
}

export function compareRangeFor(startISO, endISO) {
  const start = new Date(startISO)
  const end = new Date(endISO)
  const ms = end.getTime() - start.getTime()
  const cEnd = new Date(start.getTime() - 1000)
  const cStart = new Date(cEnd.getTime() - ms)
  return {
    start: cStart.toISOString(),
    end: cEnd.toISOString(),
  }
}

export function formatMetricValue(metricId, value) {
  const n = Number(value) || 0
  if (metricId === 'fill_rate' || metricId === 'ctr') {
    return `${(n * 100).toFixed(1)}%`
  }
  if (metricId === 'ecpm') return `$${n.toFixed(2)}`
  if (metricId === 'rpr') return n.toFixed(4)
  if (metricId === 'revenue') return n.toFixed(2)
  if (Math.abs(n) >= 1000) return Math.round(n).toLocaleString('en-US')
  return n.toFixed(2)
}

export function metricLabel(meta, id) {
  return meta?.metrics?.find((m) => m.id === id)?.label || id
}

export function dimensionLabel(meta, id) {
  return meta?.dimensions?.find((d) => d.id === id)?.label || id
}
