// Distinct filter values for the four dimensions the serving layer is keyed on.
// Query text lives in sql/queries/serving/dimension_values.sql.
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
    const result = await chQuery(servingSql('dimension_values.sql'), {}, dataset.concurrency)
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
    return errorResponse('app/api/dimensions/route.ts', e)
  }
}
