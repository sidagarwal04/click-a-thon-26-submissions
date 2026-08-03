// There's no more "sweep" to trigger locally — sql/mv/'s materialized views
// react to ad_events inserts on their own, ClickHouse-side, whether or not
// this process is even running. This script just prints whatever the MVs
// have already computed recently, plus the current incident spans
// (read from the refreshable mv_incidents target — see
// lib/incremental/incidents.ts). `npm run sweep:local`.
import { computeIncidentSpans } from "../lib/incremental/incidents.js";
import {
  fetchFreshAnomalies,
  fetchFreshSegmentAnomalies,
} from "../lib/incremental/tick.js";

const since = new Date(Date.now() - 24 * 60 * 60 * 1000);

const anomalies = await fetchFreshAnomalies(since);
console.log(`${anomalies.length} global anomalies in the last 24h:`);
for (const a of anomalies.slice(0, 20)) {
  console.log(
    `  ${a.metric}/${a.method} @ ${a.time_window}  z=${a.z.toFixed(2)}`,
  );
}

const segmentAnomalies = await fetchFreshSegmentAnomalies(since);
console.log(
  `\n${segmentAnomalies.length} segment anomalies in the last 24h (only populated after a segment sweep has run):`,
);
for (const a of segmentAnomalies.slice(0, 20)) {
  console.log(
    `  ${a.dimension}=${a.segment} ${a.metric}/${a.method} @ ${a.time_window}  z=${a.z.toFixed(2)}`,
  );
}

const spans = await computeIncidentSpans();
console.log(
  `\n${spans.length} current adverse incident spans (independent hours/days, collapsed from inmobi.anomalies):`,
);
for (const s of spans) {
  console.log(
    `  ${s.metric}: ${s.start_time} -> ${s.end_time} (${s.span_hours}h, ${s.flagged_hours} flagged, methods=${s.methods.join(",")}, max|z|=${s.max_abs_z.toFixed(2)})`,
  );
}
