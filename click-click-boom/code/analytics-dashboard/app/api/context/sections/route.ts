import { NextResponse } from 'next/server';
import { getCurrentContext } from '@/lib/clickhouse';

export const dynamic = 'force-dynamic';

// The current knowledge state -- one row per section, exactly what the
// proposer/reviewer/analytics agents read live via list_context_sections/
// lookup_context (agent_meta.current_context, see mcp_servers/context_server.py).
export async function GET() {
  try {
    const sections = await getCurrentContext();
    return NextResponse.json(sections);
  } catch (error) {
    console.error('Failed to fetch current context:', error);
    return NextResponse.json(
      { error: 'Failed to fetch current context' },
      { status: 500 }
    );
  }
}
