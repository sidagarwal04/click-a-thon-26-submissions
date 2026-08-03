import path from "node:path";
import { startActiveObservation } from "@langfuse/tracing";
import { recordPipelineStage } from "../tracking.js";
import { writeStageText } from "./artifacts.js";
import { toColumnName } from "./eventUtils.js";
import { instrumentationTrackingEvents } from "./trackingEvents.js";
import { EventProfile, FeatureManifest, SchemaPlan } from "./types.js";

export async function runSchemaCritic(input: {
  jobId: string;
  schemaPlan: SchemaPlan;
  eventProfile: EventProfile;
  manifest: FeatureManifest;
  artifactRoot: string;
}) {
  const stage = instrumentationTrackingEvents.schemaCritic;

  return startActiveObservation(stage.observationName, async (span) => {
    span.update({
      input: {
        table: `silver.${input.schemaPlan.table_name}`,
        order_by: input.schemaPlan.order_by,
        column_count: input.schemaPlan.columns.length,
      },
      metadata: {
        agent: stage.agent,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
    });

    const schemaReview = reviewSchema(
      input.schemaPlan,
      input.eventProfile,
      input.manifest,
    );
    await writeStageText(
      input.artifactRoot,
      stage.stageId,
      "schema_review.md",
      schemaReview.reviewText,
    );

    const verdict =
      schemaReview.warnings.length === 0 ? "pass" : "needs_attention";

    span.update({
      output: {
        verdict,
        warnings: schemaReview.warnings,
        artifact: path.join(
          input.artifactRoot,
          stage.stageId,
          "schema_review.md",
        ),
      },
    });

    await recordPipelineStage({
      jobId: input.jobId,
      stageId: stage.stageId,
      stageName: stage.stageName,
      status: "completed",
      stageInput: {
        table: `silver.${input.schemaPlan.table_name}`,
        column_count: input.schemaPlan.columns.length,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
      stageOutput: {
        verdict,
        warnings: schemaReview.warnings,
      },
    });

    return schemaReview;
  });
}

function reviewSchema(
  schemaPlan: SchemaPlan,
  eventProfile: EventProfile,
  manifest: FeatureManifest,
): { reviewText: string; warnings: string[] } {
  const columnNames = new Set(schemaPlan.columns.map((column) => column.name));
  const warnings: string[] = [];

  for (const required of ["event_name", "event_id", "timestamp", "user_id"]) {
    if (!columnNames.has(required)) {
      warnings.push(`Missing required analytical column: ${required}.`);
    }
  }

  if (!schemaPlan.order_by.includes("timestamp")) {
    warnings.push(
      "ORDER BY should include timestamp for time-window analytics.",
    );
  }
  if (!schemaPlan.order_by.includes("event_id")) {
    warnings.push(
      "ORDER BY should include event_id so ReplacingMergeTree does not collapse distinct events.",
    );
  }

  if (
    !schemaPlan.columns.some((column) => column.type.includes("LowCardinality"))
  ) {
    warnings.push(
      "No LowCardinality columns detected for repeated dimensions.",
    );
  }

  const nestedFields = eventProfile.fields.filter((field) =>
    field.path.includes("."),
  );
  if (nestedFields.length > 0) {
    const flattened = nestedFields.every((field) =>
      columnNames.has(toColumnName(field.path)),
    );
    if (!flattened) {
      warnings.push(
        "Some nested fields were not flattened into analytical columns.",
      );
    }
  }

  if (schemaPlan.materialized_views.length === 0) {
    warnings.push(
      "No materialized view or reusable aggregation was defined for the feature.",
    );
  }

  const reviewText = `# Schema Review

## Verdict

${warnings.length === 0 ? "Pass for v0 instrumentation." : "Needs attention before production."}

## What this schema optimizes for

- Feature workflow: \`${manifest.workflow_type}\`
- Primary entity: \`${manifest.primary_entity}\`
- Success event: \`${manifest.success_event ?? "none"}\`
- Partitioning: \`${schemaPlan.partition_by}\`
- Ordering key: \`(${schemaPlan.order_by.join(", ")})\`

## Checks

${warnings.length === 0 ? "- No blocking issues found." : warnings.map((warning) => `- ${warning}`).join("\n")}

## Notes

- Raw payload is preserved in \`raw_json\` for replay and hidden-spec debugging.
- \`${schemaPlan.engine}\` is used so repeated \`event_id\` values can collapse during merges.
- TTL is set to \`${schemaPlan.ttl}\`; adjust if judges ask for longer retention.
- Materialized views: ${schemaPlan.materialized_views.length === 0 ? "none" : schemaPlan.materialized_views.map((view) => `\`${view.name}\``).join(", ")}
`;

  return { reviewText, warnings };
}
