/**
 * Display formatting for timestamps, IST everywhere the viewer can see one.
 *
 * ClickHouse hands back "YYYY-MM-DD HH:mm:ss" in UTC (session_timezone=UTC is pinned on every
 * request), which is the right wire format and the wrong thing to put on screen for an audience
 * that reasons in IST. Everything below converts for DISPLAY ONLY: the window the UI sends back
 * to the API is still built from the raw UTC strings, so nothing here can shift a query.
 *
 * Intl with an explicit timeZone rather than the browser's local zone: the number on screen
 * must not depend on where the laptop showing it happens to be.
 */
const IST = 'Asia/Kolkata'

/** "2026-08-01 21:18:52" (UTC) -> Date. */
function toUtcDate(chTimestamp: string): Date {
  return new Date(`${chTimestamp.replace(' ', 'T')}Z`)
}

const dateTime = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST,
  day: '2-digit',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: true,
})

const timeOnly = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST,
  hour: '2-digit',
  minute: '2-digit',
  hour12: true,
})

/** "01 Aug, 09:18 pm". For headline readouts where the day matters. */
export function istDateTime(chTimestamp: string | null | undefined): string {
  if (!chTimestamp) return 'n/a'
  return dateTime.format(toUtcDate(chTimestamp)).replace(' at ', ', ')
}

/** "09:18 pm". For dense axis ticks and tooltips, where the day is already established. */
export function istTime(chTimestamp: string | null | undefined): string {
  if (!chTimestamp) return 'n/a'
  return timeOnly.format(toUtcDate(chTimestamp))
}

const dateOnly = new Intl.DateTimeFormat('en-IN', {
  timeZone: IST,
  day: '2-digit',
  month: 'short',
})

/** "01 Aug". For day-grain axis ticks, where a time-of-day would read 12:00 am on every one. */
export function istDate(chTimestamp: string | null | undefined): string {
  if (!chTimestamp) return 'n/a'
  return dateOnly.format(toUtcDate(chTimestamp))
}

/** datetime-local input value ("YYYY-MM-DDTHH:mm") in IST wall-clock terms, and back. The picker
 *  is unlabelled-local by nature, so both directions go through IST to keep what the viewer types
 *  consistent with what every other timestamp on the page shows. */
const IST_OFFSET_MS = 5.5 * 3_600_000

export function utcToIstInput(chTimestamp: string): string {
  return new Date(toUtcDate(chTimestamp).getTime() + IST_OFFSET_MS).toISOString().slice(0, 16)
}

export function istInputToUtc(inputValue: string): string {
  const asIfUtc = new Date(`${inputValue}:00Z`).getTime()
  return new Date(asIfUtc - IST_OFFSET_MS).toISOString().slice(0, 19).replace('T', ' ')
}
