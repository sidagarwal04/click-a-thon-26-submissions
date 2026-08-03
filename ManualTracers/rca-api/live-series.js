/**
 * Proxies chart series to the RCA agent's FastAPI process (docs/RCA_UI_TEMPLATE.md Step
 * 3), so real reproduce_global / segment deviation SQL backs the charts instead of
 * mock-series.js's synthetic data. Reshapes the agent's generic response into the exact
 * field names rca-ui's chart components already expect (GlobalMetricChart wants
 * bucket/actual/expected/z_score; SegmentTrendChart is hardcoded to os_version/fill_rate)
 * so neither component needs to change.
 *
 * Returns null — never throws — when RCA_AGENT_URL isn't set or the agent isn't reachable,
 * so callers can fall straight back to the mock generator. Uses Node's built-in fetch
 * (18+): no new dependency for a Node 22 image.
 */
const { bucketKey } = require("./mock-series");

const AGENT_URL = process.env.RCA_AGENT_URL; // e.g. http://localhost:8000 or http://rca-agent:8000

async function fetchGlobalSeries(report, filters) {
  if (!AGENT_URL) return null;
  const res = await fetch(`${AGENT_URL}/internal/global-series`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      metric_id: report.trigger.metric_id,
      start: new Date(filters.from).toISOString(),
      end: new Date(filters.to).toISOString(),
    }),
  });
  if (!res.ok) throw new Error(`agent global-series returned ${res.status}`);
  const rows = await res.json();
  return rows.map((r) => ({
    bucket: bucketKey(r.ts, filters.granularity),
    actual: r.actual,
    expected: r.expected,
    z_score: r.z_score,
  }));
}

async function fetchSegmentSeries(report, filters) {
  if (!AGENT_URL) return null;
  const dimName = report.trigger.dimension_hint || report.candidates?.[0]?.dim_name;
  if (!dimName) return null;

  const res = await fetch(`${AGENT_URL}/internal/segment-series`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({
      metric_id: report.trigger.metric_id,
      dim_name: dimName,
      dim_values: filters.os_versions.length > 0 ? filters.os_versions : undefined,
      start: new Date(filters.from).toISOString(),
      end: new Date(filters.to).toISOString(),
    }),
  });
  if (!res.ok) throw new Error(`agent segment-series returned ${res.status}`);
  const rows = await res.json();
  return rows.map((r) => ({
    bucket: bucketKey(r.ts, filters.granularity),
    os_version: r.dim_value,
    fill_rate: r.actual,
    expected: r.expected,
  }));
}

module.exports = { fetchGlobalSeries, fetchSegmentSeries };
