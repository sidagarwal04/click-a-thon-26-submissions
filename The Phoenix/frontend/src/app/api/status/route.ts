// What the pipeline has ingested: drives the console's live indicator and the dashboard's
// default time window. Query text lives in sql/queries/serving/ingest_status.sql, which
// explains why this route reports the live watermark and the frozen-corpus bounds separately.
import {NextRequest, NextResponse} from 'next/server'
import {chQuery} from '@/lib/clickhouse'
import {resolveDataset} from '@/lib/datasets.server'
import {columnReader, servingSql} from '@/lib/sql'
import {errorResponse} from '@/lib/apiError'
import type {ApiError, StatusResponse} from '@/lib/types'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest): Promise<NextResponse<StatusResponse | ApiError>> {
  const dataset = resolveDataset(req.nextUrl.searchParams)
  const t0 = Date.now()
  try {
    const result = await chQuery(servingSql('ingest_status.sql'), {}, dataset.concurrency)
    const row = result.data[0]
    if (!row) throw new Error('ingest_status.sql returned no rows')
    const col = columnReader(result.meta)
    const str = (name: string): string | null => {
      const v = col(row, name)
      return v != null ? String(v) : null
    }
    const body: StatusResponse = {
      events: Number(col(row, 'events') ?? 0),
      latestEvent: str('latest_event'),
      frozenEarliest: str('frozen_earliest'),
      frozenLatest: str('frozen_latest'),
      dataset: dataset.id,
      sessionRuns: Number(col(row, 'session_runs') ?? 0),
      sessionDeltas: Number(col(row, 'session_deltas') ?? 0),
      userRuns: Number(col(row, 'user_runs') ?? 0),
      userDeltas: Number(col(row, 'user_deltas') ?? 0),
      ms: Date.now() - t0,
    }
    return NextResponse.json(body)
  } catch (e) {
    return errorResponse('app/api/status/route.ts', e)
  }
}
