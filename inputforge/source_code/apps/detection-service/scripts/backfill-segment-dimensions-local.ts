/**
 * Backfill only dimensions that are completely absent from the reactive
 * segment rollup. This handles environments where ad_events were loaded before
 * the dimension joins existed or before their lookup tables were populated.
 *
 * Existing dimensions are filtered out, so rerunning this script does not
 * duplicate a complete dimension. It intentionally does not try to repair a
 * partially populated dimension; that requires an explicit rebuild decision.
 */
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { getClient, queryJson } from "../lib/clickhouse.js";

const here = path.dirname(fileURLToPath(import.meta.url));
const mvSql = await readFile(
  path.join(here, "..", "sql", "mv", "07_mv_segment_metrics_hourly.sql"),
  "utf8",
);
const marker = "\nAS\n";
const selectStart = mvSql.indexOf(marker);
if (selectStart < 0) throw new Error("Could not find the segment MV SELECT body.");
const selectBody = mvSql.slice(selectStart + marker.length).replace(/;\s*$/, "");

const before = await queryJson<{ dimension: string }>(`
  SELECT DISTINCT dimension
  FROM inmobi.segment_metrics_hourly
  ORDER BY dimension
`);
const existing = new Set(before.map((row) => row.dimension));
const expected = [
  "ad_format",
  "category",
  "publisher_tier",
  "region",
  "country",
  "vertical",
  "campaign_type",
];
const missing = expected.filter((dimension) => !existing.has(dimension));

if (missing.length === 0) {
  console.log("All segment dimensions are already populated; nothing to backfill.");
  process.exit(0);
}

await getClient().command({
  query: `
    INSERT INTO inmobi.segment_metrics_hourly
    SELECT *
    FROM (${selectBody})
    WHERE dimension NOT IN (
      SELECT DISTINCT dimension FROM inmobi.segment_metrics_hourly
    )
  `,
});

const counts = await queryJson<{
  dimension: string;
  segments: string;
  hourly_rows: string;
}>(`
  SELECT dimension, toString(uniqExact(segment)) AS segments,
    toString(count()) AS hourly_rows
  FROM inmobi.segment_metrics_hourly_v
  GROUP BY dimension
  ORDER BY dimension
`);

console.log(`Backfilled missing dimensions: ${missing.join(", ")}`);
for (const row of counts) {
  console.log(`${row.dimension}: ${row.segments} segments, ${row.hourly_rows} hourly rows`);
}
