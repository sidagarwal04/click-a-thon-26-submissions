import { NextRequest, NextResponse } from 'next/server';
import { getContextVersions } from '@/lib/clickhouse';

export const dynamic = 'force-dynamic';

// The changelog feed -- every chronicle/seed write, newest first. Optional
// ?section=table:foo to scope to one section's own history (used by the
// Context page's detail view).
export async function GET(req: NextRequest) {
  try {
    const section = req.nextUrl.searchParams.get('section') ?? undefined;
    const versions = await getContextVersions(200, section);
    return NextResponse.json(versions);
  } catch (error) {
    console.error('Failed to fetch context versions:', error);
    return NextResponse.json(
      { error: 'Failed to fetch context versions' },
      { status: 500 }
    );
  }
}
