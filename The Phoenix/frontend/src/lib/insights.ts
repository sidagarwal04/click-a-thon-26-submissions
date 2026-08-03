// The v2 insight console's data access: which database it reads, where its query text lives, and
// the one filter contract every insight query takes.
//
// SEPARATE FROM lib/sql.ts ON PURPOSE, mirroring the split scripts/init_insights.sh already makes
// between sql/schema/ and sql/insights/schema/. The concurrency engine and the insight layer have
// different lifecycles and different blast radii: v1 must keep serving `phoenix` unchanged no
// matter what happens here, and a shared loader would make one directory's failure the other's.
import fs from 'node:fs'
import path from 'node:path'
import {chQuery} from './clickhouse'
import {PublicError} from './apiError'
import type {Filters} from './types'

/** The insight layer lives only here. `phoenix` has none of these tables. */
export const INSIGHT_DATABASE = process.env.CH_INSIGHT_DATABASE || 'phoenix_next'

const INSIGHT_DIR = path.join(process.cwd(), '..', 'sql', 'insights', 'benchmark')

// Read once per file per process, the same contract as lib/sql.ts: a changed .sql file is picked
// up by a restart rather than mid-session, so the numbers on screen cannot change without the
// process that reported them changing too.
const cache = new Map<string, string>()

/** Reads a query from sql/insights/benchmark/ by filename, e.g. insightSql('state_flow.sql'). */
export function insightSql(name: string): string {
  const cached = cache.get(name)
  if (cached !== undefined) return cached
  let text: string
  try {
    text = fs.readFileSync(path.join(INSIGHT_DIR, name), 'utf8')
  } catch (cause) {
    throw new Error(
      `cannot read sql/insights/benchmark/${name}. This app reads shipped query text from the ` +
        `repo checkout; run it from the frontend/ directory inside the repo. (${(cause as Error).message})`,
    )
  }
  cache.set(name, text)
  return text
}

/**
 * Runs an insight query. The database is a per-CALL argument because the v2 console can be
 * pointed at either generation (lib/datasets.ts); it defaults to the standing insight database
 * so existing callers keep their behaviour.
 */
export function insightQuery<P extends object>(sql: string, params: P, database: string = INSIGHT_DATABASE) {
  return chQuery(sql, params, database)
}

/**
 * Every insight query takes the same seven filters, exactly matching
 * the serving-layer contract in lib/filters.ts. Same defaults, same meaning of '' and 0, so a
 * dimension filter behaves identically on both consoles and a reader comparing them is comparing
 * the data rather than two filter implementations.
 */

/**
 * The widest window a request may ask for.
 *
 * The old defaults were from_ts=2000-01-01 and to_ts=2100-01-01, described in a comment as "a
 * safety net for direct API calls". The wide default WAS the unbounded scan: any caller omitting
 * the window got a hundred-year range, and /api/open-sessions reads raw_events, the one table the
 * serving layer is built to avoid. A ceiling makes the safety net actually a net.
 *
 * 31 days is wider than any window either console offers and cheap enough that an abusive
 * direct call cannot become an outage. Measured: a 92-day clamp still answered in 14.9s
 * because the curve densifies one row per minute with no gaps, so 92 days is 132,480
 * generated minutes. 31 days is 44,640 and answers in about a second.
 */
const MAX_WINDOW_DAYS = 31
const DEFAULT_WINDOW_DAYS = 7

function boundedWindow(searchParams: URLSearchParams): {from_ts: string; to_ts: string} {
  const to = searchParams.get('to')
  const from = searchParams.get('from')
  // Both absent: a recent window, not all of history. Anchored on the caller's clock only in this
  // fallback; the consoles always send explicit bounds derived from the data's own watermark.
  if (!to && !from) {
    const now = new Date()
    const then = new Date(now.getTime() - DEFAULT_WINDOW_DAYS * 86_400_000)
    return {from_ts: chTimestamp(then), to_ts: chTimestamp(now)}
  }
  const toDate = to ? new Date(to.replace(' ', 'T') + 'Z') : new Date()
  const fromDate = from ? new Date(from.replace(' ', 'T') + 'Z') : new Date(0)
  if (Number.isNaN(toDate.getTime()) || Number.isNaN(fromDate.getTime())) {
    throw new PublicError('from and to must be timestamps like 2026-07-31 00:00:00')
  }
  const widest = MAX_WINDOW_DAYS * 86_400_000
  const clampedFrom =
    toDate.getTime() - fromDate.getTime() > widest
      ? new Date(toDate.getTime() - widest)
      : fromDate
  return {from_ts: chTimestamp(clampedFrom), to_ts: chTimestamp(toDate)}
}

function chTimestamp(d: Date): string {
  return d.toISOString().slice(0, 19).replace('T', ' ')
}

export function parseInsightFilters(searchParams: URLSearchParams): Filters {
  const window = boundedWindow(searchParams)
  return {
    platform: searchParams.get('platform') || '',
    country: searchParams.get('country') || '',
    video_type: searchParams.get('video_type') || '',
    app_version: searchParams.get('app_version') || '',
    audio_language: searchParams.get('audio_language') || '',
    subtitle_language: searchParams.get('subtitle_language') || '',
    player_version: searchParams.get('player_version') || '',
    video_resolution: searchParams.get('video_resolution') || '',
    content_id: Number(searchParams.get('content_id') || 0) || 0,
    ...window,
  }
}
