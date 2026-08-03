// How far each insight table has been derived, against how far the raw stream has got.
// Query text lives in sql/insights/benchmark/insight_status.sql.
//
// This route exists because the insight layer is refreshed by a job rather than by ingest, so it
// lags, and the lag is not small: measured 2026-07-26 11:31 against a raw watermark of
// 2026-08-01 20:06. A console that showed those insight numbers without showing that gap would be
// presenting six-day-old data as current, which is the single most misleading thing this UI could
// do. The header renders the gap, so staleness is a number on screen rather than an assumption.
import {NextRequest, NextResponse} from 'next/server'
import {insightQuery, insightSql} from '@/lib/insights'
import {resolveDataset} from '@/lib/datasets.server'
import {columnReader} from '@/lib/sql'
import {errorResponse} from '@/lib/apiError'
import type {ApiError, InsightStatusResponse} from '@/lib/types'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest): Promise<NextResponse<InsightStatusResponse | ApiError>> {
  const dataset = resolveDataset(req.nextUrl.searchParams)
  const t0 = Date.now()
  try {
    const result = await insightQuery(insightSql('insight_status.sql'), {}, dataset.insights)
    const row = result.data[0]
    if (!row) throw new Error('insight_status.sql returned no rows')
    const col = columnReader(result.meta)
    const str = (name: string): string | null => {
      const v = col(row, name)
      return v != null ? String(v) : null
    }
    const num = (name: string): number => Number(col(row, name) ?? 0)

    return NextResponse.json({
      database: dataset.insights,
      rawLatest: str('raw_latest'),
      rawEvents: num('raw_events'),
      factsLatest: str('facts_latest'),
      factsSessions: num('facts_sessions'),
      snapshotLatest: str('snapshot_latest'),
      snapshotMinutes: num('snapshot_minutes'),
      transitionsLatest: str('transitions_latest'),
      transitionsAsserted: num('transitions_asserted'),
      healthLatest: str('health_latest'),
      cohortsLatest: str('cohorts_latest'),
      spikeEvents: num('spike_events'),
      lateEvents: num('late_events'),
      ms: Date.now() - t0,
    })
  } catch (e) {
    return errorResponse('app/api/v2/status/route.ts', e)
  }
}
