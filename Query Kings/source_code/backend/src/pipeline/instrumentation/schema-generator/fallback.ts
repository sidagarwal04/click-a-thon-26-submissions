import { toColumnName } from "../eventUtils.js";
import { EventProfile, FeatureManifest, SchemaPlan } from "../types.js";
import { buildMaterializedViewPlans } from "./materializedViews.js";

export function buildSchemaPlan(
  manifest: FeatureManifest,
  eventProfile: EventProfile,
): SchemaPlan {
  const tableName = `${manifest.feature_slug}_events`;
  const standardColumns = new Set([
    "event",
    "id",
    "timestamp",
    "user_id",
    "application_id",
    "app_session_id",
    "device",
    "device_type",
    "os",
    "app_version",
    "client_lib",
    "geoip_country_code",
    "geoip_subdivision_1_code",
    "city",
    "destination",
    "citizenship",
    "gclid",
    "fbclid",
    "duplicate_id",
    "is_back_filled",
  ]);

  const columns: SchemaPlan["columns"] = [
    {
      name: "job_id",
      type: "String",
      source_path: null,
      reason: "Pipeline run identifier for replay and trace joins.",
    },
    {
      name: "event_name",
      type: "LowCardinality(String)",
      source_path: "event",
      reason: "Common event discriminator for funnel and step analysis.",
    },
    {
      name: "event_id",
      type: "String",
      source_path: "id",
      reason: "Raw event identifier used for dedupe and audit.",
    },
    {
      name: "timestamp",
      type: "DateTime64(3)",
      source_path: "timestamp",
      reason: "Primary time dimension for partitions and sequence analysis.",
    },
  ];

  for (const field of eventProfile.fields) {
    if (["event", "id", "timestamp"].includes(field.path)) {
      continue;
    }

    const name = toColumnName(field.path);
    columns.push({
      name,
      type: clickHouseTypeForField(
        field,
        standardColumns.has(field.path),
        eventProfile.row_count,
      ),
      source_path: field.path,
      reason: standardColumns.has(field.path)
        ? "Atlys common envelope field."
        : "Feature-specific field inferred from raw events.",
    });
  }

  columns.push({
    name: "raw_json",
    type: "String",
    source_path: null,
    reason: "Lossless raw payload for audit, replay, and schema evolution.",
  });
  columns.push({
    name: "ingested_at",
    type: "DateTime DEFAULT now()",
    source_path: null,
    reason: "Operational ingest timestamp.",
  });

  const columnNames = new Set(columns.map((column) => column.name));
  const nullableColumns = new Set(
    columns
      .filter((column) => column.type.startsWith("Nullable("))
      .map((column) => column.name),
  );
  const primaryEntityColumn = resolvePrimaryEntityColumn(
    manifest.primary_entity,
    columnNames,
  );

  const orderBy = [
    "event_name",
    "timestamp",
    primaryEntityColumn,
    "user_id",
    "event_id",
  ].filter(
    (column, index, all) =>
      all.indexOf(column) === index && !nullableColumns.has(column),
  );

  return {
    database: "silver",
    table_name: tableName,
    engine: "ReplacingMergeTree",
    partition_by: "toYYYYMM(timestamp)",
    order_by: orderBy,
    ttl: "timestamp + INTERVAL 18 MONTH",
    columns,
    materialized_views: buildMaterializedViewPlans(tableName, columns, {
      startEvent: manifest.event_order[0] ?? null,
      successEvent: manifest.success_event,
      entityColumn: primaryEntityColumn,
    }),
  };
}
function resolvePrimaryEntityColumn(
  primaryEntity: string,
  columnNames: Set<string>,
) {
  const normalized = toColumnName(primaryEntity);
  if (columnNames.has(normalized)) {
    return normalized;
  }

  const withId = `${normalized}_id`;
  if (columnNames.has(withId)) {
    return withId;
  }

  return columnNames.has("application_id") ? "application_id" : "user_id";
}
function clickHouseTypeForField(
  field: EventProfile["fields"][number],
  isStandard: boolean,
  totalRows: number,
): string {
  const types = field.types.filter((type) => type !== "null");
  const nullable = field.null_count > 0 || field.count < totalRows;
  const wrap = (type: string) => {
    if (!nullable) {
      return type;
    }
    if (type === "LowCardinality(String)") {
      return "Nullable(String)";
    }
    return `Nullable(${type})`;
  };

  if (field.path.endsWith("_id") || field.path === "id") {
    return wrap("String");
  }

  if (field.path === "is_back_filled" || field.path.startsWith("is_")) {
    return wrap("UInt8");
  }

  if (types.length === 1 && types[0] === "boolean") {
    return wrap("Bool");
  }

  if (types.length === 1 && types[0] === "number") {
    const samples = field.sample_values.filter(
      (sample): sample is number => typeof sample === "number",
    );
    if (/(amount|value|rate|price|revenue|currency_value)/i.test(field.path)) {
      return wrap("Float64");
    }
    if (/(latency|duration|time_on_page)/i.test(field.path)) {
      return wrap("UInt32");
    }
    const integerOnly = samples.every((sample) => Number.isInteger(sample));
    return wrap(integerOnly ? integerTypeForSamples(samples) : "Float64");
  }

  if (field.path === "timestamp") {
    return "DateTime64(3)";
  }

  const baseString =
    isStandard || field.sample_values.length <= 50
      ? "LowCardinality(String)"
      : "String";
  return wrap(baseString);
}

function integerTypeForSamples(samples: number[]) {
  const max = Math.max(...samples, 0);
  const min = Math.min(...samples, 0);
  if (min >= 0 && max <= 255) {
    return "UInt8";
  }
  if (min >= 0 && max <= 65535) {
    return "UInt16";
  }
  if (min >= 0 && max <= 4294967295) {
    return "UInt32";
  }
  return "Int64";
}
