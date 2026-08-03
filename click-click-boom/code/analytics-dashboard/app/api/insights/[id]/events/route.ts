import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@clickhouse/client';

const client = createClient({
  url:      process.env.CLICKHOUSE_HOST || '',
  username: process.env.CLICKHOUSE_USER || 'default',
  password: process.env.CLICKHOUSE_PASSWORD || '',
  database: 'agent_meta',
});

export interface TraceEventRow {
  ts_ms: number;
  trace_id: string;
  trace_url: string;
  agent: string;
  spec_name: string;
  step: string;
  event: string;
  kind: string;
  input: string;
  output: string;
  reasoning: string;
  usage: string;
  metadata: string;
}

export const dynamic = 'force-dynamic';

// Counterpart to /api/specs/[name]/events, but keyed by insight_id rather than
// spec_name -- a spec can now have MULTIPLE insights (analytics is an
// explicit, re-runnable step, see analytics/analytics_agent.py's
// run_analytics_for_spec), so "the latest trace for this spec" is no longer
// enough to find one specific insight's own trace. insights doesn't store
// trace_id directly, only trace_url (the same value every event on that trace
// carries) -- used here as the join key back into trace_events instead of
// adding a column.
export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  try {
    const insightRes = await client.query({
      query: `
        SELECT trace_url FROM agent_meta.insights
        WHERE insight_id = {id:String}
        ORDER BY ts DESC LIMIT 1
      `,
      query_params: { id },
      format: 'JSONEachRow',
    });
    const insightRows = await insightRes.json<{ trace_url: string }>();
    const traceUrl = insightRows[0]?.trace_url;
    if (!traceUrl) {
      return NextResponse.json({ trace_id: null, events: [] });
    }

    const latest = await client.query({
      query: `
        SELECT trace_id FROM agent_meta.trace_events
        WHERE trace_url = {traceUrl:String}
        ORDER BY ts DESC LIMIT 1
      `,
      query_params: { traceUrl },
      format: 'JSONEachRow',
    });
    const latestRows = await latest.json<{ trace_id: string }>();
    const traceId = latestRows[0]?.trace_id;
    if (!traceId) {
      return NextResponse.json({ trace_id: null, events: [] });
    }

    const result = await client.query({
      query: `
        SELECT
          toUnixTimestamp64Milli(ts) AS ts_ms,
          trace_id, trace_url, agent, spec_name, step, event, kind, input, output, reasoning, usage, metadata
        FROM agent_meta.trace_events
        WHERE trace_id = {traceId:String}
        ORDER BY ts ASC
      `,
      query_params: { traceId },
      format: 'JSONEachRow',
    });
    const events = await result.json<TraceEventRow>();
    return NextResponse.json({ trace_id: traceId, events });
  } catch (e) {
    console.error(e);
    return NextResponse.json({ trace_id: null, events: [] }, { status: 200 });
  }
}
