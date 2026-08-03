import { startActiveObservation } from "@langfuse/tracing";
import { callGroqJson } from "../groq.js";
import { writeStageJson } from "../instrumentation/artifacts.js";
import { BASE_FUNNEL_TABLES, qualifyFeatureTable } from "../warehouseTables.js";
import { recordPipelineStage } from "../tracking.js";
import { AnalyticsStrictFailure } from "./graceful.js";
import {
  clampTablesToCatalog,
  goldMvCandidates,
  knownAnalyticsTables,
} from "./tableCatalog.js";
import { analyticsTrackingEvents } from "./trackingEvents.js";
import { AnalysisPlan, PmRelevantContext, QueryIntent } from "./types.js";
import { compactJson, unique } from "./utils.js";

const MAX_MIN_ROWS = 1;

export async function runAnalysisPlanner(input: {
  jobId: string;
  question: string;
  intent: QueryIntent;
  context: PmRelevantContext;
  artifactRoot: string;
  repairNotes?: string[];
}): Promise<AnalysisPlan> {
  const event = analyticsTrackingEvents.analysisPlanner;
  return startActiveObservation(event.stageId, async (span) => {
    span.update({
      input: {
        question: input.question,
        intent: input.intent,
        repair_notes: input.repairNotes ?? [],
      },
      metadata: { agent: "analytics_planner" },
    });

    const knownTables = knownAnalyticsTables(input.context);
    let llmPlan: AnalysisPlan | null = null;
    try {
      llmPlan = await callGroqJson<AnalysisPlan>({
        modelRole: "plan",
        traceName: "groq.analytics.analysis_plan",
        temperature: 0.1,
        maxTokens: 1600,
        traceInput: {
          question: input.question,
          context_features: input.context.features.map(
            (feature) => feature.feature_slug,
          ),
          repair_notes: input.repairNotes ?? [],
        },
        messages: [
          {
            role: "system",
            content:
              "You are an analytics planning agent. Produce a compact JSON analysis plan. Do not write SQL yet. Never invent tables that are not listed.",
          },
          {
            role: "user",
            content: `Question:
${input.question}

Intent:
${compactJson(input.intent)}

KNOWN TABLES (use only these):
${knownTables.map((table) => `- ${table}`).join("\n") || "- (none)"}

Relevant context:
${compactJson(input.context, 16000)}

Prior repair notes:
${compactJson(input.repairNotes ?? [])}

Return JSON with this shape:
{
  "interpreted_question": string,
  "answer_type": "metric_lookup" | "trend" | "funnel" | "root_cause" | "segment_comparison" | "latency" | "data_quality" | "schema_explanation" | "open_ended",
  "tables": string[],
  "joins": [{"left_table": string, "left_column": string, "right_table": string, "right_column": string, "reason": string}],
  "queries": [{"id": string, "purpose": string, "sql_intent": string, "expected_columns": string[], "priority": "required" | "nice_to_have"}],
  "evidence_standard": {"needs_comparison": boolean, "needs_segment_cut": boolean, "min_rows": number, "can_answer_if_empty": boolean},
  "assumptions": string[],
  "risks": string[]
}

Rules:
- Plan 1-5 ClickHouse queries.
- tables[] must be a subset of KNOWN TABLES. If the feature is unknown, set answer_type to schema_explanation and do not invent silver.* tables.
- evidence_standard.min_rows must be 1 (aggregates return few rows).
- Prefer gold.* daily/segment MVs when available for the feature.
- Include baseline base-funnel tables when asking about uplift, overall conversion, or root cause.
- If contradictions mention known issues (e.g. K1 iOS OTP), plan a device/os segment cut.`,
          },
        ],
      });
    } catch (error) {
      llmPlan = null;
      span.update({
        metadata: {
          llm_failed: true,
          error: error instanceof Error ? error.message : String(error),
        },
      });
    }

    if (llmPlan && !isValidPlanShape(llmPlan)) {
      // Don't kill the ask — fall through to grounded deterministic plan.
      span.update({
        metadata: {
          llm_plan_invalid: true,
          note: "Unusable LLM plan shape; using grounded fallback plan.",
        },
      });
      llmPlan = null;
    }

    // Grounded deterministic plan is allowed (from context catalog), not invented metrics.
    const plan = repairPlan(llmPlan, input, knownTables);
    await writeStageJson(
      input.artifactRoot,
      event.stageId,
      "analysis_plan.json",
      plan,
    );
    await recordPipelineStage({
      jobId: input.jobId,
      stageId: event.stageId,
      stageName: event.stageName,
      status: "completed",
      stageInput: { question: input.question },
      stageOutput: plan,
    });
    span.update({ output: plan });
    return plan;
  });
}

function repairPlan(
  plan: AnalysisPlan | null,
  input: {
    question: string;
    intent: QueryIntent;
    context: PmRelevantContext;
  },
  knownTables: string[],
): AnalysisPlan {
  const fallback = fallbackPlan(input, knownTables);
  const source = plan ?? fallback;

  const tables = clampTablesToCatalog(
    unique([...(source.tables ?? []), ...fallback.tables]),
    input.context,
  );

  // Prefer gold MVs for known silver feature tables when present in catalog.
  const withGold = unique([
    ...tables,
    ...tables.flatMap((table) =>
      table.startsWith("silver.")
        ? goldMvCandidates(table).filter((mv) => knownTables.includes(mv))
        : [],
    ),
  ]);

  const unknownFeature =
    fallback.answer_type === "schema_explanation" &&
    fallback.assumptions.some((item) =>
      /not found in context memory|will not attribute/i.test(item),
    );

  const joins = unknownFeature
    ? []
    : uniqueJoins([
        ...(source.joins ?? []),
        ...fallback.joins,
        ...input.context.joins.slice(0, 8).map((join) => ({
          left_table: qualifyFeatureTable(join.left_table),
          left_column: join.left_column,
          right_table: qualifyFeatureTable(join.right_table),
          right_column: join.right_column,
          reason: `Context join (${join.grain}, confidence ${join.confidence})`,
        })),
      ])
        .filter(
          (join) =>
            withGold.includes(join.left_table) ||
            knownTables.includes(join.left_table) ||
            knownTables.includes(join.right_table),
        )
        .slice(0, 12);

  const queries = (source.queries ?? [])
    .filter((query) => query.id && query.purpose && query.sql_intent)
    .slice(0, 6);

  const resolvedQueries = unknownFeature
    ? fallback.queries
    : queries.length > 0
      ? queries
      : fallback.queries;
  if (resolvedQueries.length === 0) {
    throw new AnalyticsStrictFailure(
      "08c_analysis_planner",
      "No grounded queries could be planned from known tables.",
    );
  }

  return {
    interpreted_question:
      source.interpreted_question || fallback.interpreted_question,
    answer_type: unknownFeature
      ? "schema_explanation"
      : source.answer_type || fallback.answer_type,
    tables: unknownFeature
      ? fallback.tables
      : withGold.length > 0
        ? withGold
        : fallback.tables,
    joins,
    queries: resolvedQueries,
    evidence_standard: {
      needs_comparison:
        source.evidence_standard?.needs_comparison ??
        fallback.evidence_standard.needs_comparison,
      needs_segment_cut:
        source.evidence_standard?.needs_segment_cut ??
        fallback.evidence_standard.needs_segment_cut,
      // Aggregates should not require hundreds of JSON rows.
      min_rows: MAX_MIN_ROWS,
      can_answer_if_empty:
        unknownFeature ||
        source.answer_type === "schema_explanation" ||
        source.evidence_standard?.can_answer_if_empty ||
        fallback.evidence_standard.can_answer_if_empty,
    },
    assumptions: unique([
      ...(source.assumptions ?? []),
      ...fallback.assumptions,
      ...(plan
        ? []
        : [
            "Deterministic grounded plan used because LLM plan was unavailable.",
          ]),
      ...(unknownFeature
        ? [
            "Feature hints did not match generated context memory; refusing to invent feature tables.",
          ]
        : []),
    ]),
    risks: unique([...(source.risks ?? []), ...fallback.risks]),
  };
}

function isValidPlanShape(plan: AnalysisPlan) {
  return (
    Boolean(plan) &&
    typeof plan.interpreted_question === "string" &&
    typeof plan.answer_type === "string" &&
    Array.isArray(plan.tables) &&
    Array.isArray(plan.joins) &&
    Array.isArray(plan.queries) &&
    Boolean(plan.evidence_standard) &&
    Array.isArray(plan.assumptions) &&
    Array.isArray(plan.risks)
  );
}

function fallbackPlan(
  input: {
    question: string;
    intent: QueryIntent;
    context: PmRelevantContext;
  },
  knownTables: string[],
): AnalysisPlan {
  // Only use a feature table when the question/hints actually match it.
  // Never default to features[0] for unrelated questions (e.g. fake features).
  const matchedFeature = pickMatchedFeature(input.intent, input.context);
  const contextCatalogQuestion = isContextCatalogQuestion(
    input.question,
    input.intent,
  );
  const unknownNamedFeature =
    !contextCatalogQuestion &&
    looksLikeNamedFeatureQuestion(input.question, input.intent) &&
    !matchedFeature;
  const baselineRelevant = isBaselineRelevantQuestion(input.question);

  const featureTable = matchedFeature
    ? qualifyFeatureTable(matchedFeature.table_name)
    : null;

  const answerType = contextCatalogQuestion
    ? "schema_explanation"
    : unknownNamedFeature
      ? "schema_explanation"
      : (input.intent.requested_analyses[0] ?? "open_ended");
  const tables = clampTablesToCatalog(
    unique(
      (contextCatalogQuestion
        ? []
        : unknownNamedFeature
          ? [
              "context.feature_registry",
              "context.metric_registry",
              ...BASE_FUNNEL_TABLES,
            ]
          : [
              featureTable,
              ...(featureTable && !baselineRelevant ? [] : BASE_FUNNEL_TABLES),
            ]
      ).filter(Boolean) as string[],
    ),
    input.context,
  );

  const joins =
    featureTable &&
    featureTable.startsWith("silver.") &&
    knownTables.includes(featureTable)
      ? [
          {
            left_table: featureTable,
            left_column: "user_id",
            right_table: "purchase_completed",
            right_column: "user_id",
            reason:
              "Feature vs baseline conversion join on user_id for uplift/context.",
          },
          {
            left_table: featureTable,
            left_column: "application_id",
            right_table: "application_started",
            right_column: "application_id",
            reason: "Application-level join into the base funnel.",
          },
        ]
      : [];

  return {
    interpreted_question: input.question,
    answer_type: answerType,
    tables,
    joins,
    queries: contextCatalogQuestion
      ? [
          {
            id: "q_context_catalog",
            purpose:
              "Summarize instrumented feature tables, events, joins, metrics, and known caveats from context registries.",
            sql_intent:
              "Read context.feature_registry, context.workflow_registry, context.metric_registry, context.join_registry, and context.contradictions.",
            expected_columns: [
              "feature_slug",
              "table_name",
              "event_names",
              "metric_name",
              "left_table",
              "right_table",
              "summary",
            ],
            priority: "required",
          },
        ]
      : unknownNamedFeature
        ? [
            {
              id: "q1_list_features",
              purpose:
                "List instrumented features so we can show the requested feature is missing.",
              sql_intent:
                "SELECT feature_slug, table_name FROM context.feature_registry ORDER BY updated_at DESC LIMIT 1 BY feature_slug",
              expected_columns: ["feature_slug", "table_name"],
              priority: "required",
            },
          ]
        : [
            {
              id: "q1_overview",
              purpose: featureTable
                ? "Get a compact overview of feature event volume and event names."
                : "Get base funnel stage volumes for context.",
              sql_intent: featureTable
                ? `Summarize row counts by event_name from ${featureTable}.`
                : "Count distinct users at each base funnel stage.",
              expected_columns: featureTable
                ? ["event_name", "rows"]
                : ["stage", "users"],
              priority: "required",
            },
            {
              id: "q2_baseline",
              purpose: "Base conversion funnel baseline for comparison.",
              sql_intent:
                "Count distinct users on destination_card_clicked, application_started, document_uploaded, purchase_completed.",
              expected_columns: ["stage", "users"],
              priority: "nice_to_have",
            },
          ],
    evidence_standard: {
      needs_comparison: ["root_cause", "trend", "segment_comparison"].includes(
        answerType,
      ),
      needs_segment_cut: ["root_cause", "segment_comparison"].includes(
        answerType,
      ),
      min_rows: MAX_MIN_ROWS,
      can_answer_if_empty: answerType === "schema_explanation",
    },
    assumptions: [
      "Grounded fallback plan from context catalog / base funnel tables only.",
      ...(unknownNamedFeature
        ? [
            "Named feature was not found in context memory; will not attribute other feature metrics to it.",
          ]
        : []),
    ],
    risks: input.context.retrieval_notes.filter((note) =>
      note.startsWith("WARNING"),
    ),
  };
}

function pickMatchedFeature(intent: QueryIntent, context: PmRelevantContext) {
  const haystack = [
    intent.original_question,
    ...intent.feature_hints,
    ...intent.table_hints,
  ]
    .join(" ")
    .toLowerCase();
  return (
    context.features.find((feature) => {
      const slug = feature.feature_slug.toLowerCase();
      const spaced = slug.replace(/_/g, " ");
      const tokens = slug.split("_").filter((token) => token.length > 2);
      return (
        haystack.includes(slug) ||
        haystack.includes(spaced) ||
        tokens.some((token) => haystack.includes(token)) ||
        intent.feature_hints.some((hint) => {
          const normalized = hint.toLowerCase().replace(/[^a-z0-9]+/g, "_");
          return (
            slug.includes(normalized) ||
            normalized.includes(slug) ||
            spaced.includes(hint.toLowerCase())
          );
        })
      );
    }) ?? null
  );
}

/**
 * True only when the user is clearly asking about a named product feature
 * that might be missing — not base-funnel / metric / geo questions.
 */
function looksLikeNamedFeatureQuestion(question: string, intent: QueryIntent) {
  if (isContextCatalogQuestion(question, intent)) {
    return false;
  }
  if (isBaseWarehouseQuestion(question, intent)) {
    return false;
  }

  if (
    /\b(feature called|feature named|new feature|unreleased|concierge|yacht|luxury)\b/i.test(
      question,
    )
  ) {
    return true;
  }

  const metricNoise = new Set([
    "conversion",
    "funnel",
    "drop",
    "dropoff",
    "rate",
    "revenue",
    "purchase",
    "performance",
    "overall",
    "baseline",
    "uplift",
    "summary",
    "quality",
    "segment",
    "device",
    "ios",
    "android",
    "coupon",
    "currency",
    "value",
    "metric",
    "table",
    "event",
  ]);
  const productHints = intent.feature_hints.filter((hint) => {
    const token = hint.toLowerCase().replace(/[^a-z0-9]+/g, "_");
    if (!token || token.length < 3) {
      return false;
    }
    if (metricNoise.has(token) || metricNoise.has(token.replace(/_/g, ""))) {
      return false;
    }
    return true;
  });

  return productHints.length > 0;
}

function isContextCatalogQuestion(question: string, intent: QueryIntent) {
  const text = `${question} ${intent.normalized_question} ${intent.requested_analyses.join(" ")}`;
  return (
    /available|currently|catalog|inventory|what tables|what events|what joins|what metrics|known caveats|instrumented feature specs|across all/i.test(
      text,
    ) && /tables?|events?|joins?|metrics?|caveats?|features?/i.test(text)
  );
}

function isBaselineRelevantQuestion(question: string) {
  return /baseline|uplift|standard checkout|standard|versus standard|vs standard|base funnel|existing funnel|overall conversion|compared? to purchase|feature .* purchase|purchase overlap/i.test(
    question,
  );
}

function isBaseWarehouseQuestion(question: string, intent: QueryIntent) {
  const text = `${question} ${intent.table_hints.join(" ")} ${intent.metric_hints.join(" ")}`;
  return /destination_card|application_started|document_uploaded|purchase_completed|pay_now|pre-?purchase|overall conversion|base funnel|conversion funnel from|card click|schengen|geoip|coupon_applied|visa_issuance_eta|eta_shown|on-?time delivery/i.test(
    text,
  );
}

function uniqueJoins(joins: AnalysisPlan["joins"]): AnalysisPlan["joins"] {
  const seen = new Set<string>();
  return joins.filter((join) => {
    if (
      !join.left_table ||
      !join.right_table ||
      join.left_table.includes("*") ||
      join.right_table.includes("*") ||
      join.left_table.includes("|") ||
      join.right_table.includes("|")
    ) {
      return false;
    }
    const key = [
      join.left_table,
      join.left_column,
      join.right_table,
      join.right_column,
    ].join("|");
    if (seen.has(key)) {
      return false;
    }
    seen.add(key);
    return true;
  });
}
