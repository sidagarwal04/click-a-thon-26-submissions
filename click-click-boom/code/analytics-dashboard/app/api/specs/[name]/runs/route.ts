import { NextRequest, NextResponse } from 'next/server';
import { createClient } from '@clickhouse/client';

const client = createClient({
  url:      process.env.CLICKHOUSE_HOST || '',
  username: process.env.CLICKHOUSE_USER || 'default',
  password: process.env.CLICKHOUSE_PASSWORD || '',
  database: 'agent_meta',
});

export const dynamic = 'force-dynamic';

export async function GET(
  _req: NextRequest,
  { params }: { params: Promise<{ name: string }> }
) {
  const { name: spec } = await params;
  try {
    // Latest proposal per revision (append-only, take argMax per proposal_id)
    const proposals = await client.query({
      query: `
        SELECT
          proposal_id,
          argMax(revision, ts)    AS revision,
          argMax(status, ts)      AS status,
          round(argMax(confidence, ts), 3) AS confidence,
          argMax(table_name, ts)  AS table_name,
          argMax(ordering_key, ts) AS ordering_key,
          argMax(rationale, ts)   AS rationale,
          argMax(perf_report, ts) AS perf_report,
          argMax(ddl, ts)         AS ddl,
          argMax(trace_url, ts)   AS trace_url,
          formatDateTime(max(ts), '%Y-%m-%d %H:%i:%s') AS last_updated
        FROM agent_meta.schema_proposals
        WHERE spec_name = {spec:String}
        GROUP BY proposal_id
        ORDER BY max(ts) DESC
        LIMIT 30
      `,
      query_params: { spec },
      format: 'JSONEachRow',
    });
    const proposalRows = await proposals.json<Record<string, unknown>[]>();

    // Reviews for these proposals
    const ids = proposalRows.map(r => String(r.proposal_id));
    let reviewRows: Record<string, unknown>[] = [];
    if (ids.length > 0) {
      const idList = ids.map(id => `'${id}'`).join(',');
      const reviews = await client.query({
        query: `
          SELECT
            review_id, proposal_id, verdict,
            findings, reviewer_confidence, trace_url,
            formatDateTime(ts, '%Y-%m-%d %H:%i:%s') AS ts
          FROM agent_meta.schema_reviews
          WHERE proposal_id IN (${idList})
          ORDER BY ts DESC
        `,
        format: 'JSONEachRow',
      });
      reviewRows = await reviews.json<Record<string, unknown>[]>();
    }

    // Insight for this spec
    const insightRes = await client.query({
      query: `
        SELECT insight_id, title, summary, confidence,
               length(report_html) > 0 AS has_report, trace_url,
               formatDateTime(ts, '%Y-%m-%d %H:%i:%s') AS ts
        FROM agent_meta.insights
        WHERE spec_name = {spec:String}
        ORDER BY ts DESC
        LIMIT 1
      `,
      query_params: { spec },
      format: 'JSONEachRow',
    });
    const insights = await insightRes.json<Record<string, unknown>[]>();

    return NextResponse.json({
      proposals: proposalRows,
      reviews:   reviewRows,
      insight:   insights[0] ?? null,
    });
  } catch (e) {
    console.error(e);
    return NextResponse.json({ proposals: [], reviews: [], insight: null });
  }
}
