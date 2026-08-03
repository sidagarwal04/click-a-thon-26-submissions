// Sessions still open at a watermark, and how much of their counted time is provisional.
// Query text lives in sql/queries/serving/open_sessions.sql.
//
// ON DEMAND, never on the refresh tick. This is the one serving query that reads raw_events
// rather than a delta table, because "which sessions are open" is a question about events. That
// file states the cost; the console honours it by fetching this route only when the viewer opens
// the Open panel, not on the 5-second loop the chart runs on.
import {NextRequest, NextResponse} from 'next/server'
import {chQuery} from '@/lib/clickhouse'
import {resolveDataset} from '@/lib/datasets.server'
import {columnReader, servingSql} from '@/lib/sql'
import {errorResponse} from '@/lib/apiError'
import type {ApiError, OpenSessionsResponse} from '@/lib/types'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

/** Matches the pipeline's gap tolerance. Changing one without the other would make the console
 *  disagree with what the derive actually counted. */
const TOLERANCE_S = 90

/** Page size. The headline counts come from window aggregates over the whole open set, so this
 *  bounds transfer and rendering only, never the numbers. */
const ROW_LIMIT = 100

export async function GET(req: NextRequest): Promise<NextResponse<OpenSessionsResponse | ApiError>> {
  const dataset = resolveDataset(req.nextUrl.searchParams)
  const asOf = req.nextUrl.searchParams.get('as_of')
  if (!asOf) {
    return NextResponse.json({error: 'as_of is required (the watermark to evaluate against)'}, {status: 400})
  }
  const t0 = Date.now()
  try {
    const result = await chQuery(servingSql('open_sessions.sql'), {
      as_of: asOf,
      tolerance_s: TOLERANCE_S,
            row_limit: ROW_LIMIT,
    }, dataset.concurrency)
    const col = columnReader(result.meta)
    const first = result.data[0]
    const body: OpenSessionsResponse = {
      asOf,
      toleranceSeconds: TOLERANCE_S,
      // Window aggregates repeat on every row, so the first row carries the totals. No rows means
      // nothing is open, which is a zero rather than a missing answer.
      openSessions: first ? Number(col(first, 'open_sessions')) : 0,
      provisionalSecondsTotal: first ? Number(col(first, 'provisional_seconds_total')) : 0,
      openWithBackground: first ? Number(col(first, 'open_with_background')) : 0,
      rows: result.data.map((row) => ({
        videoSessionId: String(col(row, 'video_session_id')),
        platform: String(col(row, 'platform')),
        country: String(col(row, 'country')),
        contentId: Number(col(row, 'content_id')),
        lastEvent: String(col(row, 'last_event')),
        countedUntil: String(col(row, 'counted_until')),
        provisionalSeconds: Number(col(row, 'provisional_seconds')),
        backgrounds: Number(col(row, 'backgrounds')),
      })),
      ms: Date.now() - t0,
      rowsRead: result.statistics?.rows_read ?? 0,
    }
    return NextResponse.json(body)
  } catch (e) {
    return errorResponse('app/api/open-sessions/route.ts', e)
  }
}
