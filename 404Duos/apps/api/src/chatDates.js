const MONTH_INDEX = {
  jan: 0,
  january: 0,
  feb: 1,
  february: 1,
  mar: 2,
  march: 2,
  apr: 3,
  april: 3,
  may: 4,
  jun: 5,
  june: 5,
  jul: 6,
  july: 6,
  aug: 7,
  august: 7,
  sep: 8,
  sept: 8,
  september: 8,
  oct: 9,
  october: 9,
  nov: 10,
  november: 10,
  dec: 11,
  december: 11,
}

const MONTH_NAME_RE =
  'Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?'

function formatYmd(y, m0, d) {
  if (m0 == null || d < 1 || d > 31 || y < 2000 || y > 2100) return null
  return `${y}-${String(m0 + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
}

export function compareWindowFor(startISO, endISO) {
  const start = new Date(startISO)
  const end = new Date(endISO)
  const ms = Math.max(end.getTime() - start.getTime(), 0)
  const cEnd = new Date(start.getTime() - 1000)
  const cStart = new Date(cEnd.getTime() - ms)
  return {
    start: cStart.toISOString(),
    end: cEnd.toISOString(),
  }
}

export function windowFromDayBounds(startDay, endDay) {
  const start = `${startDay}T00:00:00.000Z`
  const end = `${endDay}T23:59:59.000Z`
  return {
    start,
    end,
    compare: compareWindowFor(start, end),
  }
}

/**
 * Parse "2026-06-21", "21 June 2026", "June 21", "22June", "21/06/2026" → YYYY-MM-DD.
 * When year is omitted, use defaultYear (from live data range).
 */
export function parseOneDayToken(text, defaultYear = null) {
  const q = String(text || '')

  const iso = q.match(/\b(\d{4})-(\d{2})-(\d{2})\b/)
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`

  const dmySlash = q.match(/\b(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{4})\b/)
  if (dmySlash) {
    const d = Number(dmySlash[1])
    const m = Number(dmySlash[2])
    const y = Number(dmySlash[3])
    if (m >= 1 && m <= 12 && d >= 1 && d <= 31) {
      return `${y}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    }
  }

  const dMonthY = q.match(
    new RegExp(
      `\\b(\\d{1,2})(?:st|nd|rd|th)?\\s*(${MONTH_NAME_RE})\\s*,?\\s*(\\d{4})\\b`,
      'i',
    ),
  )
  if (dMonthY) {
    return formatYmd(Number(dMonthY[3]), MONTH_INDEX[dMonthY[2].toLowerCase()], Number(dMonthY[1]))
  }

  const monthDY = q.match(
    new RegExp(
      `\\b(${MONTH_NAME_RE})\\s*(\\d{1,2})(?:st|nd|rd|th)?\\s*,?\\s*(\\d{4})\\b`,
      'i',
    ),
  )
  if (monthDY) {
    return formatYmd(Number(monthDY[3]), MONTH_INDEX[monthDY[1].toLowerCase()], Number(monthDY[2]))
  }

  if (defaultYear != null) {
    const dMonth = q.match(
      new RegExp(`\\b(\\d{1,2})(?:st|nd|rd|th)?\\s*(${MONTH_NAME_RE})\\b`, 'i'),
    )
    if (dMonth) {
      return formatYmd(defaultYear, MONTH_INDEX[dMonth[2].toLowerCase()], Number(dMonth[1]))
    }
    const monthD = q.match(
      new RegExp(`\\b(${MONTH_NAME_RE})\\s*(\\d{1,2})(?:st|nd|rd|th)?\\b`, 'i'),
    )
    if (monthD) {
      return formatYmd(defaultYear, MONTH_INDEX[monthD[1].toLowerCase()], Number(monthD[2]))
    }
  }

  return null
}

/** Parse absolute or relative date hints from the user question. */
export function parseDateWindowFromText(text, defaultYear = null) {
  const q = String(text || '')

  const isoRange = q.match(/(\d{4}-\d{2}-\d{2}).{0,48}?(\d{4}-\d{2}-\d{2})/)
  if (isoRange) {
    return windowFromDayBounds(isoRange[1], isoRange[2])
  }

  const naturalRange = q.match(
    /\b(?:from|between)\s+(.+?)\s+(?:to|and|through|-)\s+(.+?)(?:\?|$)/i,
  )
  if (naturalRange) {
    const a = parseOneDayToken(naturalRange[1], defaultYear)
    const b = parseOneDayToken(naturalRange[2], defaultYear)
    if (a && b) return windowFromDayBounds(a, b)
  }

  const single = parseOneDayToken(q, defaultYear)
  if (single) return windowFromDayBounds(single, single)

  if (/\btoday\b|\bthis day\b|\blast day\b|\byesterday\b/i.test(q)) {
    return { kind: 'day' }
  }
  if (/\bthis week\b|\blast\s*7\s*days\b|\bpast week\b|\blast week\b/i.test(q)) {
    return { kind: 'week' }
  }
  return null
}
