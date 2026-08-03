import { startActiveObservation } from "@langfuse/tracing";
import { callGroqJson } from "../groq.js";
import { writeStageJson } from "../instrumentation/artifacts.js";
import { bareTableName, qualifyFeatureTable } from "../warehouseTables.js";
import { recordPipelineStage } from "../tracking.js";
import { AnalyticsStrictFailure } from "./graceful.js";
import { analyticsTrackingEvents } from "./trackingEvents.js";
import {
  AnalysisPlan,
  GeneratedSqlQuery,
  PmRelevantContext,
  QueryIntent,
} from "./types.js";
import {
  compactJson,
  getClickHouseColumns,
  getKnownClickHouseTables,
  groundSqlTableNames,
  unique,
} from "./utils.js";

export async function runSqlGenerator(input: {
  jobId: string;
  question: string;
  intent: QueryIntent;
  context: PmRelevantContext;
  plan: AnalysisPlan;
  artifactRoot: string;
  executionFeedback?: string[];
}): Promise<GeneratedSqlQuery[]> {
  const event = analyticsTrackingEvents.sqlGenerator;
  return startActiveObservation(event.stageId, async (span) => {
    span.update({
      input: {
        question: input.question,
        plan: input.plan,
        execution_feedback: input.executionFeedback ?? [],
      },
      metadata: { agent: "analytics_sql_generator" },
    });

    const catalog = buildSqlCatalog(input.context, input.plan);
    const liveTables = await getKnownClickHouseTables();
    const allowedTables = unique([
      ...catalog.tables,
      ...liveTables.filter(
        (table) =>
          table.startsWith("silver.") ||
          table.startsWith("gold.") ||
          table.startsWith("context.") ||
          !table.includes(".") ||
          table.includes("destination_card") ||
          table.includes("application_started") ||
          table.includes("document_uploaded") ||
          table.includes("purchase_completed") ||
          table.includes("pay_now") ||
          table.includes("search_typed") ||
          table.includes("landing_page") ||
          table.includes("auth_completed"),
      ),
    ]);
    const liveColumns = await getClickHouseColumns(allowedTables);
    const columnsByTable = mergeColumnsByTable(
      catalog.columnsByTable,
      liveColumns,
    );

    let llmQueries: { queries: GeneratedSqlQuery[] } | null = null;
    try {
      llmQueries = await callGroqJson<{ queries: GeneratedSqlQuery[] }>({
        modelRole: "sql",
        traceName: "groq.analytics.sql_generator",
        temperature: 0,
        maxTokens: 2200,
        traceInput: {
          question: input.question,
          query_count: input.plan.queries.length,
          execution_feedback: input.executionFeedback ?? [],
          allowed_tables: allowedTables.slice(0, 40),
        },
        messages: [
          {
            role: "system",
            content:
              "You generate ClickHouse SELECT SQL for analytics. Return JSON only. SQL must be read-only and must not include FORMAT or semicolons. NEVER invent table or column names. If you cannot write valid SQL for a planned id using only allowed tables/columns, omit that query rather than guessing.",
          },
          {
            role: "user",
            content: `Question:
${input.question}

Intent:
${compactJson(input.intent)}

Plan:
${compactJson(input.plan)}

ALLOWED TABLES (use only these exact names):
${allowedTables.map((table) => `- ${table}`).join("\n") || "- (none — return empty queries)"}

ALLOWED COLUMNS BY TABLE:
${compactJson(columnsByTable, 16000)}

KNOWN JOINS:
${compactJson(catalog.joins, 4000)}

METRIC SQL SKETCHES (adapt, do not invent tables):
${compactJson(catalog.metrics, 4000)}

Relevant context notes / contradictions / known issues:
${compactJson(
  {
    contradictions: input.context.contradictions,
    retrieval_notes: input.context.retrieval_notes,
  },
  6000,
)}

Prior execution feedback:
${compactJson(input.executionFeedback ?? [])}

Return:
{
  "queries": [
    {
      "id": string,
      "purpose": string,
      "sql_intent": string,
      "expected_columns": string[],
      "priority": "required" | "nice_to_have",
      "sql": string
    }
  ]
}

Rules:
- Only SELECT/WITH queries.
- Prefer returning SQL for every planned query id, but NEVER invent tables/columns.
- Use ONLY exact table names from ALLOWED TABLES.
- Feature event names live in event_name for silver tables. Base tables are one event per table.
- For funnel drop-off, use workflow event order (not alphabetical event_name joins).
- For conditional unique counts, use uniqExactIf(entity_column, condition).
- Limit exploratory result sets to at most 100 rows.
- Prefer gold.* target tables (not *_mv view names) for counts/conversion/segments when listed. Example: gold.<feature>_events_daily_event_counts, gold.<feature>_events_daily_conversion, gold.<feature>_events_segment_success.
- Aggregate Gold with sum() because SummingMergeTree targets may need merging of parts.
- If allowed tables are empty, return {"queries":[]}.`,
          },
        ],
      });
    } catch (error) {
      // Strict: do not invent SQL. Deterministic primitives will still run.
      span.update({
        metadata: {
          llm_failed: true,
          error: error instanceof Error ? error.message : String(error),
        },
      });
      llmQueries = { queries: [] };
    }

    if (!llmQueries || !Array.isArray(llmQueries.queries)) {
      throw new AnalyticsStrictFailure(
        event.stageId,
        "SQL generator returned an unusable queries payload.",
      );
    }

    const generated = repairGeneratedQueries(
      llmQueries.queries,
      input.plan,
      allowedTables,
    );

    await writeStageJson(
      input.artifactRoot,
      event.stageId,
      "sql_queries.json",
      {
        queries: generated,
        allowed_tables: allowedTables,
        omitted_planned_ids: input.plan.queries
          .map((query) => query.id)
          .filter((id) => !generated.some((query) => query.id === id)),
      },
    );
    await recordPipelineStage({
      jobId: input.jobId,
      stageId: event.stageId,
      stageName: event.stageName,
      status: "completed",
      stageInput: { plan: input.plan },
      stageOutput: {
        queries: generated,
        allowed_tables: allowedTables,
      },
    });
    span.update({
      output: {
        queries: generated,
        allowed_tables: allowedTables,
      },
    });
    return generated;
  });
}

function buildSqlCatalog(context: PmRelevantContext, plan: AnalysisPlan) {
  const tables = unique(
    [
      ...plan.tables,
      ...context.features.map((feature) => feature.table_name),
      ...context.workflows.map((workflow) => workflow.table_name),
      ...context.columns.map((column) => column.table_name),
      ...context.joins.flatMap((join) => [join.left_table, join.right_table]),
      "context.metric_registry",
      "context.column_registry",
      "context.feature_registry",
    ]
      .filter(Boolean)
      .filter((table) => !table.includes("|") && !table.includes("*"))
      .map((table) => qualifyFeatureTable(table)),
  );

  const columnsByTable: Record<string, string[]> = {};
  for (const column of context.columns) {
    const table = qualifyFeatureTable(column.table_name);
    if (
      !tables.some(
        (candidate) => bareTableName(candidate) === bareTableName(table),
      )
    ) {
      continue;
    }
    const key =
      tables.find(
        (candidate) => bareTableName(candidate) === bareTableName(table),
      ) ?? table;
    columnsByTable[key] ??= [];
    if (!columnsByTable[key].includes(column.column_name)) {
      columnsByTable[key].push(column.column_name);
    }
  }

  return {
    tables,
    columnsByTable,
    joins: context.joins.slice(0, 30),
    metrics: context.metrics.slice(0, 20),
  };
}

function mergeColumnsByTable(
  contextColumnsByTable: Record<string, string[]>,
  liveColumns: Array<{ table_name: string; column_name: string }>,
) {
  const columnsByTable: Record<string, string[]> = {};
  for (const [table, columns] of Object.entries(contextColumnsByTable)) {
    columnsByTable[table] = [...columns];
  }
  for (const column of liveColumns) {
    columnsByTable[column.table_name] ??= [];
    if (!columnsByTable[column.table_name].includes(column.column_name)) {
      columnsByTable[column.table_name].push(column.column_name);
    }
    // Also index by bare name for base tables
    const bare = bareTableName(column.table_name);
    columnsByTable[bare] ??= [];
    if (!columnsByTable[bare].includes(column.column_name)) {
      columnsByTable[bare].push(column.column_name);
    }
  }
  return columnsByTable;
}

/**
 * Strict repair:
 * - Keep only queries with real SQL from the LLM
 * - Ground table names against catalog
 * - Do NOT invent fallback SQL for missing planned ids
 *   (primitives cover the reliable backbone)
 */
function repairGeneratedQueries(
  queries: GeneratedSqlQuery[],
  plan: AnalysisPlan,
  catalogTables: string[],
): GeneratedSqlQuery[] {
  const byId = new Map(
    queries
      .filter((query) => query?.id && query.sql?.trim())
      .map((query) => [query.id, query]),
  );

  const repaired: GeneratedSqlQuery[] = [];
  for (const planned of plan.queries) {
    const generated = byId.get(planned.id);
    if (!generated?.sql?.trim()) {
      // Strict: omit rather than invent.
      continue;
    }
    const sql = groundSqlTableNames(generated.sql, catalogTables);
    if (!sql.trim()) {
      continue;
    }
    repaired.push({
      ...planned,
      purpose: generated.purpose || planned.purpose,
      sql_intent: generated.sql_intent || planned.sql_intent,
      expected_columns:
        generated.expected_columns?.length > 0
          ? generated.expected_columns
          : planned.expected_columns,
      priority: generated.priority || planned.priority,
      sql,
    });
  }

  // Extra LLM queries only if they ground cleanly.
  for (const query of queries) {
    if (!query?.id || !query.sql?.trim()) {
      continue;
    }
    if (repaired.some((item) => item.id === query.id)) {
      continue;
    }
    const sql = groundSqlTableNames(query.sql, catalogTables);
    if (sql.trim()) {
      repaired.push({ ...query, sql });
    }
  }

  return repaired;
}
