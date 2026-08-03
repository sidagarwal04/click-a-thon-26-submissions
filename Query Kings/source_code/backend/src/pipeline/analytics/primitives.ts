import { startActiveObservation } from "@langfuse/tracing";
import { sqlString } from "../clickhouse.js";
import {
  BASE_FUNNEL_TABLES,
  bareTableName,
  qualifyFeatureTable,
} from "../warehouseTables.js";
import { writeStageJson } from "../instrumentation/artifacts.js";
import { recordPipelineStage } from "../tracking.js";
import { goldMvCandidates } from "./tableCatalog.js";
import { analyticsTrackingEvents } from "./trackingEvents.js";
import {
  AnalysisPlan,
  GeneratedSqlQuery,
  PmRelevantContext,
  QueryIntent,
} from "./types.js";
import { unique } from "./utils.js";

type TableShape = {
  table: string;
  columns: Set<string>;
  workflow?: PmRelevantContext["workflows"][number];
  eventOrder: string[];
  isBaseTable: boolean;
  goldTables: {
    dailyEventCounts: string | null;
    dailyConversion: string | null;
    segmentSuccess: string | null;
    latency: string | null;
  };
};

export async function runAnalyticsPrimitives(input: {
  jobId: string;
  intent: QueryIntent;
  context: PmRelevantContext;
  plan: AnalysisPlan;
  artifactRoot: string;
}): Promise<GeneratedSqlQuery[]> {
  const event = analyticsTrackingEvents.analyticsPrimitives;
  return startActiveObservation(event.stageId, async (span) => {
    const queries = buildPrimitiveQueries(input);
    await writeStageJson(
      input.artifactRoot,
      event.stageId,
      "primitive_queries.json",
      {
        queries,
      },
    );
    await recordPipelineStage({
      jobId: input.jobId,
      stageId: event.stageId,
      stageName: event.stageName,
      status: "completed",
      stageInput: {
        requested_analyses: input.intent.requested_analyses,
        plan_tables: input.plan.tables,
      },
      stageOutput: {
        query_count: queries.length,
        query_ids: queries.map((query) => query.id),
      },
    });
    span.update({ output: { query_count: queries.length, queries } });
    return queries;
  });
}

function buildPrimitiveQueries(input: {
  intent: QueryIntent;
  context: PmRelevantContext;
  plan: AnalysisPlan;
}) {
  const shapes = resolveTableShapes(input.context, input.plan);
  const queries: GeneratedSqlQuery[] = [];
  const requested = new Set([
    ...input.intent.requested_analyses,
    input.plan.answer_type,
  ]);
  const baselineRelevant = isBaselineRelevantQuestion(
    input.intent.original_question,
  );

  // Unknown-feature schema questions should list catalog only — not dump random features.
  const unknownFeatureMode =
    input.plan.answer_type === "schema_explanation" &&
    input.plan.assumptions.some((item) =>
      /not found in context memory|unknown feature|will not attribute/i.test(
        item,
      ),
    );
  if (unknownFeatureMode) {
    queries.push({
      id: "primitive_list_instrumented_features",
      purpose: "List instrumented features currently in context memory.",
      sql_intent:
        "SELECT feature_slug, table_name FROM context.feature_registry FINAL GROUP BY feature_slug",
      expected_columns: ["feature_slug", "table_name"],
      priority: "required",
      sql: `
SELECT
  feature_slug,
  table_name
FROM context.feature_registry
ORDER BY feature_slug ASC, updated_at DESC
LIMIT 1 BY feature_slug
LIMIT 100`,
    });
    return queries;
  }

  if (isContextCatalogQuestion(input.intent, input.plan)) {
    queries.push(...contextCatalogPrimitives());
    return queries;
  }

  const hasFeatureShape = shapes.some((shape) => !shape.isBaseTable);
  const analysisShapes =
    hasFeatureShape && !baselineRelevant
      ? shapes.filter((shape) => !shape.isBaseTable)
      : shapes;

  for (const shape of analysisShapes.slice(0, 4)) {
    if (shape.isBaseTable) {
      // Base tables are one-event-per-table; different primitives.
      queries.push(baseTableOverview(shape));
      if (
        requested.has("segment_comparison") ||
        requested.has("root_cause") ||
        requested.has("open_ended")
      ) {
        const segment = pickSegmentColumn(shape);
        if (segment) {
          queries.push(baseSegmentVolume(shape, segment));
        }
      }
      continue;
    }

    const gold = goldPrimitivesForShape(shape, requested);
    queries.push(...gold.queries);

    // Prefer Gold MVs when present; keep a thin Silver fallback for DQ / ordered funnel.
    if (hasCoreEventColumns(shape) && !gold.covered.has("overview")) {
      queries.push(eventOverview(shape));
    }
    if (hasCoreEventColumns(shape) && hasEntity(shape)) {
      queries.push(dataQuality(shape));
    }
    if (
      requested.has("trend") ||
      requested.has("root_cause") ||
      requested.has("open_ended")
    ) {
      if (hasCoreEventColumns(shape) && !gold.covered.has("trend")) {
        queries.push(trendScan(shape));
        queries.push(anomalyScan(shape));
      }
    }
    if (
      requested.has("funnel") ||
      requested.has("root_cause") ||
      requested.has("open_ended") ||
      requested.has("metric_lookup")
    ) {
      if (hasCoreEventColumns(shape) && hasEntity(shape)) {
        if (!gold.covered.has("funnel")) {
          queries.push(funnelBreakdown(shape));
        }
        if (shape.eventOrder.length >= 2) {
          queries.push(orderedFunnelDropoff(shape));
        }
        if (
          shape.workflow?.start_event &&
          shape.workflow?.success_event &&
          !gold.covered.has("conversion")
        ) {
          queries.push(conversionRate(shape));
        }
      }
    }
    if (
      requested.has("segment_comparison") ||
      requested.has("root_cause") ||
      requested.has("open_ended")
    ) {
      const segment = pickSegmentColumn(shape, input.intent);
      if (
        segment &&
        hasCoreEventColumns(shape) &&
        hasEntity(shape) &&
        (!gold.covered.has("segment") ||
          isExplicitSegmentRequested(input.intent, segment))
      ) {
        queries.push(segmentComparison(shape, segment));
      }
    }
    if (requested.has("latency") || requested.has("open_ended")) {
      const latencyColumn = pickColumn(shape, [
        "latency",
        "duration",
        "time_on_page",
        "processing_time",
      ]);
      if (
        latencyColumn &&
        hasCoreEventColumns(shape) &&
        !gold.covered.has("latency")
      ) {
        queries.push(latencyDistribution(shape, latencyColumn));
      }
    }
    if (
      (requested.has("open_ended") || requested.has("root_cause")) &&
      !gold.covered.has("overview")
    ) {
      const numericPair = pickNumericPair(input.context, shape);
      if (numericPair) {
        queries.push(correlationScan(shape, numericPair[0], numericPair[1]));
      }
    }
  }

  // Cross-table base funnel primitive only when baseline context is asked for,
  // or when there is no feature table to answer from.
  if (baselineRelevant || (!hasFeatureShape && requested.has("funnel"))) {
    queries.push(baseFunnelPrimitive());
    queries.push(baseFunnelByDevicePrimitive());
  }

  // Feature ↔ baseline join when we have a silver feature table with user_id.
  const featureShape = shapes.find(
    (shape) => !shape.isBaseTable && shape.columns.has("user_id"),
  );
  if (featureShape && featureShape.workflow?.success_event) {
    queries.push(featureVsBaselineUplift(featureShape));
  }

  const seen = new Set<string>();
  return queries.filter((query) => {
    if (seen.has(query.id)) {
      return false;
    }
    seen.add(query.id);
    return true;
  });
}

function resolveTableShapes(
  context: PmRelevantContext,
  plan: AnalysisPlan,
): TableShape[] {
  const tables = unique([
    ...plan.tables.filter((table) => !table.startsWith("gold.")),
  ])
    .filter(Boolean)
    .map((table) => qualifyFeatureTable(table));

  return unique(tables)
    .filter(
      (table) => !table.startsWith("gold.") && !table.startsWith("context."),
    )
    .map((table) => {
      const qualified = qualifyFeatureTable(table);
      const bare = bareTableName(qualified);
      const isBaseTable =
        (BASE_FUNNEL_TABLES as readonly string[]).includes(bare) ||
        [
          "search_typed",
          "landing_page_scrolled",
          "auth_completed",
          "pay_now_clicked",
        ].includes(bare);

      const columns = new Set(
        context.columns
          .filter(
            (column) =>
              column.table_name === qualified ||
              column.table_name === bare ||
              bareTableName(column.table_name) === bare,
          )
          .map((column) => column.column_name),
      );

      const feature = context.features.find(
        (item) =>
          qualifyFeatureTable(item.table_name) === qualified ||
          bareTableName(item.table_name) === bare,
      );
      const workflow = context.workflows.find(
        (item) =>
          item.table_name === qualified ||
          item.table_name === bare ||
          bareTableName(item.table_name) === bare,
      );
      const eventOrder =
        feature?.event_names && feature.event_names.length > 0
          ? feature.event_names
          : [workflow?.start_event, workflow?.success_event].filter(
              (value): value is string => Boolean(value),
            );

      // Gold targets from instrumentation naming convention. Prefer ones present
      // in plan/schema_quality; otherwise still emit candidates (executor will
      // error only if missing — planner usually injects existing gold tables).
      // Gold target table names follow instrumentation conventions. Prefer when
      // plan/schema_quality mentions them; otherwise still use convention for
      // instrumented silver feature tables (MVs are created with every load).
      const candidates = isBaseTable ? [] : goldMvCandidates(qualified);
      const resolveGold = (suffix: string) =>
        candidates.find((candidate) => candidate.endsWith(suffix)) ?? null;

      return {
        table: isBaseTable ? bare : qualified,
        columns,
        workflow,
        eventOrder,
        isBaseTable,
        goldTables: {
          dailyEventCounts: resolveGold("_daily_event_counts"),
          dailyConversion: resolveGold("_daily_conversion"),
          segmentSuccess: resolveGold("_segment_success"),
          latency: resolveGold("_latency_by_event"),
        },
      };
    });
}

function isBaselineRelevantQuestion(question: string) {
  return /baseline|uplift|standard checkout|standard|versus standard|vs standard|base funnel|existing funnel|overall conversion|compared? to purchase|feature .* purchase|purchase overlap/i.test(
    question,
  );
}

function isContextCatalogQuestion(intent: QueryIntent, plan: AnalysisPlan) {
  const text = `${intent.original_question} ${intent.normalized_question}`;
  return (
    plan.answer_type === "schema_explanation" &&
    /tables?|events?|joins?|metrics?|known caveats?|available|instrumented feature specs/i.test(
      text,
    ) &&
    !plan.assumptions.some((item) =>
      /not found in context memory|unknown feature|will not attribute/i.test(
        item,
      ),
    )
  );
}

function contextCatalogPrimitives(): GeneratedSqlQuery[] {
  return [
    {
      id: "primitive_context_feature_catalog",
      purpose: "List instrumented features, tables, and event names.",
      sql_intent: "Read feature registry catalog from context memory.",
      expected_columns: ["feature_slug", "table_name", "event_names"],
      priority: "required",
      sql: `
SELECT
  feature_slug,
  table_name,
  event_names_json AS event_names
FROM context.feature_registry FINAL
ORDER BY feature_slug ASC, updated_at DESC
LIMIT 1 BY feature_slug
LIMIT 100`,
    },
    {
      id: "primitive_context_workflow_catalog",
      purpose: "List workflow start/success events and primary entities.",
      sql_intent: "Read workflow registry catalog from context memory.",
      expected_columns: [
        "feature_slug",
        "table_name",
        "start_event",
        "success_event",
        "primary_entity",
      ],
      priority: "required",
      sql: `
SELECT
  feature_slug,
  table_name,
  start_event,
  success_event,
  primary_entity
FROM context.workflow_registry
FINAL
ORDER BY feature_slug ASC, updated_at DESC
LIMIT 1 BY feature_slug
LIMIT 100`,
    },
    {
      id: "primitive_context_metric_catalog",
      purpose: "List generated metrics by feature.",
      sql_intent: "Read metric registry catalog from context memory.",
      expected_columns: ["feature_slug", "metric_name", "grain", "caveats"],
      priority: "required",
      sql: `
SELECT
  feature_slug,
  metric_name,
  grain,
  caveats
FROM context.metric_registry
FINAL
ORDER BY feature_slug ASC, metric_name ASC
LIMIT 200`,
    },
    {
      id: "primitive_context_join_catalog",
      purpose: "List generated join edges by feature.",
      sql_intent: "Read join registry catalog from context memory.",
      expected_columns: [
        "left_table",
        "left_column",
        "right_table",
        "right_column",
        "confidence",
      ],
      priority: "required",
      sql: `
SELECT
  left_table,
  left_column,
  right_table,
  right_column,
  confidence
FROM context.join_registry
FINAL
WHERE left_table LIKE 'silver.%' OR right_table LIKE 'silver.%'
ORDER BY left_table ASC, right_table ASC
LIMIT 200`,
    },
    {
      id: "primitive_context_caveat_catalog",
      purpose: "List open contradictions and known caveats.",
      sql_intent: "Read contradiction/caveat registry from context memory.",
      expected_columns: ["id", "status", "summary"],
      priority: "nice_to_have",
      sql: `
SELECT
  id,
  status,
  summary
FROM context.contradictions
FINAL
ORDER BY detected_at DESC
LIMIT 50`,
    },
  ];
}

function goldPrimitivesForShape(
  shape: TableShape,
  requested: Set<string | QueryIntent["requested_analyses"][number]>,
): { queries: GeneratedSqlQuery[]; covered: Set<string> } {
  const queries: GeneratedSqlQuery[] = [];
  const covered = new Set<string>();
  const gold = shape.goldTables;

  if (gold.dailyEventCounts) {
    queries.push({
      id: idFor("primitive_gold_event_overview", gold.dailyEventCounts),
      purpose: `Gold daily event counts overview from ${gold.dailyEventCounts}.`,
      sql_intent:
        "Aggregate events and unique users by event_name from Gold MV target.",
      expected_columns: ["event_name", "events", "unique_users"],
      priority: "required",
      sql: `
SELECT
  event_name,
  sum(events) AS events,
  sum(unique_users) AS unique_users
FROM ${gold.dailyEventCounts}
GROUP BY event_name
ORDER BY events DESC
LIMIT 100`,
    });
    covered.add("overview");

    if (
      requested.has("trend") ||
      requested.has("root_cause") ||
      requested.has("open_ended")
    ) {
      queries.push({
        id: idFor("primitive_gold_trend", gold.dailyEventCounts),
        purpose: `Daily trend from Gold ${gold.dailyEventCounts}.`,
        sql_intent: "Sum events by day and event_name from Gold daily counts.",
        expected_columns: ["day", "event_name", "events"],
        priority: "nice_to_have",
        sql: `
SELECT
  event_date AS day,
  event_name,
  sum(events) AS events
FROM ${gold.dailyEventCounts}
GROUP BY day, event_name
ORDER BY day DESC, events DESC
LIMIT 200`,
      });
      covered.add("trend");
    }
  }

  if (
    gold.dailyConversion &&
    (requested.has("funnel") ||
      requested.has("metric_lookup") ||
      requested.has("root_cause") ||
      requested.has("open_ended"))
  ) {
    queries.push({
      id: idFor("primitive_gold_conversion", gold.dailyConversion),
      purpose: `Feature conversion from Gold ${gold.dailyConversion}.`,
      sql_intent: "Sum started/success entities and compute conversion rate.",
      expected_columns: ["started", "succeeded", "conversion_rate"],
      priority: "required",
      sql: `
SELECT
  sum(started_entities) AS started,
  sum(success_entities) AS succeeded,
  if(
    sum(started_entities) = 0,
    0,
    sum(success_entities) / sum(started_entities)
  ) AS conversion_rate
FROM ${gold.dailyConversion}`,
    });
    queries.push({
      id: idFor("primitive_gold_conversion_trend", gold.dailyConversion),
      purpose: `Daily conversion trend from Gold ${gold.dailyConversion}.`,
      sql_intent: "Daily started/success entities from Gold conversion MV.",
      expected_columns: ["day", "started", "succeeded", "conversion_rate"],
      priority: "nice_to_have",
      sql: `
SELECT
  event_date AS day,
  sum(started_entities) AS started,
  sum(success_entities) AS succeeded,
  if(
    sum(started_entities) = 0,
    0,
    sum(success_entities) / sum(started_entities)
  ) AS conversion_rate
FROM ${gold.dailyConversion}
GROUP BY day
ORDER BY day DESC
LIMIT 60`,
    });
    covered.add("conversion");
    covered.add("funnel");
  }

  if (
    gold.segmentSuccess &&
    (requested.has("segment_comparison") ||
      requested.has("root_cause") ||
      requested.has("open_ended"))
  ) {
    // Single-dimension rollups first — avoids cherry-picking tiny multi-dim cells.
    for (const dimension of [
      "device_type",
      "os",
      "geoip_country_code",
      "destination",
    ]) {
      queries.push({
        id: idFor(
          `primitive_gold_segment_by_${dimension}`,
          gold.segmentSuccess,
        ),
        purpose: `Segment success by ${dimension} from Gold ${gold.segmentSuccess}.`,
        sql_intent: `Roll up entities/success by ${dimension} only.`,
        expected_columns: [
          dimension,
          "entities",
          "success_entities",
          "success_rate",
        ],
        priority: "required",
        sql: `
SELECT
  ${dimension},
  sum(entities) AS entities,
  sum(success_entities) AS success_entities,
  if(sum(entities) = 0, 0, sum(success_entities) / sum(entities)) AS success_rate
FROM ${gold.segmentSuccess}
GROUP BY ${dimension}
ORDER BY entities DESC
LIMIT 50`,
      });
    }
    queries.push({
      id: idFor("primitive_gold_segment_success", gold.segmentSuccess),
      purpose: `Detailed multi-dimension segment success from Gold ${gold.segmentSuccess}.`,
      sql_intent:
        "Read pre-aggregated multi-dimension segment success from Gold.",
      expected_columns: ["entities", "success_entities", "success_rate"],
      priority: "nice_to_have",
      sql: `
SELECT
  *,
  if(entities = 0, 0, success_entities / entities) AS success_rate
FROM ${gold.segmentSuccess}
ORDER BY entities DESC
LIMIT 50`,
    });
    covered.add("segment");
  }

  if (
    gold.latency &&
    (requested.has("latency") || requested.has("open_ended"))
  ) {
    queries.push({
      id: idFor("primitive_gold_latency", gold.latency),
      purpose: `Latency rollup from Gold ${gold.latency}.`,
      sql_intent: "Mean latency by event from Gold sum/sum_sq rollup.",
      expected_columns: ["event_name", "rows", "mean_latency"],
      priority: "nice_to_have",
      sql: `
SELECT
  event_name,
  sum(rows) AS rows,
  if(sum(rows) = 0, 0, sum(latency_sum) / sum(rows)) AS mean_latency
FROM ${gold.latency}
GROUP BY event_name
ORDER BY mean_latency DESC
LIMIT 100`,
    });
    covered.add("latency");
  }

  return { queries, covered };
}

function hasCoreEventColumns(shape: TableShape) {
  return shape.columns.has("event_name") && shape.columns.has("timestamp");
}

function hasEntity(shape: TableShape) {
  return Boolean(pickEntityColumn(shape));
}

function pickEntityColumn(shape: TableShape) {
  const preferred = [
    shape.workflow?.primary_entity_column,
    "application_id",
    "user_id",
    "app_session_id",
  ].filter((value): value is string => Boolean(value));
  return preferred.find((column) => shape.columns.has(column));
}

function pickSegmentColumn(shape: TableShape, intent?: QueryIntent) {
  const questionText =
    `${intent?.original_question ?? ""} ${intent?.normalized_question ?? ""}`.toLowerCase();
  const mentionedColumn = Array.from(shape.columns).find((column) =>
    questionText.includes(column.toLowerCase()),
  );
  if (mentionedColumn) {
    return mentionedColumn;
  }

  const explicit = [
    ...(intent?.segment_hints ?? []),
    ...(intent?.metric_hints ?? []),
  ]
    .map(normalizeName)
    .find((hint) =>
      Array.from(shape.columns).some(
        (column) => normalizeName(column) === hint,
      ),
    );
  if (explicit) {
    return Array.from(shape.columns).find(
      (column) => normalizeName(column) === explicit,
    );
  }

  const preferred = [
    ...(shape.workflow?.segment_columns ?? []),
    "channel",
    "drop_step",
    "saved_method_type",
    "group_size",
    "status_shared",
    "recipient_is_new_user",
    "to_currency",
    "from_currency",
    "device_type",
    "device",
    "os",
    "geoip_country_code",
    "geoip_subdivision_1_code",
    "country",
    "destination",
    "citizenship",
    "city",
  ];
  return preferred.find((column) => shape.columns.has(column));
}

function normalizeName(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
}

function isExplicitSegmentRequested(intent: QueryIntent, segment: string) {
  const normalizedSegment = normalizeName(segment);
  const text =
    `${intent.original_question} ${intent.normalized_question}`.toLowerCase();
  return (
    text.includes(segment.toLowerCase()) ||
    intent.segment_hints.some(
      (hint) => normalizeName(hint) === normalizedSegment,
    ) ||
    intent.metric_hints.some(
      (hint) => normalizeName(hint) === normalizedSegment,
    )
  );
}

function pickColumn(shape: TableShape, fragments: string[]) {
  return Array.from(shape.columns).find((column) =>
    fragments.some((fragment) => column.includes(fragment)),
  );
}

function pickNumericPair(context: PmRelevantContext, shape: TableShape) {
  const bare = bareTableName(shape.table);
  const numeric = context.columns
    .filter(
      (column) =>
        (column.table_name === shape.table ||
          bareTableName(column.table_name) === bare) &&
        /(UInt|Int|Float|Decimal)/.test(column.clickhouse_type) &&
        !["job_id", "event_id"].includes(column.column_name),
    )
    .map((column) => column.column_name)
    .filter((column) => shape.columns.has(column));
  return numeric.length >= 2 ? ([numeric[0], numeric[1]] as const) : null;
}

function idFor(prefix: string, table: string) {
  return `${prefix}_${table.replace(/[^a-zA-Z0-9]+/g, "_")}`;
}

function eventOverview(shape: TableShape): GeneratedSqlQuery {
  return {
    id: idFor("primitive_event_overview", shape.table),
    purpose: "Show event volume by event name as a broad feature overview.",
    sql_intent: "Count rows by event_name.",
    expected_columns: ["event_name", "rows"],
    priority: "nice_to_have",
    sql: `
SELECT event_name, count() AS rows
FROM ${shape.table}
GROUP BY event_name
ORDER BY rows DESC
LIMIT 100`,
  };
}

function baseTableOverview(shape: TableShape): GeneratedSqlQuery {
  return {
    id: idFor("primitive_base_overview", shape.table),
    purpose: `Row count and time range for base table ${shape.table}.`,
    sql_intent: "Count rows and time span on a base event table.",
    expected_columns: ["rows", "unique_users", "first_seen", "last_seen"],
    priority: "nice_to_have",
    sql: `
SELECT
  count() AS rows,
  uniqExact(user_id) AS unique_users,
  min(timestamp) AS first_seen,
  max(timestamp) AS last_seen
FROM ${shape.table}`,
  };
}

function baseSegmentVolume(
  shape: TableShape,
  segment: string,
): GeneratedSqlQuery {
  return {
    id: idFor(`primitive_base_segment_${segment}`, shape.table),
    purpose: `Base table ${shape.table} volume by ${segment}.`,
    sql_intent: `Count unique users by ${segment}.`,
    expected_columns: [segment, "users", "rows"],
    priority: "nice_to_have",
    sql: `
SELECT
  ${segment},
  uniqExact(user_id) AS users,
  count() AS rows
FROM ${shape.table}
GROUP BY ${segment}
ORDER BY users DESC
LIMIT 100`,
  };
}

function baseFunnelPrimitive(): GeneratedSqlQuery {
  return {
    id: "primitive_base_funnel",
    purpose:
      "Base conversion funnel: unique users at each of the four core stages.",
    sql_intent:
      "Count distinct users on destination_card_clicked → application_started → document_uploaded → purchase_completed.",
    expected_columns: ["stage", "users"],
    priority: "required",
    sql: `
SELECT 'destination_card_clicked' AS stage, uniqExact(user_id) AS users FROM destination_card_clicked
UNION ALL
SELECT 'application_started' AS stage, uniqExact(user_id) AS users FROM application_started
UNION ALL
SELECT 'document_uploaded' AS stage, uniqExact(user_id) AS users FROM document_uploaded
UNION ALL
SELECT 'purchase_completed' AS stage, uniqExact(user_id) AS users FROM purchase_completed`,
  };
}

function baseFunnelByDevicePrimitive(): GeneratedSqlQuery {
  // Join only on application_id. Joining on user_id alone overstates conversion
  // when a user has any purchase for any application.
  return {
    id: "primitive_base_funnel_by_device",
    purpose:
      "Base funnel conversion by device_type (application_started → purchase_completed on application_id).",
    sql_intent:
      "Compare distinct users who started applications vs completed purchase by device_type.",
    expected_columns: [
      "device_type",
      "started_users",
      "purchased_users",
      "conversion_rate",
    ],
    priority: "required",
    sql: `
SELECT
  a.device_type AS device_type,
  uniqExact(a.user_id) AS started_users,
  uniqExactIf(a.user_id, p.application_id IS NOT NULL) AS purchased_users,
  if(
    uniqExact(a.user_id) = 0,
    0,
    uniqExactIf(a.user_id, p.application_id IS NOT NULL) / uniqExact(a.user_id)
  ) AS conversion_rate
FROM application_started AS a
LEFT JOIN (
  SELECT DISTINCT application_id
  FROM purchase_completed
  WHERE application_id IS NOT NULL AND toString(application_id) != ''
) AS p ON a.application_id = p.application_id
GROUP BY device_type
ORDER BY started_users DESC
LIMIT 50`,
  };
}

function featureVsBaselineUplift(shape: TableShape): GeneratedSqlQuery {
  const entity = pickEntityColumn(shape) ?? "user_id";
  const success = shape.workflow?.success_event;
  return {
    id: idFor("primitive_feature_vs_baseline", shape.table),
    purpose:
      "Compare feature success users against base purchase_completed overlap (cross-table).",
    sql_intent:
      "Join feature success entities to purchase_completed on user_id for uplift context.",
    expected_columns: [
      "feature_success_users",
      "also_purchased_users",
      "purchase_overlap_rate",
    ],
    priority: "nice_to_have",
    sql: `
SELECT
  uniqExact(f.user_id) AS feature_success_users,
  uniqExactIf(f.user_id, p.user_id IS NOT NULL) AS also_purchased_users,
  if(
    uniqExact(f.user_id) = 0,
    0,
    uniqExactIf(f.user_id, p.user_id IS NOT NULL) / uniqExact(f.user_id)
  ) AS purchase_overlap_rate
FROM (
  SELECT user_id, ${entity}
  FROM ${shape.table}
  ${success ? `WHERE event_name = ${sqlString(success)}` : ""}
) AS f
LEFT JOIN (
  SELECT DISTINCT user_id
  FROM purchase_completed
) AS p ON f.user_id = p.user_id`,
  };
}

function dataQuality(shape: TableShape): GeneratedSqlQuery {
  const entity = pickEntityColumn(shape) ?? "user_id";
  return {
    id: idFor("primitive_data_quality", shape.table),
    purpose:
      "Check basic data quality for event, timestamp, id, and entity coverage.",
    sql_intent:
      "Return row counts, entity coverage, event id uniqueness, and time range.",
    expected_columns: [
      "rows",
      "unique_events",
      "unique_entities",
      "missing_entities",
      "first_seen",
      "last_seen",
    ],
    priority: "nice_to_have",
    sql: `
SELECT
  count() AS rows,
  uniqExact(event_name) AS unique_events,
  uniqExact(${entity}) AS unique_entities,
  countIf(${entity} = '') AS missing_entities,
  uniqExact(event_id) AS unique_event_ids,
  min(timestamp) AS first_seen,
  max(timestamp) AS last_seen
FROM ${shape.table}`,
  };
}

function trendScan(shape: TableShape): GeneratedSqlQuery {
  return {
    id: idFor("primitive_trend", shape.table),
    purpose: "Show daily event trend by event name.",
    sql_intent: "Count events by day and event_name.",
    expected_columns: ["day", "event_name", "rows"],
    priority: "nice_to_have",
    sql: `
SELECT
  toDate(timestamp) AS day,
  event_name,
  count() AS rows
FROM ${shape.table}
GROUP BY day, event_name
ORDER BY day DESC, rows DESC
LIMIT 200`,
  };
}

function anomalyScan(shape: TableShape): GeneratedSqlQuery {
  return {
    id: idFor("primitive_anomaly", shape.table),
    purpose:
      "Find days whose event volume differs most from the table average.",
    sql_intent:
      "Compute daily event counts with a simple z-score over available days.",
    expected_columns: ["day", "rows", "baseline_avg", "z_score"],
    priority: "nice_to_have",
    sql: `
WITH daily AS (
  SELECT toDate(timestamp) AS day, count() AS rows
  FROM ${shape.table}
  GROUP BY day
)
SELECT
  day,
  rows,
  avg(rows) OVER () AS baseline_avg,
  stddevPop(rows) OVER () AS baseline_std,
  if(stddevPop(rows) OVER () = 0, 0, (rows - avg(rows) OVER ()) / stddevPop(rows) OVER ()) AS z_score
FROM daily
ORDER BY abs(z_score) DESC
LIMIT 30`,
  };
}

function funnelBreakdown(shape: TableShape): GeneratedSqlQuery {
  const entity = pickEntityColumn(shape) ?? "user_id";
  const success = shape.workflow?.success_event;
  return {
    id: idFor("primitive_funnel", shape.table),
    purpose: "Show entity-level funnel reach by event name.",
    sql_intent:
      "Count unique entities reaching each event; include success-event flag when known.",
    expected_columns: [
      "event_name",
      "entities",
      "event_rows",
      "is_success_event",
    ],
    priority: "required",
    sql: `
SELECT
  event_name,
  uniqExact(${entity}) AS entities,
  count() AS event_rows,
  ${success ? `event_name = ${sqlString(success)}` : "0"} AS is_success_event
FROM ${shape.table}
GROUP BY event_name
ORDER BY entities DESC
LIMIT 100`,
  };
}

/**
 * Ordered funnel using workflow/feature event_order — not alphabetical joins.
 * Emits one row per step with step_index so drop-off is computable in order.
 */
function orderedFunnelDropoff(shape: TableShape): GeneratedSqlQuery {
  const entity = pickEntityColumn(shape) ?? "user_id";
  const events = shape.eventOrder.slice(0, 12);
  const unions = events
    .map(
      (eventName, index) => `
SELECT
  ${index + 1} AS step_index,
  ${sqlString(eventName)} AS stage,
  uniqExact(${entity}) AS users
FROM ${shape.table}
WHERE event_name = ${sqlString(eventName)}`,
    )
    .join("\nUNION ALL\n");

  return {
    id: idFor("primitive_ordered_funnel", shape.table),
    purpose:
      "Ordered feature funnel by known event sequence (for true step drop-off).",
    sql_intent:
      "Count unique entities at each workflow event in order with step_index.",
    expected_columns: ["step_index", "stage", "users"],
    priority: "required",
    sql: `
SELECT step_index, stage, users
FROM (
${unions}
)
ORDER BY step_index
LIMIT 100`,
  };
}

function conversionRate(shape: TableShape): GeneratedSqlQuery {
  const entity = pickEntityColumn(shape) ?? "user_id";
  const start = shape.workflow?.start_event;
  const success = shape.workflow?.success_event;
  return {
    id: idFor("primitive_conversion", shape.table),
    purpose: "Primary feature conversion: start event → success event.",
    sql_intent: "Compute uniq entities at start vs success.",
    expected_columns: ["started", "succeeded", "conversion_rate"],
    priority: "required",
    sql: `
SELECT
  uniqExactIf(${entity}, event_name = ${sqlString(start ?? "")}) AS started,
  uniqExactIf(${entity}, event_name = ${sqlString(success ?? "")}) AS succeeded,
  if(
    uniqExactIf(${entity}, event_name = ${sqlString(start ?? "")}) = 0,
    0,
    uniqExactIf(${entity}, event_name = ${sqlString(success ?? "")})
      / uniqExactIf(${entity}, event_name = ${sqlString(start ?? "")})
  ) AS conversion_rate
FROM ${shape.table}`,
  };
}

function segmentComparison(
  shape: TableShape,
  segment: string,
): GeneratedSqlQuery {
  const entity = pickEntityColumn(shape) ?? "user_id";
  const success = shape.workflow?.success_event;
  const successExpr = success
    ? `uniqExactIf(${entity}, event_name = ${sqlString(success)})`
    : "0";
  return {
    id: idFor(`primitive_segment_${segment}`, shape.table),
    purpose: `Compare coverage and success by ${segment}.`,
    sql_intent: `Compute entity volume and success rate by ${segment}.`,
    expected_columns: [segment, "entities", "success_entities", "success_rate"],
    priority: "required",
    sql: `
SELECT
  ${segment},
  uniqExact(${entity}) AS entities,
  ${successExpr} AS success_entities,
  if(uniqExact(${entity}) = 0, 0, success_entities / uniqExact(${entity})) AS success_rate
FROM ${shape.table}
GROUP BY ${segment}
ORDER BY entities DESC
LIMIT 100`,
  };
}

function latencyDistribution(
  shape: TableShape,
  latencyColumn: string,
): GeneratedSqlQuery {
  return {
    id: idFor(`primitive_latency_${latencyColumn}`, shape.table),
    purpose: `Summarize latency distribution for ${latencyColumn}.`,
    sql_intent: `Compute p50/p90/p95 latency by event_name for ${latencyColumn}.`,
    expected_columns: ["event_name", "p50", "p90", "p95"],
    priority: "nice_to_have",
    sql: `
SELECT
  event_name,
  quantileExact(0.5)(${latencyColumn}) AS p50,
  quantileExact(0.9)(${latencyColumn}) AS p90,
  quantileExact(0.95)(${latencyColumn}) AS p95,
  count() AS rows
FROM ${shape.table}
WHERE ${latencyColumn} IS NOT NULL
GROUP BY event_name
ORDER BY p95 DESC
LIMIT 100`,
  };
}

function correlationScan(
  shape: TableShape,
  left: string,
  right: string,
): GeneratedSqlQuery {
  return {
    id: idFor(`primitive_correlation_${left}_${right}`, shape.table),
    purpose: `Check simple correlation between ${left} and ${right}.`,
    sql_intent: `Compute Pearson correlation for two numeric columns.`,
    expected_columns: ["correlation", "rows"],
    priority: "nice_to_have",
    sql: `
SELECT
  corr(toFloat64(${left}), toFloat64(${right})) AS correlation,
  count() AS rows
FROM ${shape.table}
WHERE ${left} IS NOT NULL AND ${right} IS NOT NULL`,
  };
}
