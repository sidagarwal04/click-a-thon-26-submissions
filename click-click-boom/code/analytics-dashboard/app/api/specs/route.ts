import { NextResponse } from 'next/server';
import { createClient } from '@clickhouse/client';

const client = createClient({
  url:      process.env.CLICKHOUSE_HOST || '',
  username: process.env.CLICKHOUSE_USER || 'default',
  password: process.env.CLICKHOUSE_PASSWORD || '',
  database: 'agent_meta',
});

export interface SpecSummary {
  spec_name: string;
  latest_status: string;
  latest_confidence: number;
  table_name: string;
  trace_url: string;
  last_run: string;
  total_proposals: number;
  has_insight: number;
  insight_title: string;
}

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const result = await client.query({
      query: `
        SELECT
          p.spec_name,
          argMax(p.status, p.ts)     AS latest_status,
          round(argMax(p.confidence, p.ts), 3) AS latest_confidence,
          argMax(p.table_name, p.ts) AS table_name,
          argMax(p.trace_url, p.ts)  AS trace_url,
          formatDateTime(max(p.ts), '%Y-%m-%d %H:%i:%s') AS last_run,
          count()                    AS total_proposals,
          (SELECT count() FROM agent_meta.insights i WHERE i.spec_name = p.spec_name) AS has_insight,
          (SELECT argMax(title, ts) FROM agent_meta.insights i WHERE i.spec_name = p.spec_name) AS insight_title
        FROM agent_meta.schema_proposals p
        GROUP BY p.spec_name
        ORDER BY max(p.ts) DESC
      `,
      format: 'JSONEachRow',
    });
    const data = await result.json<SpecSummary[]>();
    return NextResponse.json(data);
  } catch (e) {
    console.error(e);
    return NextResponse.json([], { status: 200 });
  }
}
