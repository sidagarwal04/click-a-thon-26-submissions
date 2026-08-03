// Prints the canonical spans materialized in inmobi.incidents:
// `npm run incidents:local`.
import { computeIncidentSpans } from "../lib/incremental/incidents.js";

const spans = await computeIncidentSpans();
console.log(`${spans.length} current incident spans:`);
for (const s of spans) {
  console.log(
    `  ${s.metric}: ${s.start_time} -> ${s.end_time} (${s.span_hours}h, ${s.flagged_hours} flagged, methods=${s.methods.join(",")}, max|z|=${s.max_abs_z.toFixed(2)})`,
  );
}
