import { createHash } from "node:crypto";
import path from "node:path";
import {
  BASE_FUNNEL_TABLES,
  BASE_SUPPORTING_TABLES,
  qualifyFeatureTable,
} from "../warehouseTables.js";
import { buildKnownIssueFacts, detectAndWriteContextGaps } from "./detect.js";
import { insertJsonRows } from "./sql.js";
import { emptyRegistry, UpdateGeneratedContextInput } from "./types.js";
import { ensureContextTables } from "./tables.js";
import { readGeneratedContext } from "./read.js";
import { slugify } from "./utils.js";

export async function updateGeneratedContext(
  input: UpdateGeneratedContextInput,
) {
  await ensureContextTables();
  const fullTableName = qualifyFeatureTable(input.table_name);

  await insertJsonRows("context.feature_registry", [
    {
      feature_slug: input.feature_slug,
      job_id: input.job_id,
      table_name: fullTableName,
      primary_entity: input.primary_entity,
      workflow_type: input.workflow_type,
      event_names_json: JSON.stringify(input.event_names),
      success_event: input.success_event ?? "",
      metric_hints_json: JSON.stringify(input.metric_hints),
      validation_json: JSON.stringify(input.validation),
    },
  ]);

  await insertJsonRows("context.fact_registry", [
    {
      fact_id: `feature:${input.feature_slug}:uses_table`,
      fact_type: "feature",
      subject: input.feature_slug,
      predicate: "uses_table",
      object: fullTableName,
      confidence: 1,
      evidence_json: JSON.stringify([
        "feature_manifest.json",
        "schema_plan.json",
        "load_report.json validation passed",
      ]),
      source_job_id: input.job_id,
    },
    {
      fact_id: `entity:${input.feature_slug}:primary_entity`,
      fact_type: "entity",
      subject: input.feature_slug,
      predicate: "primary_entity",
      object: input.primary_entity,
      confidence: 1,
      evidence_json: JSON.stringify([
        "feature_manifest.json",
        "event_profile.json",
        "load_report.json validation passed",
      ]),
      source_job_id: input.job_id,
    },
  ]);

  await writeSchemaMemory({
    ...input,
    table_name: bareOrAsIs(input.table_name),
  });
  await detectAndWriteContextGaps(input);

  return readGeneratedContext();
}

function bareOrAsIs(tableName: string) {
  return tableName.includes(".")
    ? tableName.split(".").slice(1).join(".")
    : tableName;
}

export async function ingestBaseContextDocuments(input: {
  repoRoot: string;
  jobId: string;
  baseContext: string;
  existingDdl: string;
  instrumentationNotes: string;
}) {
  const rows = [
    {
      doc_id: "base_context",
      doc_type: "business_context",
      source_path: path.join(input.repoRoot, "base_context.md"),
      content: input.baseContext,
      content_hash: hash(input.baseContext),
      job_id: input.jobId,
    },
    {
      doc_id: "existing_ddl",
      doc_type: "schema_context",
      source_path: path.join(input.repoRoot, "data", "ddl.sql"),
      content: input.existingDdl,
      content_hash: hash(input.existingDdl),
      job_id: input.jobId,
    },
    {
      doc_id: "instrumentation_notes",
      doc_type: "instrumentation_context",
      source_path: path.join(
        input.repoRoot,
        "data",
        "instrumentation_notes.md",
      ),
      content: input.instrumentationNotes,
      content_hash: hash(input.instrumentationNotes),
      job_id: input.jobId,
    },
  ];

  await insertJsonRows("context.context_documents", rows);

  await insertJsonRows(
    "context.contradictions",
    emptyRegistry.contradictions.map((contradiction) => ({
      ...contradiction,
      status: "open",
    })),
  );

  await insertJsonRows(
    "context.fact_registry",
    buildKnownIssueFacts(input.jobId),
  );

  await writeBaseSchemaMemory({
    jobId: input.jobId,
    existingDdl: input.existingDdl,
  });
}

async function writeSchemaMemory(input: UpdateGeneratedContextInput) {
  const fullTableName = `silver.${input.table_name}`;
  const fieldProfiles = new Map(
    input.event_profile.fields.map((field) => [field.path, field]),
  );
  const columns = input.schema_plan.columns.map((column) => {
    const field = column.source_path
      ? fieldProfiles.get(column.source_path)
      : null;
    return {
      feature_slug: input.feature_slug,
      table_name: fullTableName,
      column_name: column.name,
      clickhouse_type: column.type,
      source_path: column.source_path ?? "",
      semantic_role: semanticRoleForColumn(column.name, column.type),
      is_nullable: column.type.startsWith("Nullable(") ? 1 : 0,
      sample_values_json: JSON.stringify(field?.sample_values ?? []),
      reason: column.reason,
      confidence: field || !column.source_path ? 1 : 0.7,
      source_job_id: input.job_id,
    };
  });

  await insertJsonRows("context.column_registry", columns);

  const primaryEntityColumn = resolveContextPrimaryEntityColumn(
    input.primary_entity,
    input.schema_plan.columns.map((column) => column.name),
  );
  const segmentColumns = input.schema_plan.columns
    .filter(
      (column) =>
        semanticRoleForColumn(column.name, column.type) === "dimension",
    )
    .map((column) => column.name);

  await insertJsonRows("context.workflow_registry", [
    {
      feature_slug: input.feature_slug,
      table_name: fullTableName,
      workflow_type: input.workflow_type,
      ordered_events_json: JSON.stringify(input.event_names),
      start_event: input.event_names[0] ?? "",
      success_event: input.success_event ?? "",
      primary_entity: input.primary_entity,
      primary_entity_column: primaryEntityColumn,
      segment_columns_json: JSON.stringify(segmentColumns),
      source_job_id: input.job_id,
    },
  ]);

  const metrics = buildMetricMemory({
    featureSlug: input.feature_slug,
    tableName: fullTableName,
    metricHints: input.metric_hints,
    eventNames: input.event_names,
    successEvent: input.success_event,
    primaryEntityColumn,
    segmentColumns,
    jobId: input.job_id,
  });
  await insertJsonRows("context.metric_registry", metrics);

  await insertJsonRows(
    "context.join_registry",
    buildJoinMemory({
      tableName: fullTableName,
      columns: input.schema_plan.columns.map((column) => column.name),
      jobId: input.job_id,
    }),
  );

  await insertJsonRows("context.schema_quality_registry", [
    {
      feature_slug: input.feature_slug,
      table_name: fullTableName,
      engine: input.schema_plan.engine,
      partition_by: input.schema_plan.partition_by,
      order_by_json: JSON.stringify(input.schema_plan.order_by),
      ttl: input.schema_plan.ttl,
      materialized_views_json: JSON.stringify(
        input.schema_plan.materialized_views.map((view) => view.name),
      ),
      validation_json: JSON.stringify(input.validation),
      validation_passed: Boolean(
        (input.validation as { passed?: unknown }).passed,
      )
        ? 1
        : 0,
      source_job_id: input.job_id,
    },
  ]);
}

async function writeBaseSchemaMemory(input: {
  jobId: string;
  existingDdl: string;
}) {
  const tables = parseCreateTables(input.existingDdl);
  const columnRows = tables.flatMap((table) =>
    table.columns.map((column) => ({
      feature_slug: "base_context",
      table_name: table.name,
      column_name: column.name,
      clickhouse_type: column.type,
      source_path: column.name,
      semantic_role: semanticRoleForColumn(column.name, column.type),
      is_nullable: column.type.startsWith("Nullable(") ? 1 : 0,
      sample_values_json: "[]",
      reason: "Parsed from data/ddl.sql during context bootstrap.",
      confidence: 1,
      source_job_id: input.jobId,
    })),
  );
  await insertJsonRows("context.column_registry", columnRows);

  await insertJsonRows(
    "context.join_registry",
    tables.flatMap((table) =>
      buildJoinMemory({
        tableName: table.name,
        columns: table.columns.map((column) => column.name),
        jobId: input.jobId,
      }),
    ),
  );

  await insertJsonRows("context.workflow_registry", [
    {
      feature_slug: "base_conversion_funnel",
      table_name:
        "destination_card_clicked|application_started|document_uploaded|purchase_completed",
      workflow_type: "funnel",
      ordered_events_json: JSON.stringify([
        "destination_card_clicked",
        "application_started",
        "document_uploaded",
        "purchase_completed",
      ]),
      start_event: "destination_card_clicked",
      success_event: "purchase_completed",
      primary_entity: "application",
      primary_entity_column: "application_id",
      segment_columns_json: JSON.stringify([
        "device_type",
        "os",
        "geoip_country_code",
        "destination",
        "citizenship",
      ]),
      source_job_id: input.jobId,
    },
  ]);

  await insertJsonRows("context.metric_registry", [
    {
      metric_id: "base:funnel_conversion",
      feature_slug: "base_conversion_funnel",
      metric_name: "funnel_conversion_rate",
      formula_sql:
        "uniq(purchase_completed.user_id) / nullIf(uniq(application_started.user_id), 0)",
      numerator_definition: "distinct users with purchase_completed",
      denominator_definition: "distinct users with application_started",
      grain: "user",
      required_tables_json: JSON.stringify([
        "application_started",
        "purchase_completed",
      ]),
      segment_columns_json: JSON.stringify([
        "device_type",
        "os",
        "geoip_country_code",
        "destination",
      ]),
      caveats:
        "Use for funnel dashboards; leadership conversion may use sessions instead.",
      confidence: 0.9,
      source_job_id: input.jobId,
    },
    {
      metric_id: "base:passport_capture_pass_rate",
      feature_slug: "base_conversion_funnel",
      metric_name: "passport_capture_pass_rate",
      formula_sql:
        "countIf(is_crossed_failed_attempt_threshold = 0) / nullIf(count(), 0) FROM document_uploaded",
      numerator_definition:
        "document uploads without crossed failed-attempt threshold",
      denominator_definition: "all document uploads",
      grain: "event",
      required_tables_json: JSON.stringify(["document_uploaded"]),
      segment_columns_json: JSON.stringify([
        "device_type",
        "os",
        "destination",
      ]),
      caveats:
        "Base context links this to passport capture quality; validate device cuts before conclusions.",
      confidence: 0.9,
      source_job_id: input.jobId,
    },
    {
      metric_id: "base:revenue_per_conversion",
      feature_slug: "base_conversion_funnel",
      metric_name: "revenue_per_conversion",
      formula_sql: "avg(value) FROM purchase_completed",
      numerator_definition: "purchase_completed.value",
      denominator_definition: "converted purchases",
      grain: "purchase",
      required_tables_json: JSON.stringify(["purchase_completed"]),
      segment_columns_json: JSON.stringify(["currency", "destination"]),
      caveats:
        "Values are event currency amounts; normalize currency before cross-currency comparisons.",
      confidence: 0.85,
      source_job_id: input.jobId,
    },
  ]);
}

function hash(content: string) {
  return createHash("sha256").update(content).digest("hex");
}

function semanticRoleForColumn(columnName: string, clickhouseType: string) {
  if (["job_id", "ingested_at"].includes(columnName)) {
    return "operational";
  }
  if (columnName === "raw_json") {
    return "raw_payload";
  }
  if (columnName === "event_name") {
    return "event_name";
  }
  if (columnName === "timestamp" || columnName.endsWith("_at")) {
    return "timestamp";
  }
  if (columnName === "event_id" || columnName.endsWith("_id")) {
    return "entity_id";
  }
  if (
    /(amount|value|rate|price|revenue|latency|duration|count|attempts|depth|time)/i.test(
      columnName,
    )
  ) {
    return "metric_value";
  }
  if (clickhouseType.includes("Bool") || columnName.startsWith("is_")) {
    return "boolean_flag";
  }
  if (
    /(currency|country|city|destination|device|os|version|channel|method|type|source|flow|status|step)/i.test(
      columnName,
    )
  ) {
    return "dimension";
  }
  return clickhouseType.includes("String") ? "dimension" : "metric_value";
}

function resolveContextPrimaryEntityColumn(
  primaryEntity: string,
  columnNames: string[],
) {
  const names = new Set(columnNames);
  const normalized = primaryEntity.replace(/[^a-zA-Z0-9]+/g, "_");
  if (names.has(normalized)) {
    return normalized;
  }
  if (names.has(`${normalized}_id`)) {
    return `${normalized}_id`;
  }
  if (names.has("application_id")) {
    return "application_id";
  }
  return names.has("user_id") ? "user_id" : "";
}

function buildMetricMemory(input: {
  featureSlug: string;
  tableName: string;
  metricHints: string[];
  eventNames: string[];
  successEvent: string | null;
  primaryEntityColumn: string;
  segmentColumns: string[];
  jobId: string;
}) {
  const startEvent = input.eventNames[0] ?? "";
  const successEvent = input.successEvent ?? input.eventNames.at(-1) ?? "";
  const metrics = input.metricHints.map((hint) => ({
    metric_id: `${input.featureSlug}:${slugify(hint)}`,
    feature_slug: input.featureSlug,
    metric_name: hint,
    formula_sql: metricFormulaSql({
      tableName: input.tableName,
      metricName: hint,
      startEvent,
      successEvent,
      primaryEntityColumn: input.primaryEntityColumn,
    }),
    numerator_definition: successEvent
      ? `${input.primaryEntityColumn} reaching ${successEvent}`
      : "feature-specific numerator",
    denominator_definition: startEvent
      ? `${input.primaryEntityColumn} reaching ${startEvent}`
      : "feature-specific denominator",
    grain: input.primaryEntityColumn || "event",
    required_tables_json: JSON.stringify([input.tableName]),
    segment_columns_json: JSON.stringify(input.segmentColumns),
    caveats:
      "Generated from feature metric hints; analytics agent should verify exact denominator against the user question.",
    confidence: 0.75,
    source_job_id: input.jobId,
  }));

  if (startEvent && successEvent && input.primaryEntityColumn) {
    metrics.unshift({
      metric_id: `${input.featureSlug}:primary_conversion`,
      feature_slug: input.featureSlug,
      metric_name: `${startEvent}_to_${successEvent}_conversion`,
      formula_sql: metricFormulaSql({
        tableName: input.tableName,
        metricName: "conversion",
        startEvent,
        successEvent,
        primaryEntityColumn: input.primaryEntityColumn,
      }),
      numerator_definition: `${input.primaryEntityColumn} reaching ${successEvent}`,
      denominator_definition: `${input.primaryEntityColumn} reaching ${startEvent}`,
      grain: input.primaryEntityColumn,
      required_tables_json: JSON.stringify([input.tableName]),
      segment_columns_json: JSON.stringify(input.segmentColumns),
      caveats:
        "Primary feature conversion metric generated from ordered feature events.",
      confidence: 0.9,
      source_job_id: input.jobId,
    });
  }

  return metrics;
}

function metricFormulaSql(input: {
  tableName: string;
  metricName: string;
  startEvent: string;
  successEvent: string;
  primaryEntityColumn: string;
}) {
  if (!input.startEvent || !input.successEvent || !input.primaryEntityColumn) {
    return `-- Metric '${input.metricName}' requires feature-specific SQL.`;
  }
  return `uniqIf(${input.primaryEntityColumn}, event_name = '${input.successEvent}') / nullIf(uniqIf(${input.primaryEntityColumn}, event_name = '${input.startEvent}'), 0) FROM ${input.tableName}`;
}

function buildJoinMemory(input: {
  tableName: string;
  columns: string[];
  jobId: string;
}) {
  const joins = [];
  const leftTable = qualifyFeatureTable(input.tableName);
  const isBase = !leftTable.startsWith("silver.");

  // Explicit edges to every base event table when join keys exist.
  // This is what lets analytics reason about feature uplift vs baseline funnel.
  if (input.columns.includes("user_id")) {
    for (const baseTable of [
      ...BASE_FUNNEL_TABLES,
      ...BASE_SUPPORTING_TABLES,
    ]) {
      if (bareOrAsIs(leftTable) === baseTable) {
        continue;
      }
      joins.push({
        join_id: `${leftTable}:user_id:${baseTable}`,
        left_table: leftTable,
        left_column: "user_id",
        right_table: baseTable,
        right_column: "user_id",
        join_type: "entity",
        grain: "user",
        confidence: 0.95,
        evidence:
          "Base context join map: user_id is present on every Atlys event stream.",
        source_job_id: input.jobId,
      });
    }
  }

  if (input.columns.includes("application_id")) {
    const applicationTables = [
      "application_started",
      "document_uploaded",
      "pay_now_clicked",
      "purchase_completed",
    ] as const;
    for (const baseTable of applicationTables) {
      if (bareOrAsIs(leftTable) === baseTable) {
        continue;
      }
      joins.push({
        join_id: `${leftTable}:application_id:${baseTable}`,
        left_table: leftTable,
        left_column: "application_id",
        right_table: baseTable,
        right_column: "application_id",
        join_type: "entity",
        grain: "application",
        confidence: 0.95,
        evidence:
          "Base context join map: application_id links application_started and downstream funnel tables.",
        source_job_id: input.jobId,
      });
    }
  }

  // Cross-feature silver joins stay wildcard only as a fallback note.
  if (!isBase && input.columns.includes("user_id")) {
    joins.push({
      join_id: `${leftTable}:user_id:silver_features`,
      left_table: leftTable,
      left_column: "user_id",
      right_table: "silver.*",
      right_column: "user_id",
      join_type: "entity",
      grain: "user",
      confidence: 0.7,
      evidence:
        "Generated Silver feature tables share user_id when present; verify column existence before joining.",
      source_job_id: input.jobId,
    });
  }

  return joins;
}

function parseCreateTables(ddl: string) {
  const tables: Array<{
    name: string;
    columns: Array<{ name: string; type: string }>;
  }> = [];
  const tableRegex =
    /CREATE TABLE\s+([a-zA-Z0-9_]+)\s*\(([\s\S]*?)\)\s*ENGINE/g;
  for (const match of ddl.matchAll(tableRegex)) {
    const [, name, body] = match;
    const columns = body
      .split("\n")
      .map((line) => line.trim().replace(/,$/, ""))
      .filter(Boolean)
      .map((line) => {
        const columnMatch = line.match(/^([a-zA-Z0-9_]+)\s+(.+)$/);
        if (!columnMatch) {
          return null;
        }
        return { name: columnMatch[1], type: columnMatch[2] };
      })
      .filter((column): column is { name: string; type: string } =>
        Boolean(column),
      );
    tables.push({ name, columns });
  }
  return tables;
}
