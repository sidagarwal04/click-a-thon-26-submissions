import { NextResponse } from 'next/server';
import { getInsightStats } from '@/lib/clickhouse';

export async function GET() {
  try {
    const stats = await getInsightStats();
    return NextResponse.json(stats);
  } catch (error) {
    console.error('Failed to fetch stats:', error);
    return NextResponse.json(
      { error: 'Failed to fetch stats' },
      { status: 500 }
    );
  }
}
