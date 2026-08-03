import path from "node:path";
import { startActiveObservation } from "@langfuse/tracing";
import { ContextBundle } from "../context.js";
import { callGroqJson } from "../groq.js";
import { getGroqModel } from "../models.js";
import { recordPipelineStage } from "../tracking.js";
import { writeStageJson } from "./artifacts.js";
import { extractSpecEventOrder, inferMetricHints } from "./eventUtils.js";
import { instrumentationTrackingEvents } from "./trackingEvents.js";
import { EventProfile, FeatureManifest } from "./types.js";

const WORKFLOW_TYPES = new Set<FeatureManifest["workflow_type"]>([
  "funnel",
  "revenue_addon",
  "referral_loop",
  "recovery",
  "generic",
]);

export async function runSpecParser(input: {
  jobId: string;
  featureSlug: string;
  specMarkdown: string;
  eventProfile: EventProfile;
  context: ContextBundle;
  artifactRoot: string;
}) {
  const stage = instrumentationTrackingEvents.specParser;
  const model = getGroqModel("default");

  return startActiveObservation(stage.observationName, async (span) => {
    span.update({
      input: {
        feature_slug: input.featureSlug,
        event_names: input.eventProfile.event_order,
        context_features: input.context.generatedContext.features.length,
      },
      metadata: {
        agent: stage.agent,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
        llm_provider: "groq",
        model,
      },
    });

    // Prefer the stronger model for manifest JSON. 8b schema model is too flaky
    // and was hard-failing whole instrumentation runs.
    let llmManifest: FeatureManifest | null = null;
    let llmError: string | null = null;
    try {
      llmManifest = await requestManifestFromLlm(input);
      if (!isManifestShape(llmManifest)) {
        llmError = "LLM returned incomplete manifest shape.";
        llmManifest = null;
      }
    } catch (error) {
      llmError = error instanceof Error ? error.message : String(error);
      llmManifest = null;
    }

    const manifest = normalizeManifestFromEvidence({
      llmManifest,
      featureSlug: input.featureSlug,
      specMarkdown: input.specMarkdown,
      eventProfile: input.eventProfile,
      llmError,
    });

    await writeStageJson(
      input.artifactRoot,
      stage.stageId,
      "feature_manifest.json",
      {
        ...manifest,
        _meta: {
          llm_used: Boolean(llmManifest),
          llm_error: llmError,
          model,
        },
      },
    );

    span.update({
      output: {
        feature_name: manifest.feature_name,
        workflow_type: manifest.workflow_type,
        primary_entity: manifest.primary_entity,
        success_event: manifest.success_event,
        metric_hints: manifest.metric_hints,
        llm_used: Boolean(llmManifest),
        llm_error: llmError,
        artifact: path.join(
          input.artifactRoot,
          stage.stageId,
          "feature_manifest.json",
        ),
      },
    });

    await recordPipelineStage({
      jobId: input.jobId,
      stageId: stage.stageId,
      stageName: stage.stageName,
      status: "completed",
      stageInput: {
        feature_slug: input.featureSlug,
        event_names: input.eventProfile.event_order,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
      stageOutput: {
        feature_name: manifest.feature_name,
        workflow_type: manifest.workflow_type,
        primary_entity: manifest.primary_entity,
        success_event: manifest.success_event,
        metric_hints: manifest.metric_hints,
        llm_used: Boolean(llmManifest),
      },
    });

    return manifest;
  });
}

async function requestManifestFromLlm(input: {
  featureSlug: string;
  specMarkdown: string;
  eventProfile: EventProfile;
  context: ContextBundle;
}): Promise<FeatureManifest> {
  // Keep prompt compact — large context dumps make small/medium models drop required keys.
  const compactContext = {
    known_features: input.context.generatedContext.features
      .slice(0, 12)
      .map((feature) => ({
        feature_slug: feature.feature_slug,
        primary_entity: feature.primary_entity,
        success_event: feature.success_event,
        event_names: feature.event_names,
      })),
    open_contradictions: input.context.generatedContext.contradictions
      .slice(0, 8)
      .map((item) => item.summary),
    instrumentation_notes_excerpt: input.context.instrumentationNotes.slice(
      0,
      2500,
    ),
  };

  return callGroqJson<FeatureManifest>({
    modelRole: "default",
    temperature: 0,
    maxTokens: 1200,
    messages: [
      {
        role: "system",
        content:
          "You extract a feature instrumentation manifest. Return one JSON object only. Every required key must be present. Do not invent event names that are absent from the event profile.",
      },
      {
        role: "user",
        content: `Build a feature manifest for ClickHouse schema design.

Required JSON keys:
{
  "feature_slug": string,
  "feature_name": string,
  "primary_entity": string,
  "workflow_type": "funnel" | "revenue_addon" | "referral_loop" | "recovery" | "generic",
  "event_order": string[],
  "success_event": string | null,
  "metric_hints": string[],
  "context_notes": string[]
}

Rules:
- feature_slug must be "${input.featureSlug}"
- event_order must use only event names from event_profile.event_order (or empty if none)
- success_event must be one of event_order or null
- primary_entity should be the main grain for analytics (usually an *_id field present in the events)
- metric_hints should be PM questions/metrics implied by the spec
- context_notes: short caveats only

feature_slug: ${input.featureSlug}

spec_markdown:
${input.specMarkdown.slice(0, 6000)}

event_profile:
${JSON.stringify(
  {
    event_order: input.eventProfile.event_order,
    event_counts: input.eventProfile.event_counts,
    row_count: input.eventProfile.row_count,
    fields: input.eventProfile.fields.slice(0, 80).map((field) => ({
      path: field.path,
      null_count: field.null_count,
      count: field.count,
      types: field.types,
    })),
  },
  null,
  2,
)}

compact_context:
${JSON.stringify(compactContext, null, 2)}
`,
      },
    ],
    traceName: instrumentationTrackingEvents.specParser.generationName,
    traceInput: {
      task: "feature_manifest_for_schema_generation",
      feature_slug: input.featureSlug,
      event_names: input.eventProfile.event_order,
      row_count: input.eventProfile.row_count,
      field_count: input.eventProfile.fields.length,
    },
  });
}

function isManifestShape(value: unknown): value is FeatureManifest {
  if (!value || typeof value !== "object") {
    return false;
  }
  const manifest = value as FeatureManifest;
  return (
    typeof manifest.feature_slug === "string" &&
    typeof manifest.feature_name === "string" &&
    typeof manifest.primary_entity === "string" &&
    typeof manifest.workflow_type === "string" &&
    Array.isArray(manifest.event_order) &&
    Array.isArray(manifest.metric_hints) &&
    Array.isArray(manifest.context_notes)
  );
}

/**
 * Normalize LLM output against evidence. No feature-specific branches.
 * Event names always come from the spec/profile evidence when available.
 */
function normalizeManifestFromEvidence(input: {
  llmManifest: FeatureManifest | null;
  featureSlug: string;
  specMarkdown: string;
  eventProfile: EventProfile;
  llmError: string | null;
}): FeatureManifest {
  const evidenceEvents = extractSpecEventOrder(
    input.specMarkdown,
    input.eventProfile.event_order,
  );
  const llm = input.llmManifest;

  const eventOrder =
    evidenceEvents.length > 0
      ? evidenceEvents
      : Array.isArray(llm?.event_order) && llm.event_order.length > 0
        ? llm.event_order.map(String)
        : input.eventProfile.event_order;

  const workflowType = normalizeWorkflowType(llm?.workflow_type, eventOrder);
  const primaryEntity =
    (llm?.primary_entity && String(llm.primary_entity).trim()) ||
    inferPrimaryEntityFromProfile(input.eventProfile);

  const successFromLlm =
    llm?.success_event && eventOrder.includes(String(llm.success_event))
      ? String(llm.success_event)
      : null;

  const metricHints =
    Array.isArray(llm?.metric_hints) && llm.metric_hints.length > 0
      ? llm.metric_hints.map(String)
      : inferMetricHints(workflowType, eventOrder);

  const contextNotes = [
    ...(Array.isArray(llm?.context_notes) ? llm.context_notes.map(String) : []),
    ...(input.llmError
      ? [
          `LLM manifest unavailable (${input.llmError}); filled missing fields from event profile + spec evidence only.`,
        ]
      : []),
  ];

  return {
    feature_slug: input.featureSlug,
    feature_name:
      (llm?.feature_name && String(llm.feature_name).trim()) ||
      titleCaseSlug(input.featureSlug),
    primary_entity: primaryEntity,
    workflow_type: workflowType,
    event_order: eventOrder,
    success_event: successFromLlm ?? eventOrder.at(-1) ?? null,
    metric_hints: metricHints,
    context_notes: uniqueStrings(contextNotes),
  };
}

function normalizeWorkflowType(
  value: unknown,
  eventOrder: string[],
): FeatureManifest["workflow_type"] {
  if (
    typeof value === "string" &&
    WORKFLOW_TYPES.has(value as FeatureManifest["workflow_type"])
  ) {
    return value as FeatureManifest["workflow_type"];
  }
  // Structural default only — no product-feature keyword tables.
  return eventOrder.length >= 2 ? "funnel" : "generic";
}

/**
 * Generic entity pick: prefer non-envelope *_id fields with high coverage.
 * Envelope-ish ids (user_id, application_id) used only if nothing better exists.
 */
function inferPrimaryEntityFromProfile(eventProfile: EventProfile): string {
  const rowCount = Math.max(eventProfile.row_count, 1);
  const envelope = new Set([
    "id",
    "event_id",
    "job_id",
    "user_id",
    "application_id",
    "app_session_id",
    "session_id",
  ]);

  const idFields = eventProfile.fields
    .filter((field) => {
      const leaf = field.path.split(".").at(-1) ?? field.path;
      return leaf.endsWith("_id") || leaf === "id";
    })
    .map((field) => {
      const leaf = field.path.split(".").at(-1) ?? field.path;
      const coverage = (field.count - field.null_count) / rowCount;
      return { leaf, coverage, path: field.path };
    })
    .filter((field) => field.coverage >= 0.3);

  const specific = idFields
    .filter((field) => !envelope.has(field.leaf))
    .sort((a, b) => b.coverage - a.coverage);
  if (specific[0]) {
    return specific[0].leaf;
  }

  const preferredEnvelope = ["application_id", "user_id", "app_session_id"];
  for (const name of preferredEnvelope) {
    if (idFields.some((field) => field.leaf === name)) {
      return name;
    }
  }

  return idFields[0]?.leaf ?? "user_id";
}

function titleCaseSlug(slug: string) {
  return slug
    .split(/[_-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}
