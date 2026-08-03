// Session-independent concurrency: concurrent USERS, not sessions. Identical shape and
// guarantees to /api/concurrency (see that file's header), reading user_concurrency_deltas
// instead of concurrency_deltas. One person watching on a phone and a TV is two sessions and
// one viewer, which is the divergence Compare mode on the dashboard exists to show.
//
// Query text lives in sql/queries/serving/, not here.
import {NextRequest, NextResponse} from 'next/server'
import {chQuery} from '@/lib/clickhouse'
import {resolveDataset} from '@/lib/datasets.server'
import {parseFilters} from '@/lib/filters'
import {columnReader, servingSql} from '@/lib/sql'
import {errorResponse} from '@/lib/apiError'
import type {ApiError, ConcurrencyResponse} from '@/lib/types'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest): Promise<NextResponse<ConcurrencyResponse | ApiError>> {
  const filters = parseFilters(req.nextUrl.searchParams)
  // Which generation to read. Opaque id in, database name out, allowlist in between.
  const dataset = resolveDataset(req.nextUrl.searchParams)
  const t0 = Date.now()
  try {
    const curveSql = servingSql('user_concurrency_curve.sql')
    const reachSql = servingSql('reach.sql')
    const [curve, reach] = await Promise.all([
      chQuery(curveSql, filters, dataset.concurrency),
      chQuery(reachSql, filters, dataset.concurrency),
    ])

    const col = columnReader(curve.meta)
    const points = curve.data.map(
      (row) => [String(col(row, 'minute')), Number(col(row, 'concurrency'))] as [string, number],
    )
    const last = curve.data[curve.data.length - 1]

    const reachCol = columnReader(reach.meta)
    const usersRow = reach.data.find((row) => String(reachCol(row, 'level')) === 'users')

    const body: ConcurrencyResponse = {
      points,
      peakConcurrency: last ? Number(col(last, 'peak_concurrency')) : 0,
      peakMinute: last ? String(col(last, 'peak_minute')) : '',
      avgConcurrency: last ? Number(col(last, 'avg_all_minutes')) : 0,
      avgActiveMinutes: last ? Number(col(last, 'avg_active_minutes')) : 0,
      minutesWithAudience: last ? Number(col(last, 'minutes_with_audience')) : 0,
      minutesInRange: last ? Number(col(last, 'minutes_in_range')) : 0,
      p95Concurrency: last ? Number(col(last, 'p95_concurrency')) : 0,
      reach: usersRow ? Number(reachCol(usersRow, 'reach')) : 0,
      ms: Date.now() - t0,
      rowsRead: (curve.statistics?.rows_read ?? 0) + (reach.statistics?.rows_read ?? 0),
      sqlFiles: ['sql/queries/serving/user_concurrency_curve.sql', 'sql/queries/serving/reach.sql'],
      sql: [curveSql, reachSql],
      reads: 'user_concurrency_deltas',
      bytesRead: (curve.statistics?.bytes_read ?? 0) + (reach.statistics?.bytes_read ?? 0),
      serverMs: Math.round(((curve.statistics?.elapsed ?? 0) + (reach.statistics?.elapsed ?? 0)) * 1000),
    }
    return NextResponse.json(body)
  } catch (e) {
    return errorResponse('app/api/user-concurrency/route.ts', e)
  }
}
