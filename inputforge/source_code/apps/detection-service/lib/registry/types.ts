import { z } from "zod";

// This module's shape mirrors the Postgres control-plane schema 1:1 (see
// apps/detection-service/README.md's registry section) — Postgres isn't
// provisioned yet, so lib/registry/seed.ts stands in for "SELECT * FROM
// metric_definitions" etc. until that's wired up. The point of keeping the
// types here Zod-validated is that whichever store backs this later
// (Postgres today, something else tomorrow), the shape a PM can produce
// through the UI is constrained the same way.

export const RawMeasureId = z.enum(["requests", "fills", "impressions", "clicks", "revenue"]);
export type RawMeasureId = z.infer<typeof RawMeasureId>;

// NOT a Postgres table — hardcoded in code (registry/rawMeasures.ts), not a
// control-plane concept. Adding a raw measure means new raw data landing in
// ad_events/metrics_hourly, which is inherently an engineering task (a
// migration + rollup change), not something a config row could make happen.
// metric_definitions (below) is the layer that's actually dynamic/PM-facing:
// new *combinations* of these 5 measures need zero pipeline changes.

export const MetricDefinition = z.object({
  id: z.string(),
  label: z.string(),
  kind: z.enum(["volume", "ratio"]),
  numeratorId: RawMeasureId,
  denominatorId: RawMeasureId.optional(),
  scale: z.number().default(1),
  requiresFill: z.boolean().default(false),
});
export type MetricDefinition = z.infer<typeof MetricDefinition>;

export const DimensionDefinition = z.object({
  id: z.string(),
  label: z.string(),
  source: z.enum(["event_column", "joined_table"]),
  joinTable: z.enum(["apps", "geo_device", "advertisers"]).optional(),
  joinKey: z.enum(["app_id", "geo_device_id", "advertiser_id"]).optional(),
  columnName: z.string(),
  requiresFill: z.boolean().default(false),
  cardinalityHint: z.number(),
  enabledForSweep: z.boolean().default(true),
});
export type DimensionDefinition = z.infer<typeof DimensionDefinition>;

export const MonitorMethodConfig = z.object({
  method: z.enum(["trend_seasonal", "proportion", "day_level"]),
  zThreshold: z.number(),
  enabled: z.boolean().default(true),
});
export type MonitorMethodConfig = z.infer<typeof MonitorMethodConfig>;

// The only table a PM edits. Deliberately references metrics/dimensions by
// id (FK), never carries a raw expression.
export const Monitor = z.object({
  id: z.string(),
  name: z.string(),
  metricId: z.string(),
  dimensionId: z.string().nullable(),
  methods: z.array(MonitorMethodConfig),
  webhookUrl: z.string().url().optional(),
  owner: z.string().optional(),
  enabled: z.boolean().default(true),
});
export type Monitor = z.infer<typeof Monitor>;
