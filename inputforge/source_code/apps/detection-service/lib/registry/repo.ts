import { getPool } from "./db.js";
import type { DimensionDefinition, MetricDefinition, Monitor } from "./types.js";

/** Replaces lib/registry/seed.ts's in-memory stand-in now that Postgres is
 * wired up — same shape, real data. seed.ts / db/seed.sql stay in sync as
 * the fixture; this is what production code actually reads. */

interface MetricRow {
  id: string;
  label: string;
  kind: "volume" | "ratio";
  numerator_id: string;
  denominator_id: string | null;
  scale: string; // numeric comes back as string from pg by default
  requires_fill: boolean;
}

export async function getMetricDefinitions(): Promise<MetricDefinition[]> {
  const { rows } = await getPool().query<MetricRow>(
    `SELECT id, label, kind, numerator_id, denominator_id, scale, requires_fill FROM metric_definitions ORDER BY id`,
  );
  return rows.map((r) => ({
    id: r.id,
    label: r.label,
    kind: r.kind,
    numeratorId: r.numerator_id as MetricDefinition["numeratorId"],
    denominatorId: (r.denominator_id ?? undefined) as MetricDefinition["denominatorId"],
    scale: Number(r.scale),
    requiresFill: r.requires_fill,
  }));
}

interface DimensionRow {
  id: string;
  label: string;
  source: "event_column" | "joined_table";
  join_table: string | null;
  join_key: string | null;
  column_name: string;
  requires_fill: boolean;
  cardinality_hint: number;
  enabled_for_sweep: boolean;
}

export async function getDimensionDefinitions(): Promise<DimensionDefinition[]> {
  const { rows } = await getPool().query<DimensionRow>(
    `SELECT id, label, source, join_table, join_key, column_name, requires_fill, cardinality_hint, enabled_for_sweep
     FROM dimension_definitions ORDER BY id`,
  );
  return rows.map((r) => ({
    id: r.id,
    label: r.label,
    source: r.source,
    joinTable: (r.join_table ?? undefined) as DimensionDefinition["joinTable"],
    joinKey: (r.join_key ?? undefined) as DimensionDefinition["joinKey"],
    columnName: r.column_name,
    requiresFill: r.requires_fill,
    cardinalityHint: r.cardinality_hint,
    enabledForSweep: r.enabled_for_sweep,
  }));
}

interface MonitorRow {
  id: string;
  name: string;
  metric_id: string;
  dimension_id: string | null;
  methods: Monitor["methods"];
  webhook_url: string | null;
  owner: string | null;
  enabled: boolean;
}

export async function getMonitors(): Promise<Monitor[]> {
  const { rows } = await getPool().query<MonitorRow>(
    `SELECT id, name, metric_id, dimension_id, methods, webhook_url, owner, enabled FROM monitors WHERE enabled ORDER BY name`,
  );
  return rows.map((r) => ({
    id: r.id,
    name: r.name,
    metricId: r.metric_id,
    dimensionId: r.dimension_id,
    methods: r.methods,
    webhookUrl: r.webhook_url ?? undefined,
    owner: r.owner ?? undefined,
    enabled: r.enabled,
  }));
}
