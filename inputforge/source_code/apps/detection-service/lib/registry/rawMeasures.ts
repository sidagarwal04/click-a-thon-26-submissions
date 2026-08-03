import type { RawMeasureId } from "./types.js";

// The fixed set of raw measures materialized in metrics_hourly /
// segment_metrics_hourly. Hardcoded, not Postgres-backed — see the comment
// in types.ts for why. This is the one place a raw ClickHouse column name is
// written; metric_definitions rows reference these by id only.
export const RAW_MEASURES: Record<RawMeasureId, { label: string; column: string }> = {
  requests: { label: "Requests", column: "requests" },
  fills: { label: "Fills", column: "fills" },
  impressions: { label: "Impressions", column: "impressions" },
  clicks: { label: "Clicks", column: "clicks" },
  revenue: { label: "Revenue", column: "revenue" },
};
