// Filter values for the v2 rail, read out of phoenix_next.
//
// REUSES sql/queries/serving/dimension_values.sql rather than adding an insight-layer copy. That
// file already emits the value/label pair the rail needs, already resolves content_id to its
// title, and already reads concurrency_deltas, which exists in both databases. A second copy
// pointed at the same tables would be a number waiting to go stale, which is the whole reason
// lib/sql.ts exists.
//
// The only difference from the v1 route is the database, which is now an argument rather than an
// environment default.
import {NextRequest, NextResponse} from 'next/server'
import {chQuery} from '@/lib/clickhouse'
import {resolveDataset} from '@/lib/datasets.server'
import {columnReader, servingSql} from '@/lib/sql'
import {errorResponse} from '@/lib/apiError'
import type {ApiError, DimensionsResponse} from '@/lib/types'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest): Promise<NextResponse<DimensionsResponse | ApiError>> {
  const dataset = resolveDataset(req.nextUrl.searchParams)
  try {
    const result = await chQuery(
      servingSql('dimension_values.sql'),
      {},
      dataset.insights,
    )
    const col = columnReader(result.meta)
    const values = result.data
      .map((row) => ({
        dim: String(col(row, 'dim')),
        value: String(col(row, 'value')),
        label: String(col(row, 'label')),
      }))
      .filter((v) => v.value !== '') as DimensionsResponse['values']
    return NextResponse.json({values})
  } catch (e) {
    return errorResponse('app/api/v2/dimensions/route.ts', e)
  }
}
