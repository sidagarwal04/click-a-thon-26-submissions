import { createClient } from '@clickhouse/client';
import type { Insight, ContextVersion, ContextSection, SchemaProposal, SchemaReview, TestRun } from './types';

const client = createClient({
  url: process.env.CLICKHOUSE_HOST || 'https://your-instance.clickhouse.cloud:8443',
  username: process.env.CLICKHOUSE_USER || 'default',
  password: process.env.CLICKHOUSE_PASSWORD || '',
  database: 'agent_meta',
});

export async function getInsights(limit = 50): Promise<Insight[]> {
  const result = await client.query({
    query: `
      SELECT
        insight_id,
        spec_name,
        title,
        summary,
        confidence,
        evidence,
        related_known_issues,
        segment_cuts,
        length(report_html) > 0 as has_report,
        formatDateTime(ts, '%Y-%m-%d %H:%i:%s') as created_at,
        trace_url,
        prompt
      FROM agent_meta.insights
      ORDER BY ts DESC
      LIMIT ${limit}
    `,
    format: 'JSONEachRow',
  });

  const data = await result.json<Insight>();
  return data;
}

// Full standalone HTML report for one insight — kept out of getInsights' list
// query (which only needs has_report) since report_html can be tens of KB.
export async function getInsightReport(insightId: string): Promise<string | null> {
  const result = await client.query({
    query: `
      SELECT report_html
      FROM agent_meta.insights
      WHERE insight_id = {id:String}
      ORDER BY ts DESC
      LIMIT 1
    `,
    query_params: { id: insightId },
    format: 'JSONEachRow',
  });
  const rows = await result.json<{ report_html: string }>();
  return rows[0]?.report_html || null;
}

// The changelog: every chronicle/seed write to the context layer, newest
// first. `before` is '' for a pure addition, non-empty when this write
// corrected an earlier claim -- that's the real "contradiction" signal, no
// separate flagging mechanism needed (see agent_meta_ddl.sql's
// context_versions comment).
export async function getContextVersions(limit = 200, section?: string): Promise<ContextVersion[]> {
  const result = await client.query({
    query: `
      SELECT
        version_id, section, before, after, diff_summary, rationale, trigger, confidence,
        formatDateTime(ts, '%Y-%m-%d %H:%i:%s') as created_at,
        trace_url
      FROM agent_meta.context_versions
      ${section ? 'WHERE section = {section:String}' : ''}
      ORDER BY ts DESC
      LIMIT ${limit}
    `,
    query_params: section ? { section } : undefined,
    format: 'JSONEachRow',
  });

  return result.json<ContextVersion>();
}

// The current state of the context layer: one row per section, the latest
// write (argMax'd by ts) -- what the analytics/proposer/reviewer agents
// actually read via list_context_sections/lookup_context (see
// mcp_servers/context_server.py). This is the view, not context_versions
// itself, specifically so the dashboard shows exactly what the agents see.
export async function getCurrentContext(): Promise<ContextSection[]> {
  const result = await client.query({
    query: `
      SELECT section, content, confidence, trace_url,
        formatDateTime(last_updated, '%Y-%m-%d %H:%i:%s') as last_updated
      FROM agent_meta.current_context
      ORDER BY section
    `,
    format: 'JSONEachRow',
  });

  return result.json<ContextSection>();
}

export async function getSchemaProposals(limit = 50): Promise<SchemaProposal[]> {
  const result = await client.query({
    query: `
      SELECT
        proposal_id,
        spec_name as spec_id,
        '' as agent_run_id,
        ddl as proposed_ddl,
        rationale as ordering_key_rationale,
        arrayStringConcat(materialized_views, '\n\n') as materialized_views,
        perf_report as performance_report,
        confidence as confidence_score,
        status,
        revision as revision_number,
        formatDateTime(ts, '%Y-%m-%d %H:%i:%s') as created_at,
        trace_url
      FROM agent_meta.schema_proposals
      ORDER BY ts DESC
      LIMIT ${limit}
    `,
    format: 'JSONEachRow',
  });

  const data = await result.json<SchemaProposal[]>();
  return data;
}

export async function getSchemaReviews(proposalId?: string): Promise<SchemaReview[]> {
  const whereClause = proposalId ? `WHERE proposal_id = '${proposalId}'` : '';

  const result = await client.query({
    query: `
      SELECT
        review_id,
        proposal_id,
        '' as reviewer_agent,
        verdict,
        findings,
        formatDateTime(ts, '%Y-%m-%d %H:%i:%s') as reviewed_at,
        trace_url
      FROM agent_meta.schema_reviews
      ${whereClause}
      ORDER BY ts DESC
      LIMIT 100
    `,
    format: 'JSONEachRow',
  });

  const data = await result.json<SchemaReview[]>();
  return data;
}

export async function getTestRuns(proposalId?: string): Promise<TestRun[]> {
  const whereClause = proposalId ? `WHERE proposal_id = '${proposalId}'` : '';

  const result = await client.query({
    query: `
      SELECT
        run_id,
        proposal_id,
        test_id as test_case_id,
        IF(passed = 1, 'passed', 'failed') as status,
        actual as error_message,
        duration_ms as execution_time_ms,
        formatDateTime(ts, '%Y-%m-%d %H:%i:%s') as executed_at
      FROM agent_meta.test_runs
      ${whereClause}
      ORDER BY ts DESC
      LIMIT 100
    `,
    format: 'JSONEachRow',
  });

  const data = await result.json<TestRun[]>();
  return data;
}

export async function getInsightStats() {
  const result = await client.query({
    query: `
      SELECT
        count() as total_insights,
        avg(confidence) as avg_confidence,
        countIf(confidence >= 0.8) as high_confidence_count,
        countIf(confidence < 0.6) as low_confidence_count
      FROM agent_meta.insights
    `,
    format: 'JSONEachRow',
  });

  const data = await result.json<any[]>();
  return data[0] || {};
}
