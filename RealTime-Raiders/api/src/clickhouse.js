import { createClient } from '@clickhouse/client';
import { trace, SpanStatusCode } from '@opentelemetry/api';
import { logs } from '@opentelemetry/api-logs';

const tracer = trace.getTracer('liv-clickhouse');
const logger = logs.getLogger('liv-clickhouse');

export const client = createClient({
  url: process.env.CLICKHOUSE_ENDPOINT,
  username: process.env.CLICKHOUSE_USER,
  password: process.env.CLICKHOUSE_PASSWORD,
  database: process.env.CLICKHOUSE_DATABASE || 'liv',
  clickhouse_settings: {
    // The GROUP BY in every KPI query is a sort-key prefix of conc_minute,
    // so ClickHouse can aggregate in order instead of building hash tables.
    optimize_aggregation_in_order: 1,
    max_execution_time: 30,
  },
});

/**
 * Runs a query and returns rows plus the timing that the UI displays.
 *
 * server_ms is ClickHouse's own execution time, taken from the statistics
 * block in the response. That is the number the console shows: it excludes
 * network transit, JSON parsing and every millisecond of React rendering.
 * wall_ms is kept alongside so the gap between them is visible.
 */
export async function runQuery(name, sql, query_params = {}) {
  return tracer.startActiveSpan(`clickhouse.${name}`, async (span) => {
    const started = performance.now();
    try {
      const resultSet = await client.query({ query: sql, query_params, format: 'JSON' });
      const body = await resultSet.json();
      const wall_ms = +(performance.now() - started).toFixed(1);

      const st = body.statistics || {};
      const stats = {
        query: name,
        server_ms: +(((st.elapsed ?? 0) * 1000).toFixed(1)),
        wall_ms,
        rows_read: st.rows_read ?? 0,
        bytes_read: st.bytes_read ?? 0,
        rows_returned: body.rows ?? (body.data || []).length,
      };

      span.setAttributes({
        'db.system': 'clickhouse',
        'db.operation': name,
        'clickhouse.server_ms': stats.server_ms,
        'clickhouse.wall_ms': stats.wall_ms,
        'clickhouse.rows_read': stats.rows_read,
        'clickhouse.bytes_read': stats.bytes_read,
        'clickhouse.rows_returned': stats.rows_returned,
      });

      logger.emit({
        severityText: 'INFO',
        body: `clickhouse query ${name} took ${stats.server_ms}ms server-side`,
        attributes: stats,
      });

      return { data: body.data || [], stats };
    } catch (err) {
      span.recordException(err);
      span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
      logger.emit({
        severityText: 'ERROR',
        body: `clickhouse query ${name} failed: ${err.message}`,
        attributes: { query: name },
      });
      throw err;
    } finally {
      span.end();
    }
  });
}

/** Runs several queries in parallel and collects their timings together. */
export async function runAll(specs) {
  const results = await Promise.all(specs.map((s) => runQuery(s.name, s.sql, s.params)));
  return {
    data: Object.fromEntries(specs.map((s, i) => [s.name, results[i].data])),
    timings: results.map((r) => r.stats),
  };
}
