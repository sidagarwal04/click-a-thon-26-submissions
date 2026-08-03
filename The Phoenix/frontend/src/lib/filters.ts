import {PublicError} from './apiError'
import type {Filters} from './types'

/**
 * Parses the shared filter contract off a request's search params. Every dimension defaults to
 * '' (no filter) and content_id defaults to 0 (no filter) to match the {x:String}='' OR ...
 * pattern the SQL files use. from_ts/to_ts default to a wide-open bound: in practice the UI
 * always sends explicit bounds derived from /api/status's `latest`, so this default is only a
 * safety net for direct API calls, not a path the dashboard itself takes.
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

export function parseFilters(searchParams: URLSearchParams): Filters {
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
