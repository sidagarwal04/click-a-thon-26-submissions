/** Match Go math.Round(v*10)/10 */
export function round1(v) {
  return Math.round(Number(v) * 10) / 10
}

/** Match Go roundMoney: 4 decimal places */
export function roundMoney(v) {
  return Math.round(Number(v) * 10000) / 10000
}

export function pctChange(obs, base) {
  if (base === 0) {
    if (obs === 0) return 0
    return 100
  }
  return ((obs - base) / Math.abs(base)) * 100
}

export function formatPct(v) {
  return `${Number(v).toFixed(1)}%`
}

export function formatSignedPct(v) {
  if (v > 0) return `+${Number(v).toFixed(1)}%`
  return `${Number(v).toFixed(1)}%`
}

export function formatInt(v) {
  let n = Math.round(Number(v))
  const neg = n < 0
  if (neg) n = -n
  const s = String(n)
  let out = ''
  for (let i = 0; i < s.length; i++) {
    if (i > 0 && (s.length - i) % 3 === 0) out += ','
    out += s[i]
  }
  return neg ? `-${out}` : out
}

export function formatNumber(v) {
  if (Math.abs(v) >= 1000) return formatInt(v)
  return Number(v).toFixed(4)
}

export function formatFactorValue(factor, v) {
  switch (factor) {
    case 'fill_rate':
    case 'render_rate':
    case 'ctr':
      return `${(v * 100).toFixed(1)}%`
    case 'ecpm':
      return `$${Number(v).toFixed(2)}`
    case 'requests':
    case 'impressions':
    case 'clicks':
    case 'fills':
      return formatInt(v)
    default:
      if (Math.abs(v) >= 1000) return formatInt(v)
      return Number(v).toFixed(2)
  }
}

export function humanMetric(m) {
  switch (m) {
    case 'fill_rate':
      return 'Fill rate'
    case 'render_rate':
      return 'Render rate'
    case 'ecpm':
      return 'eCPM'
    case 'ctr':
      return 'CTR'
    case 'rpr':
      return 'Revenue per request'
    case 'requests':
      return 'Requests'
    case 'impressions':
      return 'Impressions'
    case 'revenue':
      return 'Revenue'
    default: {
      const s = String(m || '').replace(/_/g, ' ')
      if (!s) return s
      return s.charAt(0).toUpperCase() + s.slice(1)
    }
  }
}

export function humanDimension(d) {
  switch (d) {
    case 'ad_format':
      return 'Ad format'
    case 'publisher_tier':
      return 'Publisher tier'
    case 'campaign_type':
      return 'Campaign type'
    case 'device_model':
      return 'Device'
    case 'os_version':
      return 'OS'
    default:
      return humanMetric(d)
  }
}

/** RFC3339 without milliseconds (matches Go time.RFC3339 for whole seconds). */
export function formatRFC3339(d) {
  return d.toISOString().replace(/\.\d{3}Z$/, 'Z')
}

export function parseFlexibleTime(s) {
  if (!s) throw new Error(`invalid time: ${s}`)
  // RFC3339 / ISO
  const iso = Date.parse(s)
  if (!Number.isNaN(iso) && (s.includes('T') || s.includes('Z') || s.includes('+'))) {
    return new Date(iso)
  }
  // YYYY-MM-DD HH:mm:ss
  const m1 = String(s).match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})/)
  if (m1) {
    return new Date(Date.UTC(+m1[1], +m1[2] - 1, +m1[3], +m1[4], +m1[5], +m1[6]))
  }
  // YYYY-MM-DD
  const m2 = String(s).match(/^(\d{4})-(\d{2})-(\d{2})$/)
  if (m2) {
    return new Date(Date.UTC(+m2[1], +m2[2] - 1, +m2[3], 0, 0, 0))
  }
  if (!Number.isNaN(iso)) return new Date(iso)
  throw new Error(`invalid time: ${s}`)
}

export function parseCHTime(s) {
  const str = String(s || '').trim()
  const layouts = [
    /^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})/,
    /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})/,
    /^(\d{4})-(\d{2})-(\d{2})$/,
  ]
  for (const re of layouts) {
    const m = str.match(re)
    if (m) {
      if (m.length >= 7) {
        return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]))
      }
      return new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], 0, 0, 0))
    }
  }
  const t = Date.parse(str)
  if (!Number.isNaN(t)) return new Date(t)
  throw new Error(`invalid clickhouse time: ${s}`)
}

/** Truncate to UTC hour start. */
export function truncateUTCHour(d) {
  return new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), d.getUTCHours(), 0, 0, 0))
}

/** Calendar day shift in UTC (matches Go AddDate for day offsets). */
export function addUTCDays(d, days) {
  return new Date(
    Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate() + days, d.getUTCHours(), d.getUTCMinutes(), d.getUTCSeconds(), d.getUTCMilliseconds()),
  )
}
