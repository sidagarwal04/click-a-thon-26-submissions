// Proves two things before committing to the registry-driven redesign:
// 1. Schema introspection actually discovers the right candidates.
// 2. The dynamically-generated SQL produces numerically identical results
//    to the hand-written static query it's meant to replace.
// Run: npm run prototype:registry (needs .env.local)
import { getClient, queryJson } from "../lib/clickhouse.js";
import { buildRatioTrendSeasonalSelect } from "../lib/registry/buildSql.js";
import { getPool } from "../lib/registry/db.js";
import { discoverDimensions, discoverRawMeasures, syncDiscoveredDimensions } from "../lib/registry/introspect.js";
import { getMetricDefinitions } from "../lib/registry/repo.js";

async function main() {
  const ch = getClient();

  console.log("=== 1. Schema introspection ===");
  const measures = await discoverRawMeasures(ch, "inmobi", "metrics_hourly");
  console.log(`Discovered ${measures.length} candidate raw measures on metrics_hourly:`);
  for (const m of measures) console.log(`  ${m.table}.${m.column} (${m.type})`);

  const dims = await discoverDimensions(ch, "inmobi", "ad_events", ["apps", "geo_device", "advertisers"]);
  console.log(`\nDiscovered ${dims.length} candidate dimensions:`);
  for (const d of dims) {
    console.log(`  ${d.table}.${d.column} (join key: ${d.joinKey ?? "none — lives on ad_events"})`);
  }
  const currentlySwept = new Set([
    "ad_format", "category", "publisher_tier", "region", "country", "vertical", "campaign_type",
  ]);
  const notYetSwept = dims.filter((d) => !currentlySwept.has(d.column));
  if (notYetSwept.length) {
    console.log(`\n  -> ${notYetSwept.length} discovered dimension(s) NOT currently in the segment sweep:`);
    for (const d of notYetSwept) console.log(`     ${d.table}.${d.column}`);
  }

  await syncDiscoveredDimensions(dims);
  console.log(`\nSynced ${dims.length} discovered dimensions into Postgres (discovered_dimensions).`);

  console.log("\n=== 2. Dynamic vs. static ratio-metric equivalence (metrics read from Postgres) ===");
  const metrics = await getMetricDefinitions();
  console.log(`Read ${metrics.length} metric_definitions rows from Postgres.`);
  const dynamicSql = buildRatioTrendSeasonalSelect(metrics, { withThreshold: false });
  const dynamicRows = await queryJson<{ metric: string; hour_ts: string; z: number | null }>(
    `${dynamicSql} ORDER BY metric, hour_ts`,
  );

  // Static equivalent: same query, hand-written metric list (mirrors
  // sql/04_detect_and_populate.sql's ratio block exactly), no threshold.
  const staticSql = `
    WITH ratios AS (
      SELECT hour_ts, d, dow, hod,
        fills/requests AS fill_rate,
        impressions/fills AS render_rate,
        clicks/impressions AS ctr,
        revenue/impressions*1000 AS ecpm,
        revenue/requests AS rpr
      FROM inmobi.metrics_hourly
    ),
    unpivoted AS (
      SELECT hour_ts, d, dow, hod, 'fill_rate' AS metric, fill_rate AS value FROM ratios
      UNION ALL SELECT hour_ts, d, dow, hod, 'render_rate', render_rate FROM ratios
      UNION ALL SELECT hour_ts, d, dow, hod, 'ctr', ctr FROM ratios
      UNION ALL SELECT hour_ts, d, dow, hod, 'ecpm', ecpm FROM ratios
      UNION ALL SELECT hour_ts, d, dow, hod, 'rpr', rpr FROM ratios
    ),
    cell_mean AS (SELECT metric, dow, hod, avg(value) AS ca FROM unpivoted GROUP BY metric, dow, hod),
    noise AS (
      SELECT u.metric AS metric, varSamp(u.value - cm.ca) AS v
      FROM unpivoted u JOIN cell_mean cm USING (metric, dow, hod)
      GROUP BY u.metric
    ),
    seasonal AS (
      SELECT *,
        avg(value) OVER w AS mean_v, varSamp(value) OVER w AS var_v,
        count(value) OVER w AS baseline_n
      FROM unpivoted
      WINDOW w AS (PARTITION BY metric, dow, hod ORDER BY d ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING)
    ),
    scored AS (
      SELECT s.*, n.v AS noise_v,
        sqrt((baseline_n*ifNull(var_v,0) + 3*n.v) / (baseline_n+3)) AS std_v
      FROM seasonal s JOIN noise n USING (metric)
    )
    SELECT metric, hour_ts, value, mean_v, value-mean_v AS delta, (value-mean_v)/mean_v AS pct_delta,
      (value-mean_v)/nullif(std_v,0) AS z, baseline_n
    FROM scored WHERE baseline_n >= 2
  `;
  const staticRows = await queryJson<{ metric: string; hour_ts: string; z: number | null }>(staticSql);

  console.log(`dynamic: ${dynamicRows.length} rows, static: ${staticRows.length} rows`);

  const key = (r: { metric: string; hour_ts: string }) => `${r.metric}|${r.hour_ts}`;
  const staticByKey = new Map(staticRows.map((r) => [key(r), r]));
  let maxAbsDiff = 0;
  let mismatches = 0;
  let missing = 0;
  for (const d of dynamicRows) {
    const s = staticByKey.get(key(d));
    if (!s) { missing++; continue; }
    const dz = d.z ?? 0;
    const sz = s.z ?? 0;
    const diff = Math.abs(dz - sz);
    if (diff > maxAbsDiff) maxAbsDiff = diff;
    if (diff > 1e-9) mismatches++;
  }
  console.log(`rows present in dynamic but missing from static: ${missing}`);
  console.log(`rows with z mismatch (diff > 1e-9): ${mismatches}`);
  console.log(`max |z| difference across all matched rows: ${maxAbsDiff}`);
  console.log(mismatches === 0 && missing === 0 ? "\n✅ EQUIVALENT" : "\n❌ NOT EQUIVALENT");

  await getPool().end();
}

main();
