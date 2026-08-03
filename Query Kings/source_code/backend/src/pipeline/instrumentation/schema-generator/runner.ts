import path from "node:path";
import { startActiveObservation } from "@langfuse/tracing";
import { recordPipelineStage } from "../../tracking.js";
import { writeStageJson, writeStageText } from "../artifacts.js";
import { instrumentationTrackingEvents } from "../trackingEvents.js";
import { runSchemaDesignLoop } from "./designLoop.js";
import {
  buildMappingPlan,
  renderCreateTableSql,
  renderMaterializedViewsSql,
} from "./render.js";
import { RunSchemaGeneratorInput } from "./types.js";

export async function runSchemaGenerator(input: RunSchemaGeneratorInput) {
  const stage = instrumentationTrackingEvents.schemaGenerator;

  return startActiveObservation(stage.observationName, async (span) => {
    span.update({
      input: {
        feature_slug: input.featureSlug,
        workflow_type: input.manifest.workflow_type,
        primary_entity: input.manifest.primary_entity,
        field_count: input.eventProfile.fields.length,
        execution_feedback: input.executionFeedback ?? [],
      },
      metadata: {
        agent: stage.agent,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
    });

    const designLoop = await runSchemaDesignLoop(input);
    const schemaPlan = designLoop.final_plan;
    const schemaSql = renderCreateTableSql(schemaPlan);
    const mappingPlan = buildMappingPlan(schemaPlan);
    const materializedViewsSql = renderMaterializedViewsSql(schemaPlan);

    await writeStageJson(
      input.artifactRoot,
      stage.stageId,
      "schema_plan.json",
      schemaPlan,
    );
    await writeStageJson(
      input.artifactRoot,
      stage.stageId,
      "schema_design_loop.json",
      designLoop,
    );
    await writeStageText(
      input.artifactRoot,
      stage.stageId,
      "schema.sql",
      schemaSql,
    );
    await writeStageText(
      input.artifactRoot,
      stage.stageId,
      "materialized_views.sql",
      materializedViewsSql,
    );
    await writeStageJson(
      input.artifactRoot,
      stage.stageId,
      "mapping.json",
      mappingPlan,
    );

    span.update({
      output: {
        table: `silver.${schemaPlan.table_name}`,
        engine: schemaPlan.engine,
        partition_by: schemaPlan.partition_by,
        order_by: schemaPlan.order_by,
        column_count: schemaPlan.columns.length,
        materialized_views: schemaPlan.materialized_views.map(
          (view) => view.name,
        ),
        loop_iterations: designLoop.iterations.length,
        artifacts: [
          path.join(
            input.artifactRoot,
            stage.stageId,
            "schema_design_loop.json",
          ),
          path.join(input.artifactRoot, stage.stageId, "schema_plan.json"),
          path.join(input.artifactRoot, stage.stageId, "schema.sql"),
          path.join(
            input.artifactRoot,
            stage.stageId,
            "materialized_views.sql",
          ),
          path.join(input.artifactRoot, stage.stageId, "mapping.json"),
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
        workflow_type: input.manifest.workflow_type,
        primary_entity: input.manifest.primary_entity,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
      stageOutput: {
        table: `silver.${schemaPlan.table_name}`,
        engine: schemaPlan.engine,
        partition_by: schemaPlan.partition_by,
        order_by: schemaPlan.order_by,
        column_count: schemaPlan.columns.length,
        materialized_views: schemaPlan.materialized_views.map(
          (view) => view.name,
        ),
        loop_iterations: designLoop.iterations.length,
      },
    });

    return { schemaPlan, schemaSql, mappingPlan };
  });
}
