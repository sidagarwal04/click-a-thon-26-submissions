/**
 * Force every refreshable MV to run right now, in dependency order, instead
 * of waiting up to ten minutes for its own schedule. Since the cascaded
 * stages (zr, detection, incidents) became refreshable MVs — see
 * sql/mv/README.md for why — they no longer need the drop-and-backfill
 * dance this script used to do: a refreshable MV always recomputes full
 * history on every run, so "recompute now" is just "refresh now."
 * `npm run recompute:local`.
 */
import { getClient, queryJson } from "../lib/clickhouse.js";

const ch = getClient();

// Dependency order matters even though mv_detect_global/mv_incidents
// already DEPENDS ON their upstream view — SYSTEM REFRESH VIEW triggers a
// refresh immediately regardless of the schedule, but doesn't itself wait
// for a DEPENDS ON parent, so we still refresh+wait top-down by hand here.
const chain = [
  "mv_noise_baseline_daily",
  "mv_zr_hourly",
  "mv_detect_global",
  "mv_segment_detect_global",
  "mv_segment_zr_hourly",
  "mv_incidents",
  "mv_segment_incident_evidence",
];

for (const view of chain) {
  await ch.command({ query: `SYSTEM REFRESH VIEW inmobi.${view}` });
  await ch.command({ query: `SYSTEM WAIT VIEW inmobi.${view}` });
  console.log(`refreshed ${view}`);
}

const counts = await queryJson<{ table_name: string; rows: string }>(`
  SELECT * FROM (
    SELECT 'metric_zr_hourly' AS table_name, toString(count()) AS rows FROM inmobi.metric_zr_hourly
    UNION ALL
    SELECT 'anomalies', toString(count()) FROM inmobi.anomalies
    UNION ALL
    SELECT 'segment_anomalies', toString(count()) FROM inmobi.segment_anomalies
    UNION ALL
    SELECT 'segment_zr_hourly', toString(count()) FROM inmobi.segment_zr_hourly
    UNION ALL
    SELECT 'segment_incident_evidence', toString(count()) FROM inmobi.segment_incident_evidence
    UNION ALL
    SELECT 'incidents', toString(count()) FROM inmobi.incidents
  )
  ORDER BY table_name
`);
for (const row of counts) console.log(`${row.table_name}: ${row.rows}`);
