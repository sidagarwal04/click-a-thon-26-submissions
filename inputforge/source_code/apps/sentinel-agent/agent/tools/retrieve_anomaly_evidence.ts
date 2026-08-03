import { defineTool } from "eve/tools";
import { z } from "zod";
import { queryReadOnly } from "../clickhouse";

const metrics = [
  "requests",
  "revenue",
  "fill_rate",
  "render_rate",
  "ctr",
  "ecpm",
  "rpr",
] as const;
const metricSchema = z.enum(metrics);

function normalizeUtcTimestamp(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime()))
    throw new Error("startTime and endTime must be valid timestamps.");
  return date.toISOString().slice(0, 19).replace("T", " ");
}

function metricExpression(metric: (typeof metrics)[number]): string {
  switch (metric) {
    case "requests":
      return "toFloat64(requests)";
    case "revenue":
      return "revenue";
    case "fill_rate":
      return "toFloat64(fills) / nullIf(requests, 0)";
    case "render_rate":
      return "toFloat64(impressions) / nullIf(fills, 0)";
    case "ctr":
      return "toFloat64(clicks) / nullIf(impressions, 0)";
    case "ecpm":
      return "revenue / nullIf(impressions, 0) * 1000";
    case "rpr":
      return "revenue / nullIf(requests, 0)";
  }
}

export default defineTool({
  description:
    "Retrieve the canonical ClickHouse evidence for the anomaly currently selected in Sentinel. " +
    "Use this first for any question about that incident; it returns the incident, detector rows, " +
    "same-metric segment signals, all-segment rule-out evidence, and an hourly window around it.",
  inputSchema: z.object({
    metric: metricSchema,
    startTime: z
      .string()
      .describe(
        "Selected incident start time, normally from dashboardIncident.",
      ),
    endTime: z
      .string()
      .describe("Selected incident end time, normally from dashboardIncident."),
  }),
  async execute({ metric, startTime, endTime }) {
    const start = normalizeUtcTimestamp(startTime);
    const end = normalizeUtcTimestamp(endTime);
    if (start > end)
      throw new Error("startTime must be no later than endTime.");

    const where = `metric = '${metric}' AND time_window >= toDateTime('${start}') AND time_window <= toDateTime('${end}')`;
    const [incident, detectorRows, segmentSignals, segmentEvidence, hourly] =
      await Promise.all([
        queryReadOnly(`
        SELECT metric, start_time, end_time, span_hours, flagged_hours, methods,
               max_abs_z, detected_at, observed, expected, pct_delta, refreshed_at
        FROM inmobi.incidents
        WHERE metric = '${metric}'
          AND start_time <= toDateTime('${end}')
          AND end_time >= toDateTime('${start}')
        ORDER BY start_time DESC
        LIMIT 5
      `),
        queryReadOnly(`
        SELECT metric, method, time_window, observed, expected, delta, pct_delta, z, baseline_n
        FROM inmobi.anomalies
        WHERE ${where}
        ORDER BY time_window, method
        LIMIT 200
      `),
        queryReadOnly(`
        SELECT dimension, segment, metric, method, time_window, observed, expected,
               pct_delta, z, baseline_n
        FROM inmobi.segment_anomalies
        WHERE ${where}
        ORDER BY abs(z) DESC, time_window DESC
        LIMIT 100
      `),
        queryReadOnly(`
        SELECT dimension, segment, peak_z, mean_z, global_peak_z, global_mean_z,
               incident_correlation, incident_correlation_n,
               baseline_correlation, baseline_correlation_n,
               direction_match_pct, scored_hours, quiet_hours
        FROM inmobi.segment_incident_evidence
        WHERE metric = '${metric}'
          AND incident_start = toDateTime('${start}')
          AND incident_end = toDateTime('${end}')
        ORDER BY dimension, abs(peak_z) DESC
        LIMIT 500
      `),
        queryReadOnly(`
        SELECT hour_ts, requests, fills, impressions, clicks, revenue,
               ${metricExpression(metric)} AS metric_value
        FROM inmobi.metrics_hourly_v
        WHERE hour_ts >= toDateTime('${start}') - INTERVAL 24 HOUR
          AND hour_ts <= toDateTime('${end}') + INTERVAL 24 HOUR
        ORDER BY hour_ts
        LIMIT 200
      `),
      ]);

    return {
      scope: { metric, startTime: start, endTime: end },
      incident: incident.rows,
      detectorRows: detectorRows.rows,
      segmentSignals: segmentSignals.rows,
      segmentEvidence: segmentEvidence.rows,
      hourly: hourly.rows,
      metricDefinition: {
        requests: "count of ad events",
        revenue: "sum of revenue",
        fill_rate: "fills / requests",
        render_rate: "impressions / fills",
        ctr: "clicks / impressions",
        ecpm: "revenue / impressions * 1000",
        rpr: "revenue / requests",
      }[metric],
    };
  },
});
