import express from 'express';
import cors from 'cors';
import { logs } from '@opentelemetry/api-logs';
import { runAll, runQuery, client } from './clickhouse.js';
import { overviewQueries, segmentQueries, metaQuery, SEGMENT_DIMENSIONS } from './queries.js';

const app = express();
const logger = logs.getLogger('liv-api');
app.use(cors());
app.use(express.json());

app.use((req, _res, next) => {
  logger.emit({ severityText: 'INFO', body: `${req.method} ${req.path}`, attributes: { path: req.path, query: JSON.stringify(req.query) } });
  next();
});

const asHandler = (fn) => async (req, res) => {
  try {
    res.json(await fn(req));
  } catch (err) {
    console.error(err);
    res.status(500).json({ error: err.message });
  }
};

// Range defaults to whatever is actually in the table, so the UI is never
// empty on first load regardless of what dates the dataset covers.
async function resolveRange(q) {
  if (q.from && q.to) return { from: q.from, to: q.to };
  const { data } = await runQuery('range_default', `
    SELECT
      formatDateTime(min(minute), '%Y-%m-%d %H:%M:%S')                     AS from,
      formatDateTime(max(minute) + INTERVAL 1 MINUTE, '%Y-%m-%d %H:%M:%S') AS to
    FROM conc_minute`);
  return data[0] || {};
}

function filtersFrom(q, range) {
  return {
    from: range.from, to: range.to,
    platform: q.platform || '', country: q.country || '',
    video_type: q.video_type || '', content_id: q.content_id || '',
  };
}

app.get('/api/health', asHandler(async () => {
  await client.ping();
  return { ok: true, service: 'liv-concurrency-api' };
}));

app.get('/api/meta', asHandler(async () => {
  const { data, timings } = await runAll(metaQuery());
  return {
    ...data.meta[0],
    dimensions: Object.entries(SEGMENT_DIMENSIONS).map(([k, v]) => ({ key: k, label: v.label })),
    timings,
  };
}));

app.get('/api/overview', asHandler(async (req) => {
  const range = await resolveRange(req.query);
  const filters = filtersFrom(req.query, range);
  const { data, timings } = await runAll(overviewQueries(filters));
  return {
    range,
    filters,
    summary: data.summary[0] || {},
    reach: data.reach[0] || {},
    timeseries: data.timeseries,
    hourly: data.hourly,
    platformMix: data.platform_mix,
    topContent: data.top_content,
    timings,
  };
}));

app.get('/api/segments', asHandler(async (req) => {
  const range = await resolveRange(req.query);
  const filters = filtersFrom(req.query, range);
  const dimension = req.query.dimension || 'platform';
  const topN = Math.min(20, Number(req.query.top) || 8);
  const { data, timings } = await runAll(segmentQueries(filters, dimension, topN));
  return {
    range, filters, dimension,
    breakdown: data.breakdown,
    series: data.series,
    concentration: data.concentration[0] || {},
    timings,
  };
}));

const port = process.env.API_PORT || 8080;
app.listen(port, () => console.log(`[api] listening on ${port}`));
