import { startActiveObservation } from "@langfuse/tracing";
import { callGroqJson } from "../groq.js";
import { BASE_EVENT_TABLES } from "../warehouseTables.js";
import { writeStageJson } from "../instrumentation/artifacts.js";
import { recordPipelineStage } from "../tracking.js";
import { AnalyticsStrictFailure } from "./graceful.js";
import { clampTableHints } from "./tableCatalog.js";
import { analyticsTrackingEvents } from "./trackingEvents.js";
import { QueryIntent } from "./types.js";
import { normalizeTokens, unique } from "./utils.js";

const ALLOWED_ANALYSES = new Set<QueryIntent["requested_analyses"][number]>([
  "metric_lookup",
  "trend",
  "funnel",
  "root_cause",
  "segment_comparison",
  "latency",
  "data_quality",
  "schema_explanation",
  "open_ended",
]);

export async function runQueryUnderstanding(input: {
  jobId: string;
  question: string;
  artifactRoot: string;
}): Promise<QueryIntent> {
  const event = analyticsTrackingEvents.queryUnderstanding;
  return startActiveObservation(event.stageId, async (span) => {
    span.update({
      input: { question: input.question },
      metadata: { agent: "analytics_query_understanding" },
    });

    // Refuse garbage / uninterpretable prompts without burning warehouse scan tokens.
    if (isUninterpretableQuestion(input.question)) {
      const intent: QueryIntent = {
        original_question: input.question,
        normalized_question: input.question.trim().toLowerCase(),
        feature_hints: [],
        metric_hints: [],
        table_hints: [],
        segment_hints: [],
        time_hints: [],
        requested_analyses: ["schema_explanation"],
        ambiguity_notes: [
          "UNINTERPRETABLE_QUESTION: prompt does not look like a product analytics question.",
        ],
      };
      await writeStageJson(
        input.artifactRoot,
        event.stageId,
        "intent.json",
        intent,
      );
      await recordPipelineStage({
        jobId: input.jobId,
        stageId: event.stageId,
        stageName: event.stageName,
        status: "completed",
        stageInput: { question: input.question },
        stageOutput: intent,
      });
      span.update({ output: intent });
      return intent;
    }

    let llmIntent: QueryIntent | null = null;
    try {
      llmIntent = await callGroqJson<QueryIntent>({
        modelRole: "intent",
        traceName: "groq.analytics.query_intent",
        temperature: 0,
        maxTokens: 800,
        traceInput: { question: input.question },
        messages: [
          {
            role: "system",
            content:
              "You parse product-manager analytics questions. Return strict JSON only. Do not answer the question. Never invent warehouse table names.",
          },
          {
            role: "user",
            content: `Parse this PM analytics question into:
{
  "original_question": string,
  "normalized_question": string,
  "feature_hints": string[],
  "metric_hints": string[],
  "table_hints": string[],
  "segment_hints": string[],
  "time_hints": string[],
  "requested_analyses": string[],
  "ambiguity_notes": string[]
}

Allowed requested_analyses values: metric_lookup, trend, funnel, root_cause, segment_comparison, latency, data_quality, schema_explanation, open_ended.

table_hints rules:
- Only include a table_hint if the question explicitly names a real event/table style identifier.
- Do NOT invent names like user_sessions, checkout_events, checkout_sessions, logs.
- Prefer empty table_hints over guesses. Feature names belong in feature_hints, not table_hints.
- Known base tables if ever named: ${BASE_EVENT_TABLES.join(", ")}.

Question: ${input.question}`,
          },
        ],
      });
    } catch (error) {
      llmIntent = null;
      span.update({
        metadata: {
          llm_failed: true,
          error: error instanceof Error ? error.message : String(error),
        },
      });
    }

    if (llmIntent && !isValidIntentShape(llmIntent)) {
      throw new AnalyticsStrictFailure(
        event.stageId,
        "Query understanding returned an unusable intent shape.",
      );
    }

    const intent = repairIntent(llmIntent, input.question);
    await writeStageJson(
      input.artifactRoot,
      event.stageId,
      "intent.json",
      intent,
    );
    await recordPipelineStage({
      jobId: input.jobId,
      stageId: event.stageId,
      stageName: event.stageName,
      status: "completed",
      stageInput: { question: input.question },
      stageOutput: intent,
    });
    span.update({ output: intent });
    return intent;
  });
}

function repairIntent(
  intent: QueryIntent | null,
  question: string,
): QueryIntent {
  const fallback = deterministicIntent(question);
  const source = intent ?? fallback;

  const requested = unique(
    (source.requested_analyses ?? [])
      .map((value) => value as QueryIntent["requested_analyses"][number])
      .filter((value) => ALLOWED_ANALYSES.has(value)),
  );

  const rawTableHints = unique([
    ...(source.table_hints ?? []),
    ...fallback.table_hints,
  ]);

  return {
    original_question: question,
    normalized_question:
      source.normalized_question || fallback.normalized_question,
    feature_hints: unique([
      ...(source.feature_hints ?? []),
      ...fallback.feature_hints,
    ]),
    metric_hints: unique([
      ...(source.metric_hints ?? []),
      ...fallback.metric_hints,
    ]),
    table_hints: clampTableHints(rawTableHints),
    segment_hints: unique([
      ...(source.segment_hints ?? []),
      ...fallback.segment_hints,
    ]),
    time_hints: unique([...(source.time_hints ?? []), ...fallback.time_hints]),
    requested_analyses:
      requested.length > 0 ? requested : fallback.requested_analyses,
    ambiguity_notes: unique([
      ...(source.ambiguity_notes ?? []),
      ...fallback.ambiguity_notes,
      ...(intent
        ? []
        : [
            "Used deterministic intent parse because LLM intent was unavailable.",
          ]),
    ]),
  };
}

function isValidIntentShape(intent: QueryIntent) {
  return (
    Boolean(intent) &&
    Array.isArray(intent.feature_hints) &&
    Array.isArray(intent.metric_hints) &&
    Array.isArray(intent.table_hints) &&
    Array.isArray(intent.segment_hints) &&
    Array.isArray(intent.time_hints) &&
    Array.isArray(intent.requested_analyses) &&
    Array.isArray(intent.ambiguity_notes)
  );
}

/** True for keyboard-smash / empty / non-analytics prompts. */
export function isUninterpretableQuestion(question: string): boolean {
  const raw = question.trim();
  if (raw.length < 4) {
    return true;
  }
  const alpha = raw.replace(/[^a-zA-Z\s]/g, " ").trim();
  const words = alpha.split(/\s+/).filter((word) => word.length > 2);
  if (words.length === 0) {
    return true;
  }
  const analyticsSignal =
    /\b(funnel|conversion|checkout|express|group|family|status|abandon|recovery|forex|purchase|destination|device|ios|android|coupon|revenue|drop|segment|metric|table|event|visa|feature|performance|summary|why|what|how|which|where|rate|latency|quality|uplift|baseline|compare|schengen|otp|payment)\b/i;
  if (!analyticsSignal.test(raw) && words.length <= 6) {
    return true;
  }
  // High symbol noise with almost no real words
  const symbolRatio =
    (raw.replace(/[a-zA-Z0-9\s]/g, "").length || 0) / Math.max(raw.length, 1);
  if (symbolRatio > 0.35 && words.length < 4) {
    return true;
  }
  return false;
}

function deterministicIntent(question: string): QueryIntent {
  const tokens = normalizeTokens(question);
  const has = (...values: string[]) =>
    values.some((value) => tokens.has(value));
  const requested_analyses: QueryIntent["requested_analyses"] = [];

  if (has("why", "drop", "dropped", "worse", "root", "cause")) {
    requested_analyses.push("root_cause");
  }
  if (has("funnel", "conversion", "complete", "completion", "dropoff")) {
    requested_analyses.push("funnel");
  }
  if (has("ios", "android", "mobile", "country", "geo", "device", "segment")) {
    requested_analyses.push("segment_comparison");
  }
  if (has("trend", "over", "daily", "weekly", "yesterday", "today")) {
    requested_analyses.push("trend");
  }
  if (has("slow", "latency", "time", "duration")) {
    requested_analyses.push("latency");
  }
  if (has("quality", "missing", "null", "duplicate")) {
    requested_analyses.push("data_quality");
  }
  if (has("schema", "table", "column", "event", "metric", "available")) {
    requested_analyses.push("schema_explanation");
  }
  if (requested_analyses.length === 0) {
    requested_analyses.push("open_ended");
  }

  const table_hints = (BASE_EVENT_TABLES as readonly string[]).filter((table) =>
    question.toLowerCase().includes(table),
  );

  return {
    original_question: question,
    normalized_question: question.trim().toLowerCase(),
    feature_hints: Array.from(tokens).filter((token) =>
      [
        "checkout",
        "express",
        "family",
        "group",
        "forex",
        "status",
        "sharing",
        "abandoned",
        "recovery",
      ].includes(token),
    ),
    metric_hints: Array.from(tokens).filter((token) =>
      [
        "conversion",
        "completion",
        "dropoff",
        "revenue",
        "latency",
        "success",
        "failure",
        "value",
        "coupon",
      ].includes(token),
    ),
    table_hints,
    segment_hints: Array.from(tokens).filter((token) =>
      ["ios", "android", "mobile", "web", "country", "device", "geo"].includes(
        token,
      ),
    ),
    time_hints: Array.from(tokens).filter((token) =>
      [
        "today",
        "yesterday",
        "daily",
        "weekly",
        "month",
        "latest",
        "quarter",
      ].includes(token),
    ),
    requested_analyses,
    ambiguity_notes: [],
  };
}
