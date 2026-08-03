/**
 * Shared warehouse table catalog helpers.
 * Base funnel tables live in the app ClickHouse database (default schema_kings).
 * Generated feature tables live in silver/gold.
 */

export const BASE_FUNNEL_TABLES = [
  "destination_card_clicked",
  "application_started",
  "document_uploaded",
  "purchase_completed",
] as const;

export const BASE_SUPPORTING_TABLES = [
  "search_typed",
  "landing_page_scrolled",
  "auth_completed",
  "pay_now_clicked",
] as const;

export const BASE_EVENT_TABLES = [
  ...BASE_FUNNEL_TABLES,
  ...BASE_SUPPORTING_TABLES,
] as const;

export const ANALYTICS_DATABASES = [
  "silver",
  "gold",
  "context",
  "schema_kings",
  "default",
] as const;

/** Qualify a bare feature table name as silver.<name>. Leave already-qualified names alone. */
export function qualifyFeatureTable(tableName: string): string {
  const trimmed = tableName.trim();
  if (!trimmed) {
    return trimmed;
  }
  if (trimmed.includes(".")) {
    return trimmed;
  }
  if ((BASE_EVENT_TABLES as readonly string[]).includes(trimmed)) {
    return trimmed;
  }
  return `silver.${trimmed}`;
}

/** Bare table name without database prefix. */
export function bareTableName(tableName: string): string {
  const parts = tableName.split(".");
  return parts[parts.length - 1] ?? tableName;
}

/** True when the table is one of the 8 pre-existing Atlys event tables. */
export function isBaseEventTable(tableName: string): boolean {
  return (BASE_EVENT_TABLES as readonly string[]).includes(
    bareTableName(tableName),
  );
}

/** Tables that should always be available for baseline / cross-feature analytics. */
export function baseTablesForAnalytics(): string[] {
  return [...BASE_EVENT_TABLES];
}
