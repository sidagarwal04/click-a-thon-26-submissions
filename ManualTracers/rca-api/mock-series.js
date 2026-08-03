/**
 * Synthetic hourly series for RCA charts — shaped like reproduce_global output.
 * Filters slice rows by [from, to] and optional os_version.
 */

function parseFilters(body) {
  const from = body.from;
  const to = body.to;
  if (!from || !to) throw new Error("from and to are required");
  return {
    from: new Date(from).getTime(),
    to: new Date(to).getTime(),
    os_versions: Array.isArray(body.os_versions) ? body.os_versions : [],
    granularity: body.granularity === "day" ? "day" : "hour",
  };
}

function inRange(ts, from, to) {
  const t = new Date(ts).getTime();
  return t >= from && t <= to;
}

function bucketKey(ts, granularity) {
  if (granularity === "day") return ts.slice(0, 10);
  return ts.slice(0, 13) + ":00:00";
}

/** Global fill rate: baseline ~0.785, dip during incident window */
function globalMetricSeries(reportId, filters) {
  const start = reportId.includes("android")
    ? "2026-06-20T00:00:00"
    : "2026-06-27T00:00:00";
  const dipStart = reportId.includes("android") ? 23 : 48;
  const dipEnd = reportId.includes("android") ? 95 : 71;
  const rows = [];
  for (let h = 0; h < 168; h++) {
    const d = new Date(start);
    d.setHours(d.getHours() + h);
    const ts = d.toISOString().slice(0, 19);
    if (!inRange(ts, filters.from, filters.to)) continue;
    const inDip = h >= dipStart && h <= dipEnd;
    const expected = 0.785;
    const actual = inDip ? 0.75 + Math.sin(h / 4) * 0.008 : expected + Math.sin(h / 6) * 0.004;
    rows.push({
      bucket: bucketKey(ts, filters.granularity),
      ts,
      actual: Number(actual.toFixed(4)),
      expected: Number(expected.toFixed(4)),
      z_score: inDip ? 8 + Math.abs(Math.sin(h)) * 3 : 0.5 + Math.random() * 0.8,
    });
  }
  return aggregateByBucket(rows, filters.granularity);
}

/** Segment fill rate: culprit vs rest */
function segmentSeries(reportId, filters) {
  const culprit = reportId.includes("android") ? "Android 15" : "iOS 18.1";
  const start = reportId.includes("android")
    ? "2026-06-20T00:00:00"
    : "2026-06-27T00:00:00";
  const osFilter = filters.os_versions;
  const segments =
    osFilter.length > 0
      ? osFilter
      : [culprit, reportId.includes("android") ? "Android 14" : "iOS 17.5"];

  const rows = [];
  for (let h = 0; h < 168; h++) {
    const d = new Date(start);
    d.setHours(d.getHours() + h);
    const ts = d.toISOString().slice(0, 19);
    if (!inRange(ts, filters.from, filters.to)) continue;
    const inDip = reportId.includes("android")
      ? h >= 23 && h <= 95
      : h >= 48 && h <= 71;

    for (const os of segments) {
      const isCulprit = os === culprit;
      const expected = isCulprit ? 0.745 : 0.785;
      const actual = isCulprit && inDip ? 0.43 + Math.sin(h / 5) * 0.02 : expected + Math.sin(h / 7) * 0.003;
      rows.push({
        bucket: bucketKey(ts, filters.granularity),
        ts,
        os_version: os,
        fill_rate: Number(actual.toFixed(4)),
        expected: Number(expected.toFixed(4)),
      });
    }
  }
  return aggregateSegment(rows, filters.granularity);
}

function aggregateByBucket(rows, granularity) {
  if (granularity === "hour") return rows;
  const map = new Map();
  for (const r of rows) {
    const k = r.bucket;
    if (!map.has(k)) map.set(k, { bucket: k, actual: [], expected: [], z_score: [] });
    const m = map.get(k);
    m.actual.push(r.actual);
    m.expected.push(r.expected);
    m.z_score.push(r.z_score);
  }
  return [...map.values()].map((m) => ({
    bucket: m.bucket,
    actual: avg(m.actual),
    expected: avg(m.expected),
    z_score: Math.max(...m.z_score),
  }));
}

function aggregateSegment(rows, granularity) {
  if (granularity === "hour") return rows;
  const map = new Map();
  for (const r of rows) {
    const k = `${r.bucket}|${r.os_version}`;
    if (!map.has(k)) map.set(k, { bucket: r.bucket, os_version: r.os_version, fill_rate: [], expected: [] });
    const m = map.get(k);
    m.fill_rate.push(r.fill_rate);
    m.expected.push(r.expected);
  }
  return [...map.values()].map((m) => ({
    bucket: m.bucket,
    os_version: m.os_version,
    fill_rate: avg(m.fill_rate),
    expected: avg(m.expected),
  }));
}

function avg(arr) {
  return Number((arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(4));
}

/** Contribution bars for candidate ranking */
function contributionBars(report) {
  return report.candidates.map((c) => ({
    segment: `${c.dim_name}=${c.dim_value}`,
    contribution: c.contribution,
    peak_abs_z: c.peak_abs_z,
    avg_actual: c.avg_actual,
    avg_expected: c.avg_expected,
  }));
}

module.exports = {
  parseFilters,
  globalMetricSeries,
  segmentSeries,
  contributionBars,
  // exported so live-series.js can bucket + roll up real rows the same way as the mock path
  bucketKey,
  aggregateByBucket,
  aggregateSegment,
};
