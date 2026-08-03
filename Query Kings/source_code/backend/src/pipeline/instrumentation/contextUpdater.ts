import path from "node:path";
import { startActiveObservation } from "@langfuse/tracing";
import {
  GeneratedContextRegistry,
  updateGeneratedContext,
} from "../context.js";
import { recordPipelineStage } from "../tracking.js";
import { writeStageJson, writeStageText } from "./artifacts.js";
import { instrumentationTrackingEvents } from "./trackingEvents.js";
import {
  EventProfile,
  FeatureManifest,
  SchemaPlan,
  SilverLoadReport,
} from "./types.js";

export async function runContextUpdater(input: {
  jobId: string;
  featureSlug: string;
  manifest: FeatureManifest;
  schemaPlan: SchemaPlan;
  eventProfile: EventProfile;
  loadReport: SilverLoadReport;
  artifactRoot: string;
}) {
  const stage = instrumentationTrackingEvents.contextUpdater;

  return startActiveObservation(stage.observationName, async (span) => {
    span.update({
      input: {
        feature_slug: input.featureSlug,
        table_name: input.schemaPlan.table_name,
        event_names: input.manifest.event_order,
        validation_passed: input.loadReport.validation.passed,
      },
      metadata: {
        agent: stage.agent,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
    });

    const updatedContext = await updateGeneratedContext({
      job_id: input.jobId,
      feature_slug: input.featureSlug,
      table_name: input.schemaPlan.table_name,
      primary_entity: input.manifest.primary_entity,
      workflow_type: input.manifest.workflow_type,
      event_names: input.manifest.event_order,
      success_event: input.manifest.success_event,
      metric_hints: input.manifest.metric_hints,
      validation: input.loadReport.validation,
      schema_plan: input.schemaPlan,
      event_profile: input.eventProfile,
    });

    await writeStageText(
      input.artifactRoot,
      stage.stageId,
      "context_diff.md",
      renderContextDiff(input.manifest, input.schemaPlan, updatedContext),
    );
    await writeStageJson(
      input.artifactRoot,
      stage.stageId,
      "updated_context.json",
      updatedContext,
    );

    span.update({
      output: {
        generated_features: updatedContext.features.length,
        columns: updatedContext.columns.length,
        workflows: updatedContext.workflows.length,
        metrics: updatedContext.metrics.length,
        joins: updatedContext.joins.length,
        contradictions: updatedContext.contradictions.length,
        artifacts: [
          path.join(input.artifactRoot, stage.stageId, "context_diff.md"),
          path.join(input.artifactRoot, stage.stageId, "updated_context.json"),
        ],
      },
    });

    await recordPipelineStage({
      jobId: input.jobId,
      stageId: stage.stageId,
      stageName: stage.stageName,
      status: "completed",
      stageInput: {
        feature_slug: input.featureSlug,
        table_name: input.schemaPlan.table_name,
        validation_passed: input.loadReport.validation.passed,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
      stageOutput: {
        generated_features: updatedContext.features.length,
        columns: updatedContext.columns.length,
        workflows: updatedContext.workflows.length,
        metrics: updatedContext.metrics.length,
        joins: updatedContext.joins.length,
        contradictions: updatedContext.contradictions.length,
      },
    });

    return updatedContext;
  });
}

function renderContextDiff(
  manifest: FeatureManifest,
  schemaPlan: SchemaPlan,
  registry: GeneratedContextRegistry,
): string {
  return `# Context Diff

## Added Feature

- Feature: ${manifest.feature_name}
- Slug: \`${manifest.feature_slug}\`
- Table: \`silver.${schemaPlan.table_name}\`
- Primary entity: \`${manifest.primary_entity}\`
- Workflow type: \`${manifest.workflow_type}\`
- Events: ${manifest.event_order.map((event) => `\`${event}\``).join(" -> ")}
- Success event: \`${manifest.success_event ?? "none"}\`

## Metric Hints

${manifest.metric_hints.map((metric) => `- ${metric}`).join("\n")}

## Context Notes

${manifest.context_notes.map((note) => `- ${note}`).join("\n")}

## Registry Status

- Known generated features: ${registry.features.length}
- Known columns: ${registry.columns.length}
- Known workflows: ${registry.workflows.length}
- Known metrics: ${registry.metrics.length}
- Known joins: ${registry.joins.length}
- Known context contradictions / gaps / known-issue links: ${registry.contradictions.length}

## Open Contradictions & Gaps (sample)

${
  registry.contradictions.length === 0
    ? "- none"
    : registry.contradictions
        .slice(0, 12)
        .map((item) => `- \`${item.id}\`: ${item.summary}`)
        .join("\n")
}
`;
}
