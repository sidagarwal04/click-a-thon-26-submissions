import { SchemaPlan } from "../types.js";

/**
 * Build reusable Gold MVs that earn their keep for PM analytics:
 * 1. daily event + unique-user counts (with segment dims when present)
 * 2. daily funnel / conversion rates (start → success by day)
 * 3. segment success rates (device / geo / destination)
 * 4. latency distribution when a latency-like column exists
 */
export function buildMaterializedViewPlans(
  tableName: string,
  columns: SchemaPlan["columns"],
  options?: {
    startEvent?: string | null;
    successEvent?: string | null;
    entityColumn?: string | null;
  },
): SchemaPlan["materialized_views"] {
  const columnNames = new Set(columns.map((column) => column.name));
  const dimensions = [
    "device_type",
    "os",
    "geoip_country_code",
    "destination",
  ].filter((column) => columnNames.has(column));

  const entityColumn =
    options?.entityColumn && columnNames.has(options.entityColumn)
      ? options.entityColumn
      : columnNames.has("application_id")
        ? "application_id"
        : columnNames.has("user_id")
          ? "user_id"
          : null;

  const startEvent = options?.startEvent ?? null;
  const successEvent = options?.successEvent ?? null;
  const latencyColumn = pickLatencyColumn(columnNames);

  const views: SchemaPlan["materialized_views"] = [
    buildDailyEventCountMv(tableName, dimensions),
  ];

  if (entityColumn && successEvent) {
    views.push(
      buildDailyConversionMv(tableName, entityColumn, startEvent, successEvent),
    );
    if (dimensions.length > 0) {
      views.push(
        buildSegmentSuccessMv(
          tableName,
          entityColumn,
          successEvent,
          dimensions,
        ),
      );
    }
  }

  if (latencyColumn) {
    views.push(buildLatencyMv(tableName, latencyColumn));
  }

  return views;
}

function buildDailyEventCountMv(
  tableName: string,
  dimensions: string[],
): SchemaPlan["materialized_views"][number] {
  const targetTable = `${tableName}_daily_event_counts`;
  const viewName = `${targetTable}_mv`;
  const dimensionDefinitions =
    dimensions.length > 0
      ? `${dimensions.map((column) => `    ${column} String`).join(",\n")},\n`
      : "";
  const dimensionSelects =
    dimensions.length > 0
      ? `${dimensions
          .map((column) => `    toString(ifNull(${column}, '')) AS ${column}`)
          .join(",\n")},\n`
      : "";
  const dimensionGroupBy =
    dimensions.length > 0 ? `, ${dimensions.join(", ")}` : "";
  const orderBy = ["event_date", "event_name", ...dimensions].join(", ");
  const uniqueUsers = "uniq(user_id)";

  return {
    name: viewName,
    target_table: `gold.${targetTable}`,
    target_table_sql: `CREATE TABLE IF NOT EXISTS gold.${targetTable}
(
    event_date Date,
    event_name LowCardinality(String),
${dimensionDefinitions}    events UInt64,
    unique_users UInt64
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (${orderBy});`,
    view_sql: `CREATE MATERIALIZED VIEW IF NOT EXISTS gold.${viewName}
TO gold.${targetTable}
AS
SELECT
    toDate(timestamp) AS event_date,
    event_name,
${dimensionSelects}    count() AS events,
    ${uniqueUsers} AS unique_users
FROM silver.${tableName}
GROUP BY event_date, event_name${dimensionGroupBy};`,
    purpose:
      "Reusable daily event and unique-user counts for PM-facing funnel and segment analysis.",
    dimensions,
    metrics: ["events", "unique_users"],
  };
}

function buildDailyConversionMv(
  tableName: string,
  entityColumn: string,
  startEvent: string | null,
  successEvent: string,
): SchemaPlan["materialized_views"][number] {
  const targetTable = `${tableName}_daily_conversion`;
  const viewName = `${targetTable}_mv`;
  const startExpr = startEvent
    ? `uniqExactIf(${entityColumn}, event_name = '${escapeSql(startEvent)}')`
    : `uniqExact(${entityColumn})`;

  return {
    name: viewName,
    target_table: `gold.${targetTable}`,
    target_table_sql: `CREATE TABLE IF NOT EXISTS gold.${targetTable}
(
    event_date Date,
    started_entities UInt64,
    success_entities UInt64
)
ENGINE = SummingMergeTree
PARTITION BY toYYYYMM(event_date)
ORDER BY (event_date);`,
    view_sql: `CREATE MATERIALIZED VIEW IF NOT EXISTS gold.${viewName}
TO gold.${targetTable}
AS
SELECT
    toDate(timestamp) AS event_date,
    ${startExpr} AS started_entities,
    uniqExactIf(${entityColumn}, event_name = '${escapeSql(successEvent)}') AS success_entities
FROM silver.${tableName}
GROUP BY event_date;`,
    purpose:
      "Daily funnel conversion: entities reaching start vs success events for trend and uplift analysis.",
    dimensions: [],
    metrics: ["started_entities", "success_entities", "conversion_rate"],
  };
}

function buildSegmentSuccessMv(
  tableName: string,
  entityColumn: string,
  successEvent: string,
  dimensions: string[],
): SchemaPlan["materialized_views"][number] {
  const targetTable = `${tableName}_segment_success`;
  const viewName = `${targetTable}_mv`;
  const dimensionDefinitions = dimensions
    .map((column) => `    ${column} String`)
    .join(",\n");
  const dimensionSelects = dimensions
    .map((column) => `    toString(ifNull(${column}, '')) AS ${column}`)
    .join(",\n");
  const orderBy = dimensions.join(", ");

  return {
    name: viewName,
    target_table: `gold.${targetTable}`,
    target_table_sql: `CREATE TABLE IF NOT EXISTS gold.${targetTable}
(
${dimensionDefinitions},
    entities UInt64,
    success_entities UInt64
)
ENGINE = SummingMergeTree
ORDER BY (${orderBy});`,
    view_sql: `CREATE MATERIALIZED VIEW IF NOT EXISTS gold.${viewName}
TO gold.${targetTable}
AS
SELECT
${dimensionSelects},
    uniqExact(${entityColumn}) AS entities,
    uniqExactIf(${entityColumn}, event_name = '${escapeSql(successEvent)}') AS success_entities
FROM silver.${tableName}
GROUP BY ${dimensions.join(", ")};`,
    purpose:
      "Segment success rates by device/os/geo/destination for root-cause and comparison cuts.",
    dimensions,
    metrics: ["entities", "success_entities", "success_rate"],
  };
}

function buildLatencyMv(
  tableName: string,
  latencyColumn: string,
): SchemaPlan["materialized_views"][number] {
  const targetTable = `${tableName}_latency_by_event`;
  const viewName = `${targetTable}_mv`;

  return {
    name: viewName,
    target_table: `gold.${targetTable}`,
    target_table_sql: `CREATE TABLE IF NOT EXISTS gold.${targetTable}
(
    event_name LowCardinality(String),
    rows UInt64,
    latency_sum Float64,
    latency_sum_sq Float64
)
ENGINE = SummingMergeTree
ORDER BY (event_name);`,
    view_sql: `CREATE MATERIALIZED VIEW IF NOT EXISTS gold.${viewName}
TO gold.${targetTable}
AS
SELECT
    event_name,
    count() AS rows,
    sum(toFloat64(${latencyColumn})) AS latency_sum,
    sum(pow(toFloat64(${latencyColumn}), 2)) AS latency_sum_sq
FROM silver.${tableName}
WHERE ${latencyColumn} IS NOT NULL
GROUP BY event_name;`,
    purpose: `Latency rollup for ${latencyColumn} by event_name (sum/sum_sq for mean and variance reconstruction).`,
    dimensions: [],
    metrics: ["rows", "latency_sum", "latency_sum_sq"],
  };
}

function pickLatencyColumn(columnNames: Set<string>) {
  const preferred = [
    "payment_latency_ms",
    "latency_ms",
    "duration_ms",
    "processing_time_ms",
    "time_to_complete_ms",
    "time_on_page_s",
  ];
  for (const name of preferred) {
    if (columnNames.has(name)) {
      return name;
    }
  }
  return Array.from(columnNames).find((column) =>
    /latency|duration|time_to|elapsed/.test(column),
  );
}

function escapeSql(value: string) {
  return value.replace(/\\/g, "\\\\").replace(/'/g, "\\'");
}
