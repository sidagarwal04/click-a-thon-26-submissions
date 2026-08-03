import { retrieveRelevantContextForSpec } from "../../context.js";
import { buildSchemaPlan } from "./fallback.js";
import {
  normalizeDesignDraft,
  repairSchemaPlan,
  reviewSchemaPlan,
} from "./guardrails.js";
import {
  requestSchemaCriticReview,
  requestSchemaDesignDraft,
  requestSchemaRevisionDraft,
} from "./prompts.js";
import { RunSchemaGeneratorInput, SchemaDesignLoop } from "./types.js";

export async function runSchemaDesignLoop(
  input: RunSchemaGeneratorInput,
): Promise<SchemaDesignLoop> {
  const iterations: SchemaDesignLoop["iterations"] = [];
  // Evidence-based plan is always available — LLM is assistive, not required.
  const fallbackPlan = buildSchemaPlan(input.manifest, input.eventProfile);
  let schemaPlan = fallbackPlan;
  let mode: SchemaDesignLoop["mode"] = "deterministic_fallback";

  const relevantContext = retrieveRelevantContextForSpec({
    context: input.context,
    featureSlug: input.featureSlug,
    workflowType: input.manifest.workflow_type,
    primaryEntity: input.manifest.primary_entity,
    eventNames: input.manifest.event_order,
    fieldPaths: input.eventProfile.fields.map((field) => field.path),
    metricHints: input.manifest.metric_hints,
  });

  const draft = await requestSchemaDesignDraft(input, relevantContext);

  if (draft) {
    mode = "llm_assisted";
    schemaPlan = normalizeDesignDraft(
      draft,
      fallbackPlan,
      input.eventProfile,
      input.manifest,
    );
    iterations.push({
      iteration: 1,
      actor: "schema_designer",
      summary:
        "LLM schema designer proposed a full ClickHouse schema plan from spec, profile, and context evidence.",
      issues: [
        ...(draft.rationale ?? []),
        ...(draft.context_assumptions ?? []).map(
          (assumption) =>
            `${assumption.trusted ? "trusted" : "not_trusted"} context: ${assumption.claim} (${assumption.evidence})`,
        ),
      ],
    });
  } else {
    iterations.push({
      iteration: 1,
      actor: "schema_designer",
      summary:
        "LLM schema designer unavailable or returned unusable JSON; using evidence-based schema plan from event profile.",
      issues: [
        "No invented schema: columns/types derived from profiled event fields only.",
      ],
    });
  }

  const criticReview = await requestSchemaCriticReview({
    ...input,
    schemaPlan,
    relevantContext,
    deterministicIssues: reviewSchemaPlan(schemaPlan, input.eventProfile),
  });

  if (criticReview) {
    const criticIssues = [
      ...(criticReview.issues ?? []),
      ...(criticReview.rationale ?? []),
    ];
    iterations.push({
      iteration: 1,
      actor: "schema_critic",
      summary:
        criticReview.verdict === "revise"
          ? "LLM schema critic requested a schema revision."
          : "LLM schema critic passed the schema plan.",
      issues: criticIssues,
    });

    if (criticReview.verdict === "revise") {
      const revision = await requestSchemaRevisionDraft({
        ...input,
        currentPlan: schemaPlan,
        criticReview,
        relevantContext,
      });
      if (revision) {
        schemaPlan = normalizeDesignDraft(
          revision,
          fallbackPlan,
          input.eventProfile,
          input.manifest,
        );
        iterations.push({
          iteration: 2,
          actor: "schema_designer_revision",
          summary:
            "LLM schema designer revised the plan using schema critic feedback.",
          issues: revision.rationale ?? [],
        });
      } else {
        iterations.push({
          iteration: 2,
          actor: "schema_designer_revision",
          summary:
            "LLM revision unavailable; keeping current plan and applying deterministic guardrails.",
          issues: criticReview.revision_instructions ?? [],
        });
      }
    }
  } else {
    iterations.push({
      iteration: 1,
      actor: "schema_critic",
      summary:
        "LLM schema critic unavailable; deterministic guardrails remain the critic of record.",
      issues: [],
    });
  }

  const firstReview = reviewSchemaPlan(schemaPlan, input.eventProfile);
  iterations.push({
    iteration: 1,
    actor: "deterministic_guardrail",
    summary:
      firstReview.length === 0
        ? "Draft passed guardrails."
        : "Draft had guardrail issues.",
    issues: firstReview,
  });

  if (firstReview.length > 0) {
    schemaPlan = repairSchemaPlan(
      schemaPlan,
      input.manifest,
      input.eventProfile,
    );
    const secondReview = reviewSchemaPlan(schemaPlan, input.eventProfile);
    iterations.push({
      iteration: 2,
      actor: "schema_repair",
      summary:
        secondReview.length === 0
          ? "Deterministic repair produced an executable schema plan."
          : "Deterministic repair left unresolved issues.",
      issues: secondReview,
    });

    if (secondReview.length > 0) {
      // Last resort: pure evidence plan (always valid by construction).
      schemaPlan = fallbackPlan;
      iterations.push({
        iteration: 3,
        actor: "schema_repair",
        summary:
          "Falling back to pure evidence-based schema plan after unresolved guardrail issues.",
        issues: secondReview,
      });
    }
  }

  return {
    mode,
    iterations,
    final_plan: schemaPlan,
  };
}
