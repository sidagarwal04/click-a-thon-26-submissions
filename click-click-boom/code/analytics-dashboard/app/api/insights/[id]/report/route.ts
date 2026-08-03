import { NextRequest, NextResponse } from 'next/server';
import { getInsightReport } from '@/lib/clickhouse';

// Serves the agent-authored HTML report as a real text/html response (not JSON) —
// the [id]/page.tsx viewer loads this in an iframe via `src`, so the report's own
// <style> tags stay scoped to it instead of leaking into (or being overridden by)
// the dashboard's own styles.
export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    const html = await getInsightReport(id);
    if (!html) {
      return new NextResponse('<p>No report available for this insight.</p>', {
        status: 404,
        headers: { 'Content-Type': 'text/html' },
      });
    }
    return new NextResponse(html, {
      headers: { 'Content-Type': 'text/html; charset=utf-8' },
    });
  } catch (error) {
    console.error('Failed to fetch insight report:', error);
    return new NextResponse('<p>Failed to load report.</p>', {
      status: 500,
      headers: { 'Content-Type': 'text/html' },
    });
  }
}
