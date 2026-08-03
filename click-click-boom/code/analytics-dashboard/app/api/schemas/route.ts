import { NextResponse } from 'next/server';
import { createClient } from '@clickhouse/client';

const client = createClient({
  url:      process.env.CLICKHOUSE_HOST || '',
  username: process.env.CLICKHOUSE_USER || 'default',
  password: process.env.CLICKHOUSE_PASSWORD || '',
  database: 'agent_meta',
});

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    // Query 1: all tables + MVs in the atlys db, excluding internal MV backing tables
    const tablesRes = await client.query({
      query: `
        SELECT
          name                                                                   AS table_name,
          engine,
          sorting_key                                                            AS ordering_key,
          create_table_query                                                     AS ddl,
          formatDateTime(metadata_modification_time, '%Y-%m-%d %H:%i:%s')       AS created_at
        FROM system.tables
        WHERE database = 'atlys'
          AND name NOT LIKE '.inner%'
        ORDER BY engine DESC, metadata_modification_time DESC
      `,
      format: 'JSONEachRow',
    });
    const tables = await tablesRes.json<Record<string, any>>();

    // Query 2: latest proposal per spec from agent_meta (best-effort enrichment)
    const proposalsRes = await client.query({
      query: `
        SELECT
          argMax(proposal_id, ts)                                               AS proposal_id,
          argMax(table_name,  ts)                                               AS table_name,
          spec_name,
          argMax(status,      ts)                                               AS status,
          round(argMax(confidence, ts), 3)                                      AS confidence,
          argMax(rationale,   ts)                                               AS rationale,
          argMax(trace_url,   ts)                                               AS trace_url,
          arrayStringConcat(argMax(materialized_views, ts), '\n\n')             AS materialized_views
        FROM agent_meta.schema_proposals
        GROUP BY spec_name
      `,
      format: 'JSONEachRow',
    });
    const proposals = await proposalsRes.json<Record<string, any>>();

    // Index proposals by table_name for O(1) merge
    const byTable = Object.fromEntries(proposals.map(p => [p.table_name, p]));

    const merged = tables.map(t => ({
      table_name:         t.table_name,
      engine:             t.engine,
      ordering_key:       t.ordering_key ?? '',
      ddl:                t.ddl ?? '',
      created_at:         t.created_at,
      proposal_id:        byTable[t.table_name]?.proposal_id   ?? '',
      spec_name:          byTable[t.table_name]?.spec_name     ?? '',
      status:             byTable[t.table_name]?.status        ?? '',
      confidence:         byTable[t.table_name]?.confidence    ?? 0,
      rationale:          byTable[t.table_name]?.rationale     ?? '',
      trace_url:          byTable[t.table_name]?.trace_url     ?? '',
      materialized_views: byTable[t.table_name]?.materialized_views ?? '',
    }));

    return NextResponse.json(merged);
  } catch (e) {
    console.error('Failed to fetch schemas:', e);
    return NextResponse.json([], { status: 200 });
  }
}
