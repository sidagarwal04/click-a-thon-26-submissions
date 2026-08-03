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

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ name: string }> }
) {
  const { name: spec } = await params;
  try {
    // "How was this spec most recently INGESTED" -- scoped to agent='pipeline'
    // specifically, not just the latest trace_id for this spec_name overall.
    // analytics_agent.run_analytics_for_spec (the dashboard's "Create Insight"
    // button) now opens its OWN traced_run(agent="analytics", ...) as a
    // separate, later, explicit step (see orchestrator/pipeline.py's
    // ingest_spec docstring) -- without this filter, running analytics on a
    // spec made its analytics trace the newest one for that spec_name, which
    // silently replaced the ingestion trace (propose/review/execute) in the
    // Specs list's history panel with the unrelated analytics trace instead.
    const latest = await client.query({
      query: `
        SELECT trace_id FROM agent_meta.trace_events
        WHERE spec_name = {spec:String} AND agent = 'pipeline'
        ORDER BY ts DESC LIMIT 1
      `,
      query_params: { spec },
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
