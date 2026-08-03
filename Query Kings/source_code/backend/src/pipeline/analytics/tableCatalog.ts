import {
  BASE_EVENT_TABLES,
  bareTableName,
  qualifyFeatureTable,
} from "../warehouseTables.js";
import { PmRelevantContext } from "./types.js";
import { unique } from "./utils.js";

/** Known analytics tables from context + base funnel (never invents feature tables). */
export function knownAnalyticsTables(context: PmRelevantContext): string[] {
  const fromContext = [
    ...context.features.map((feature) => feature.table_name),
    ...context.workflows.flatMap((workflow) =>
      workflow.table_name.includes("|")
        ? workflow.table_name.split("|")
        : [workflow.table_name],
    ),
    ...context.columns.map((column) => column.table_name),
    ...context.schema_quality.map((quality) => quality.table_name),
    ...context.joins.flatMap((join) => [join.left_table, join.right_table]),
  ];

  return unique(
    [...fromContext, ...BASE_EVENT_TABLES]
      .filter(Boolean)
      .filter((table) => !table.includes("*"))
      .map((table) =>
        table.includes("|") ? table : qualifyFeatureTable(table),
      )
      .filter((table) => !table.includes("|")),
  );
}

export function isKnownAnalyticsTable(
  tableName: string,
  knownTables: Iterable<string>,
): boolean {
  const qualified = qualifyFeatureTable(tableName);
  const bare = bareTableName(tableName);
  const known = new Set(
    Array.from(knownTables).flatMap((table) => [
      table,
      bareTableName(table),
      qualifyFeatureTable(table),
    ]),
  );
  return known.has(tableName) || known.has(qualified) || known.has(bare);
}

/** Drop invented tables; keep only catalog-grounded names. */
export function clampTablesToCatalog(
  tables: string[],
  context: PmRelevantContext,
): string[] {
  const known = knownAnalyticsTables(context);
  return unique(
    tables
      .map((table) => qualifyFeatureTable(table))
      .filter((table) => isKnownAnalyticsTable(table, known)),
  );
}

/** Filter LLM table_hints to names that exist in the catalog (or base tables). */
export function clampTableHints(
  tableHints: string[],
  context?: PmRelevantContext,
): string[] {
  const base = new Set<string>(BASE_EVENT_TABLES as unknown as string[]);
  const known = context
    ? new Set(
        knownAnalyticsTables(context).flatMap((table) => [
          table,
          bareTableName(table),
        ]),
      )
    : base;

  return unique(
    tableHints
      .map((hint) => hint.trim())
      .filter(Boolean)
      .filter((hint) => {
        const bare = bareTableName(hint);
        const qualified = qualifyFeatureTable(hint);
        // Reject obvious invented names
        if (
          /^(user_sessions|checkout_events|checkout_sessions|sessions|events|logs)$/i.test(
            bare,
          )
        ) {
          return false;
        }
        if (!context) {
          // Without context yet, only keep base tables or *_events that look like features
          return base.has(bare) || /_events$/.test(bare);
        }
        return (
          known.has(hint) ||
          known.has(bare) ||
          known.has(qualified) ||
          base.has(bare)
        );
      }),
  );
}

export function goldMvCandidates(featureTable: string): string[] {
  const bare = bareTableName(featureTable).replace(/^silver\./, "");
  const stem = bare.endsWith("_events") ? bare : `${bare}`;
  return [
    `gold.${stem}_daily_event_counts`,
    `gold.${stem}_daily_conversion`,
    `gold.${stem}_segment_success`,
    `gold.${stem}_latency_by_event`,
  ];
}
