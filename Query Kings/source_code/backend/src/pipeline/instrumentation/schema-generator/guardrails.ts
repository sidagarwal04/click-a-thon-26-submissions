import { toColumnName } from "../eventUtils.js";
import { EventProfile, FeatureManifest, SchemaPlan } from "../types.js";
import { buildSchemaPlan } from "./fallback.js";
import { buildMaterializedViewPlans } from "./materializedViews.js";
import { SchemaDesignDraft } from "./types.js";

export function normalizeDesignDraft(
  draft: SchemaDesignDraft,
  fallbackPlan: SchemaPlan,
  eventProfile: EventProfile,
  manifest?: FeatureManifest | null,
): SchemaPlan {
  const allowedSourcePaths = new Set(
    eventProfile.fields.map((field) => field.path),
  );
  const fallbackByName = new Map(
    fallbackPlan.columns.map((column) => [column.name, column]),
  );
  const columns: SchemaPlan["columns"] = [];
  const seenNames = new Set<string>();

  for (const draftColumn of draft.columns ?? []) {
    const name = toColumnName(draftColumn.name);
    if (!name || seenNames.has(name)) {
      continue;
    }
    const fallbackColumn = fallbackByName.get(name);
    const sourcePath = normalizeSourcePath(name, draftColumn.source_path);
    if (sourcePath && !allowedSourcePaths.has(sourcePath)) {
      continue;
    }
    if (!sourcePath && !isPipelineColumn(name)) {
      continue;
    }

    const field = sourcePath
      ? eventProfile.fields.find((candidate) => candidate.path === sourcePath)
      : null;
    const fallbackType =
      fallbackColumn?.type ?? typeForPipelineColumn(name) ?? "String";
    const type = sanitizeColumnType(
      draftColumn.type,
      fallbackType,
      field,
      eventProfile.row_count,
      name,
    );

    columns.push({
      name,
      type,
      source_path: sourcePath,
      reason:
        draftColumn.reason ||
        fallbackColumn?.reason ||
        "Selected by schema designer and validated against event evidence.",
    });
    seenNames.add(name);
  }

  const mergedColumns = mergeColumns(columns, fallbackPlan.columns);
  const columnNames = new Set(mergedColumns.map((column) => column.name));
  const nullableColumns = new Set(
    mergedColumns
      .filter((column) => column.type.startsWith("Nullable("))
      .map((column) => column.name),
  );
  const orderBy = (draft.order_by ?? []).filter(
    (column, index, all) =>
      columnNames.has(column) &&
      !nullableColumns.has(column) &&
      all.indexOf(column) === index,
  );

  const partitionBy =
    draft.partition_by === "toYYYYMM(timestamp)"
      ? draft.partition_by
      : fallbackPlan.partition_by;
  const ttl = normalizeTtl(draft.ttl, fallbackPlan.ttl);

  return repairSchemaPlan(
    {
      database: "silver",
      table_name:
        draft.table_name === fallbackPlan.table_name
          ? draft.table_name
          : fallbackPlan.table_name,
      engine:
        draft.engine === "ReplacingMergeTree"
          ? draft.engine
          : fallbackPlan.engine,
      partition_by: partitionBy,
      ttl,
      order_by: orderBy,
      columns: mergedColumns,
      materialized_views: buildMaterializedViewPlans(
        fallbackPlan.table_name,
        mergedColumns,
        mvOptionsFrom(manifest, mergedColumns),
      ),
    },
    null,
    null,
    manifest,
  );
}

function normalizeSourcePath(columnName: string, sourcePath: string | null) {
  if (columnName === "event_name") {
    return "event";
  }
  if (columnName === "event_id") {
    return "id";
  }
  if (columnName === "timestamp") {
    return "timestamp";
  }
  return sourcePath;
}

function isPipelineColumn(columnName: string) {
  return ["job_id", "raw_json", "ingested_at"].includes(columnName);
}

function typeForPipelineColumn(columnName: string) {
  if (columnName === "job_id" || columnName === "raw_json") {
    return "String";
  }
  if (columnName === "ingested_at") {
    return "DateTime DEFAULT now()";
  }
  return null;
}

function sanitizeColumnType(
  requestedType: string,
  fallbackType: string,
  field: EventProfile["fields"][number] | null | undefined,
  totalRows: number,
  columnName: string,
) {
  const allowedTypes = new Set([
    "String",
    "LowCardinality(String)",
    "DateTime64(3)",
    "DateTime DEFAULT now()",
    "Bool",
    "UInt8",
    "UInt16",
    "UInt32",
    "UInt64",
    "Int64",
    "Float64",
    "Nullable(String)",
    "Nullable(Bool)",
    "Nullable(UInt8)",
    "Nullable(UInt16)",
    "Nullable(UInt32)",
    "Nullable(UInt64)",
    "Nullable(Int64)",
    "Nullable(Float64)",
  ]);
  if (!allowedTypes.has(requestedType)) {
    return fallbackType;
  }
  if (columnName === "timestamp") {
    return "DateTime64(3)";
  }
  if (columnName === "event_name") {
    return "LowCardinality(String)";
  }
  if (columnName === "event_id") {
    return "String";
  }
  if (columnName === "ingested_at") {
    return "DateTime DEFAULT now()";
  }
  const sourceIsNullable =
    field && (field.null_count > 0 || field.count < totalRows);
  if (!sourceIsNullable && requestedType.startsWith("Nullable(")) {
    return fallbackType;
  }
  if (sourceIsNullable && !requestedType.startsWith("Nullable(")) {
    return fallbackType.startsWith("Nullable(")
      ? fallbackType
      : `Nullable(${fallbackType.replace("LowCardinality(String)", "String")})`;
  }
  return requestedType;
}

export function reviewSchemaPlan(
  plan: SchemaPlan,
  eventProfile: EventProfile,
): string[] {
  const issues: string[] = [];
  const columnNames = new Set(plan.columns.map((column) => column.name));
  const sourcePaths = new Set(
    plan.columns
      .map((column) => column.source_path)
      .filter((sourcePath): sourcePath is string => Boolean(sourcePath)),
  );
  const nullableColumns = new Set(
    plan.columns
      .filter((column) => column.type.startsWith("Nullable("))
      .map((column) => column.name),
  );

  for (const required of [
    "job_id",
    "event_name",
    "event_id",
    "timestamp",
    "raw_json",
  ]) {
    if (!columnNames.has(required)) {
      issues.push(`missing_required_column:${required}`);
    }
  }

  for (const column of plan.order_by) {
    if (!columnNames.has(column)) {
      issues.push(`order_by_unknown_column:${column}`);
    }
    if (nullableColumns.has(column)) {
      issues.push(`order_by_nullable_column:${column}`);
    }
  }

  if (!plan.order_by.includes("timestamp")) {
    issues.push("order_by_missing_timestamp");
  }
  if (!plan.order_by.includes("event_id")) {
    issues.push("order_by_missing_event_id");
  }

  if (parseTtlMonths(plan.ttl) < MIN_TTL_MONTHS) {
    issues.push(`ttl_too_short:${plan.ttl}`);
  }

  for (const field of eventProfile.fields) {
    if (
      !["event", "id", "timestamp"].includes(field.path) &&
      !sourcePaths.has(field.path)
    ) {
      issues.push(`unmapped_raw_field:${field.path}`);
    }
  }

  return issues;
}

export function repairSchemaPlan(
  plan: SchemaPlan,
  manifest: FeatureManifest | null,
  eventProfile: EventProfile | null,
  manifestForMv?: FeatureManifest | null,
): SchemaPlan {
  const baseline =
    manifest && eventProfile ? buildSchemaPlan(manifest, eventProfile) : plan;
  const columns = canonicalizeKeyColumns(
    mergeColumns(plan.columns, baseline.columns),
    baseline.columns,
  );
  const columnNames = new Set(columns.map((column) => column.name));
  const nullableColumns = new Set(
    columns
      .filter((column) => column.type.startsWith("Nullable("))
      .map((column) => column.name),
  );
  const orderBy = plan.order_by.filter(
    (column, index, all) =>
      columnNames.has(column) &&
      !nullableColumns.has(column) &&
      all.indexOf(column) === index,
  );
  const repairedOrderBy =
    orderBy.includes("timestamp") && orderBy.includes("event_id")
      ? orderBy
      : baseline.order_by;
  const mvManifest = manifest ?? manifestForMv ?? null;

  return {
    ...plan,
    partition_by: plan.partition_by || baseline.partition_by,
    ttl: normalizeTtl(plan.ttl, baseline.ttl),
    order_by: repairedOrderBy,
    columns,
    materialized_views: buildMaterializedViewPlans(
      plan.table_name,
      columns,
      mvOptionsFrom(mvManifest, columns),
    ),
  };
}

function mvOptionsFrom(
  manifest: FeatureManifest | null | undefined,
  columns: SchemaPlan["columns"],
) {
  const columnNames = new Set(columns.map((column) => column.name));
  const entityColumn = manifest
    ? columnNames.has(
        manifest.primary_entity.endsWith("_id")
          ? manifest.primary_entity
          : `${manifest.primary_entity}_id`,
      )
      ? manifest.primary_entity.endsWith("_id")
        ? manifest.primary_entity
        : `${manifest.primary_entity}_id`
      : columnNames.has("application_id")
        ? "application_id"
        : columnNames.has("user_id")
          ? "user_id"
          : null
    : columnNames.has("application_id")
      ? "application_id"
      : columnNames.has("user_id")
        ? "user_id"
        : null;

  return {
    startEvent: manifest?.event_order[0] ?? null,
    successEvent: manifest?.success_event ?? null,
    entityColumn,
  };
}

const MIN_TTL_MONTHS = 18;

function normalizeTtl(ttl: string | undefined, fallbackTtl: string) {
  const months = parseTtlMonths(ttl);
  return months >= MIN_TTL_MONTHS ? ttl! : fallbackTtl;
}

function parseTtlMonths(ttl: string | undefined) {
  const match = ttl?.match(/^timestamp \+ INTERVAL (\d+) MONTH$/);
  return match ? Number(match[1]) : 0;
}

function canonicalizeKeyColumns(
  columns: SchemaPlan["columns"],
  baselineColumns: SchemaPlan["columns"],
) {
  const baselineByName = new Map(
    baselineColumns.map((column) => [column.name, column]),
  );
  const canonicalNames = new Set([
    "job_id",
    "event_name",
    "event_id",
    "timestamp",
    "raw_json",
    "ingested_at",
    "user_id",
    "application_id",
  ]);
  return columns.map((column) => {
    const baselineColumn = baselineByName.get(column.name);
    if (
      baselineColumn &&
      canonicalNames.has(column.name) &&
      column.type.startsWith("Nullable(") &&
      !baselineColumn.type.startsWith("Nullable(")
    ) {
      return {
        ...column,
        type: baselineColumn.type,
        reason: `${column.reason} Canonicalized to non-nullable type because raw evidence has complete values.`,
      };
    }
    return column;
  });
}

function mergeColumns(
  columns: SchemaPlan["columns"],
  baselineColumns: SchemaPlan["columns"],
) {
  const merged = [...columns];
  const names = new Set(merged.map((column) => column.name));
  for (const baselineColumn of baselineColumns) {
    if (!names.has(baselineColumn.name)) {
      merged.push(baselineColumn);
      names.add(baselineColumn.name);
    }
  }
  return merged;
}
