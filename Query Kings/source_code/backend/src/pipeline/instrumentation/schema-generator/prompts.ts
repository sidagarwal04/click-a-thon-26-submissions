import { ContextBundle, RelevantContextBundle } from "../../context.js";
import { callGroqJson } from "../../groq.js";
import { EventProfile, FeatureManifest, SchemaPlan } from "../types.js";
import { SchemaCriticDraft, SchemaDesignDraft } from "./types.js";

export async function requestSchemaDesignDraft(
  input: {
    featureSlug: string;
    manifest: FeatureManifest;
    eventProfile: EventProfile;
    context: ContextBundle;
    executionFeedback?: string[];
  },
  relevantContext: RelevantContextBundle,
): Promise<SchemaDesignDraft | null> {
  // Never abort instrumentation on LLM failure — caller falls back to evidence plan.
  try {
    const draft = await callGroqJson<SchemaDesignDraft>({
      modelRole: "schema",
      strictJson: false,
      temperature: 0,
      maxTokens: 3500,
      traceName: "groq.schema_design",
      traceInput: {
        task: "clickhouse_schema_design",
        feature_slug: input.featureSlug,
        workflow_type: input.manifest.workflow_type,
        field_count: input.eventProfile.fields.length,
        execution_feedback_count: input.executionFeedback?.length ?? 0,
        context_features: input.context.generatedContext.features.length,
        retrieved_workflows: relevantContext.similar_workflows.length,
        retrieved_columns: relevantContext.column_type_precedents.length,
        retrieved_metrics: relevantContext.reusable_metrics.length,
        retrieved_joins: relevantContext.recommended_joins.length,
      },
      messages: [
        {
          role: "system",
          content:
            "You are a ClickHouse instrumentation schema designer. Return exactly one JSON object and nothing else. Do not return null. The JSON object must include a columns array. Design from the spec and raw event evidence. Treat business context as useful but fallible; never trust context over raw event evidence.",
        },
        {
          role: "user",
          content: JSON.stringify({
            task: "Design the full Silver ClickHouse schema plan for this feature. Use the spec and event profile as source of truth. Use context only when supported by evidence, and explicitly mark context assumptions as trusted or not trusted.",
            allowed_shape: {
              table_name: `${input.featureSlug}_events`,
              engine: "ReplacingMergeTree",
              order_by: ["existing_column_name"],
              partition_by:
                "ClickHouse partition expression, usually toYYYYMM(timestamp)",
              ttl: "ClickHouse TTL expression",
              columns: [
                {
                  name: "snake_case_column_name",
                  type: "ClickHouse type",
                  source_path:
                    "raw JSON path from event_profile, or null only for pipeline columns",
                  reason: "why this column belongs in the analytical schema",
                },
              ],
              materialized_view_recommendations: [
                {
                  purpose: "aggregation purpose",
                  dimensions: ["existing_column_name"],
                  metrics: ["count | success_count | entity_count"],
                },
              ],
              context_assumptions: [
                {
                  claim: "context claim used or rejected",
                  evidence: "spec/event/profile/context evidence",
                  trusted: true,
                },
              ],
              rationale: ["short reasoning bullets"],
            },
            constraints: [
              "Return exactly one JSON object. No markdown, no prose outside JSON, no null.",
              "Every non-pipeline source_path must exist in event_profile.fields.",
              "Include required pipeline columns: job_id, event_name, event_id, timestamp, raw_json, ingested_at.",
              "event_name maps from raw path event; event_id maps from raw path id; timestamp maps from raw path timestamp.",
              "ORDER BY columns must be non-nullable.",
              "ORDER BY must include timestamp and event_id.",
              "Keep raw_json for replay.",
              "Prefer LowCardinality(String) for repeated dimensions.",
              "Use Nullable types for fields missing from some events or containing nulls.",
              "Suggest materialized views only for reusable aggregates.",
              "Do not copy context errors into the schema. If context conflicts with event evidence, trust event evidence.",
              "If execution_feedback is present, fix the schema or mapping decision that caused the failed load/validation attempt.",
            ],
            execution_feedback: input.executionFeedback ?? [],
            feature_manifest: input.manifest,
            // Compact profile — huge payloads make 8b models emit non-JSON garbage.
            event_profile: compactEventProfile(input.eventProfile),
            relevant_context: {
              similar_workflows: relevantContext.similar_workflows.slice(0, 5),
              column_type_precedents:
                relevantContext.column_type_precedents.slice(0, 40),
              reusable_metrics: relevantContext.reusable_metrics.slice(0, 15),
              recommended_joins: relevantContext.recommended_joins.slice(0, 15),
              retrieval_notes: relevantContext.retrieval_notes,
              contradictions: relevantContext.contradictions.slice(0, 8),
            },
            base_context_excerpt: input.context.baseContext.slice(0, 2500),
          }),
        },
      ],
    });
    if (!draft || !Array.isArray(draft.columns) || draft.columns.length === 0) {
      return null;
    }
    return draft;
  } catch {
    return null;
  }
}

export async function requestSchemaCriticReview(input: {
  featureSlug: string;
  manifest: FeatureManifest;
  eventProfile: EventProfile;
  context: ContextBundle;
  schemaPlan: SchemaPlan;
  relevantContext: RelevantContextBundle;
  deterministicIssues: string[];
}): Promise<SchemaCriticDraft | null> {
  try {
    const review = await callGroqJson<SchemaCriticDraft>({
      modelRole: "critic",
      strictJson: false,
      temperature: 0,
      maxTokens: 2000,
      traceName: "groq.schema_critic",
      traceInput: {
        task: "clickhouse_schema_critic",
        feature_slug: input.featureSlug,
        workflow_type: input.manifest.workflow_type,
        deterministic_issue_count: input.deterministicIssues.length,
      },
      messages: [
        {
          role: "system",
          content:
            "You are a strict ClickHouse schema critic for product analytics instrumentation. Return exactly one valid JSON object with verdict, issues, revision_instructions, and rationale. Do not return null.",
        },
        {
          role: "user",
          content: JSON.stringify({
            task: "Critique this generated schema summary. Return verdict pass or revise. If revise, provide concrete revision_instructions for the schema designer.",
            required_shape: {
              verdict: "pass | revise",
              issues: ["specific issue"],
              revision_instructions: ["specific instruction"],
              rationale: ["short reasoning"],
            },
            checks: [
              "Return exactly one JSON object. No markdown, no prose outside JSON, no null.",
              "Can the schema answer the feature spec's PM questions?",
              "Are important dimensions and metrics preserved?",
              "Are sparse event-specific fields nullable?",
              "Are nested fields flattened?",
              "Is ORDER BY appropriate for ClickHouse time/entity analysis and dedupe?",
              "Are materialized views useful for reusable aggregates?",
              "Did the design avoid trusting contradicted context over raw evidence?",
            ],
            feature_manifest: input.manifest,
            event_profile: compactEventProfile(input.eventProfile),
            schema_summary: compactSchemaPlan(input.schemaPlan),
            deterministic_issues: input.deterministicIssues,
            retrieved_context_summary: {
              similar_workflows: input.relevantContext.similar_workflows.length,
              column_precedents:
                input.relevantContext.column_type_precedents.length,
              reusable_metrics: input.relevantContext.reusable_metrics.length,
              recommended_joins: input.relevantContext.recommended_joins.length,
              retrieval_notes: input.relevantContext.retrieval_notes,
            },
            known_context_contradictions:
              input.context.generatedContext.contradictions,
          }),
        },
      ],
    });
    if (!review || !["pass", "revise"].includes(String(review.verdict))) {
      return null;
    }
    return {
      ...review,
      issues: asStringArray(review.issues),
      revision_instructions: asStringArray(review.revision_instructions),
      rationale: asStringArray(review.rationale),
    };
  } catch {
    return null;
  }
}

function asStringArray(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value.map(String);
  }
  if (typeof value === "string" && value.trim()) {
    return [value];
  }
  return [];
}

function compactEventProfile(eventProfile: EventProfile) {
  return {
    feature_slug: eventProfile.feature_slug,
    row_count: eventProfile.row_count,
    event_counts: eventProfile.event_counts,
    event_order: eventProfile.event_order,
    fields: eventProfile.fields.map((field) => ({
      path: field.path,
      count: field.count,
      null_count: field.null_count,
      types: field.types,
      sample_values: field.sample_values.slice(0, 2),
    })),
  };
}

function compactSchemaPlan(schemaPlan: SchemaPlan) {
  return {
    table_name: schemaPlan.table_name,
    engine: schemaPlan.engine,
    partition_by: schemaPlan.partition_by,
    order_by: schemaPlan.order_by,
    ttl: schemaPlan.ttl,
    columns: schemaPlan.columns.map((column) => ({
      name: column.name,
      type: column.type,
      source_path: column.source_path,
    })),
    materialized_views: schemaPlan.materialized_views.map((view) => ({
      name: view.name,
      target_table: view.target_table,
      purpose: view.purpose,
      dimensions: view.dimensions,
      metrics: view.metrics,
    })),
  };
}

export async function requestSchemaRevisionDraft(input: {
  featureSlug: string;
  manifest: FeatureManifest;
  eventProfile: EventProfile;
  context: ContextBundle;
  currentPlan: SchemaPlan;
  criticReview: SchemaCriticDraft;
  relevantContext: RelevantContextBundle;
}): Promise<SchemaDesignDraft | null> {
  try {
    const revision = await callGroqJson<SchemaDesignDraft>({
      modelRole: "schema",
      strictJson: false,
      temperature: 0,
      maxTokens: 3500,
      traceName: "groq.schema_revision",
      traceInput: {
        task: "clickhouse_schema_revision",
        feature_slug: input.featureSlug,
        issue_count: input.criticReview.issues?.length ?? 0,
      },
      messages: [
        {
          role: "system",
          content:
            "You are a ClickHouse schema designer revising a rejected instrumentation schema. Return exactly one JSON object with a columns array. Use critic feedback, but raw event evidence remains source of truth.",
        },
        {
          role: "user",
          content: JSON.stringify({
            task: "Revise the schema plan using critic feedback. Keep valid parts of the current plan, fix the issues, and return the same schema draft shape.",
            current_schema_plan: compactSchemaPlan(input.currentPlan),
            critic_review: input.criticReview,
            feature_manifest: input.manifest,
            event_profile: compactEventProfile(input.eventProfile),
            relevant_context: {
              retrieval_notes: input.relevantContext.retrieval_notes,
              recommended_joins: input.relevantContext.recommended_joins.slice(
                0,
                10,
              ),
            },
            constraints: [
              "Return exactly one JSON object. No markdown.",
              "Every non-pipeline source_path must exist in event_profile.fields.",
              "Include job_id, event_name, event_id, timestamp, raw_json, ingested_at.",
              "ORDER BY must include timestamp and event_id.",
              "Sparse fields must stay Nullable.",
              "Do not trust contradicted context over raw event evidence.",
            ],
          }),
        },
      ],
    });
    if (
      !revision ||
      !Array.isArray(revision.columns) ||
      revision.columns.length === 0
    ) {
      return null;
    }
    return revision;
  } catch {
    return null;
  }
}
