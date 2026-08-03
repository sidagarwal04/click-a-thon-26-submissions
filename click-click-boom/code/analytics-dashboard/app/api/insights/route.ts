import { NextResponse } from 'next/server';
import { getInsights } from '@/lib/clickhouse';

export async function GET() {
  try {
    const insights = await getInsights(50);
    return NextResponse.json(insights);
  } catch (error) {
    console.error('Failed to fetch insights:', error);
    return NextResponse.json(
      { error: 'Failed to fetch insights' },
      { status: 500 }
    );
  }
}
