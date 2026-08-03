import { defineSkill } from "eve/skills";

export default defineSkill({
  description: "Investigate InMobi ad-tech anomalies with ClickHouse evidence.",
  markdown: `
Use ClickHouse evidence, not the dashboard's mock display values.

The data is in the \`inmobi\` database. \`ad_events\` is the fact table:
\`event_time, app_id, geo_device_id, advertiser_id, ad_format, is_filled,
is_impression, is_click, revenue\`, ordered by \`(event_time, app_id)\`.

The core metrics are: requests = \`count(*)\`; fill rate =
\`sum(is_filled)/count(*)\`; render rate =
\`sum(is_impression)/sum(is_filled)\`; CTR =
\`sum(is_click)/sum(is_impression)\`; revenue = \`sum(revenue)\`; eCPM =
\`sum(revenue)/sum(is_impression)*1000\`; RPR = \`sum(revenue)/count(*)\`.
Always calculate rates as sum/sum, never averages of daily ratios.

For detected incidents, query \`inmobi.anomalies\` (plain \`MergeTree\`, one
writer, fully replaced every refresh — do NOT add \`FINAL\`, ClickHouse
Cloud's \`SharedMergeTree\` rejects it outright on a non-Replacing table).
Its fields are \`detected_at, metric, method, time_window, observed,
expected, delta, pct_delta, z, baseline_n\`. The
active methods are \`trend_seasonal\`, \`proportion\`, and \`day_level\`
globally, \`trend_seasonal\`/\`proportion\` only per segment. CTR and render rate are
reporting-only anomaly evidence for secondary correlation and cannot open an
incident. Canonical reportable spans are materialized in \`inmobi.incidents\`
from adverse rows whose config has \`incident_enabled=1\`. Each hourly row
qualifies independently, while a \`day_level\` row qualifies its full 24-hour
day; adjacency only groups already-qualified units. Read that table when the
dashboard supplies an incident id or window instead of reconstructing a
different incident policy from raw anomaly rows. The
hourly rollup is \`inmobi.metrics_hourly_v\` with
\`hour_ts, d, dow, hod, requests, fills, impressions, clicks, revenue\` — read
this view, not \`inmobi.metrics_hourly\` directly, which can hold more than
one partial row per hour and needs re-summing.
Use the trailing 4-week same-day-of-week, same-hour baseline when describing
comparisons.

Workflow:
1. Every ClickHouse query must be one read-only SELECT/WITH statement with a
numeric LIMIT. Narrow by time range and aggregate before reading raw rows.
2. For an open-ended "latest" request, first query the recent anomaly rows,
then query the matching metric/window to validate the lead.
3. Confirm a cause with a second query. State what happened, when, evidence,
severity, blast radius, and next action. Say inconclusive when it is.
4. For segment attribution, exclude segments under 3% of baseline volume. A
top lift above 2x is localized; otherwise call the movement broad-based.
`,
});
