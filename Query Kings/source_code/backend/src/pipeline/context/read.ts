import { queryClickHouseText } from "../clickhouse.js";
import { qualifyFeatureTable } from "../warehouseTables.js";
import { emptyRegistry, GeneratedContextRegistry } from "./types.js";
import { ensureContextTables } from "./tables.js";
import { parseJsonArray } from "./utils.js";

export async function readGeneratedContext(): Promise<GeneratedContextRegistry> {
  await ensureContextTables();
  // LIMIT 1 BY keeps the newest row per key without nested aggregates.
  const featuresRaw = (
    await queryClickHouseText(`
SELECT
  feature_slug,
  table_name,
  primary_entity,
  event_names_json,
  success_event,
  metric_hints_json,
  toString(updated_at)
FROM context.feature_registry
ORDER BY feature_slug ASC, updated_at DESC
LIMIT 1 BY feature_slug
FORMAT TabSeparated
`)
  ).trim();

  const contradictionsRaw = (
    await queryClickHouseText(`
SELECT id, summary, evidence
FROM context.contradictions
WHERE status = 'open'
ORDER BY id ASC, detected_at DESC
LIMIT 1 BY id
FORMAT TabSeparated
`)
  ).trim();

  const columnsRaw = (
    await queryClickHouseText(`
SELECT
  table_name,
  column_name,
  clickhouse_type,
  source_path,
  semantic_role,
  is_nullable
FROM context.column_registry
ORDER BY table_name ASC, column_name ASC, updated_at DESC
LIMIT 1 BY table_name, column_name
LIMIT 500
FORMAT TabSeparated
`)
  ).trim();

  const workflowsRaw = (
    await queryClickHouseText(`
SELECT
  feature_slug,
  table_name,
  workflow_type,
  start_event,
  success_event,
  primary_entity,
  primary_entity_column,
  segment_columns_json
FROM context.workflow_registry
ORDER BY feature_slug ASC, updated_at DESC
LIMIT 1 BY feature_slug
LIMIT 50
FORMAT TabSeparated
`)
  ).trim();

  const metricsRaw = (
    await queryClickHouseText(`
SELECT
  metric_name,
  feature_slug,
  formula_sql,
  grain,
  segment_columns_json
FROM context.metric_registry
ORDER BY feature_slug ASC, metric_name ASC, updated_at DESC
LIMIT 1 BY metric_name, feature_slug
LIMIT 100
FORMAT TabSeparated
`)
  ).trim();

  const joinsRaw = (
    await queryClickHouseText(`
SELECT
  left_table,
  left_column,
  right_table,
  right_column,
  grain,
  confidence
FROM context.join_registry
ORDER BY left_table ASC, right_table ASC, updated_at DESC
LIMIT 1 BY left_table, left_column, right_table, right_column
LIMIT 100
FORMAT TabSeparated
`)
  ).trim();

  const qualityRaw = (
    await queryClickHouseText(`
SELECT
  table_name,
  order_by_json,
  partition_by,
  ttl,
  materialized_views_json,
  validation_passed
FROM context.schema_quality_registry
ORDER BY table_name ASC, updated_at DESC
LIMIT 1 BY table_name
LIMIT 100
FORMAT TabSeparated
`)
  ).trim();

  return {
    version: 1,
    updated_at: new Date().toISOString(),
    features: featuresRaw
      ? featuresRaw.split("\n").map((line) => {
          const [
            feature_slug,
            table_name,
            primary_entity,
            event_names_json,
            success_event,
            metric_hints_json,
            added_at,
          ] = line.split("\t");
          return {
            feature_slug,
            table_name: qualifyFeatureTable(table_name),
            primary_entity,
            event_names: parseJsonArray(event_names_json),
            success_event: success_event || null,
            metric_hints: parseJsonArray(metric_hints_json),
            added_at,
          };
        })
      : [],
    contradictions: contradictionsRaw
      ? contradictionsRaw.split("\n").map((line) => {
          const [id, summary, evidence] = line.split("\t");
          return { id, summary, evidence };
        })
      : emptyRegistry.contradictions,
    columns: columnsRaw
      ? columnsRaw.split("\n").map((line) => {
          const [
            table_name,
            column_name,
            clickhouse_type,
            source_path,
            semantic_role,
            is_nullable,
          ] = line.split("\t");
          return {
            table_name: normalizeRegistryTableName(table_name),
            column_name,
            clickhouse_type,
            source_path: source_path || null,
            semantic_role,
            is_nullable: is_nullable === "1",
          };
        })
      : [],
    workflows: workflowsRaw
      ? workflowsRaw.split("\n").map((line) => {
          const [
            feature_slug,
            table_name,
            workflow_type,
            start_event,
            success_event,
            primary_entity,
            primary_entity_column,
            segment_columns_json,
          ] = line.split("\t");
          return {
            feature_slug,
            table_name: normalizeRegistryTableName(table_name),
            workflow_type,
            start_event: start_event || null,
            success_event: success_event || null,
            primary_entity,
            primary_entity_column,
            segment_columns: parseJsonArray(segment_columns_json),
          };
        })
      : [],
    metrics: metricsRaw
      ? metricsRaw.split("\n").map((line) => {
          const [
            metric_name,
            feature_slug,
            formula_sql,
            grain,
            segment_columns_json,
          ] = line.split("\t");
          return {
            metric_name,
            feature_slug,
            formula_sql,
            grain,
            segment_columns: parseJsonArray(segment_columns_json),
          };
        })
      : [],
    joins: joinsRaw
      ? joinsRaw.split("\n").map((line) => {
          const [
            left_table,
            left_column,
            right_table,
            right_column,
            grain,
            confidence,
          ] = line.split("\t");
          return {
            left_table: normalizeRegistryTableName(left_table),
            left_column,
            right_table: normalizeRegistryTableName(right_table),
            right_column,
            grain,
            confidence: Number(confidence),
          };
        })
      : [],
    schema_quality: qualityRaw
      ? qualityRaw.split("\n").map((line) => {
          const [
            table_name,
            order_by_json,
            partition_by,
            ttl,
            materialized_views_json,
            validation_passed,
          ] = line.split("\t");
          return {
            table_name: normalizeRegistryTableName(table_name),
            order_by: parseJsonArray(order_by_json),
            partition_by,
            ttl,
            materialized_views: parseJsonArray(materialized_views_json),
            validation_passed: validation_passed === "1",
          };
        })
      : [],
  };
}

/** Qualify feature tables; leave multi-table workflow markers and base tables alone. */
function normalizeRegistryTableName(tableName: string) {
  if (!tableName || tableName.includes("|") || tableName.includes("*")) {
    return tableName;
  }
  return qualifyFeatureTable(tableName);
}
