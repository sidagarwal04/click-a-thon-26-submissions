import path from "node:path";
import { startActiveObservation } from "@langfuse/tracing";
import { loadContextBundle } from "./context.js";
import { writeJobRootJson } from "./instrumentation/artifacts.js";
import { completedInstrumentationStageIds } from "./instrumentation/trackingEvents.js";
import { runInstrumentationAgent } from "./instrumentation.js";
import { ensurePipelineLayers } from "./layers.js";
import { pipelineStages } from "./stages.js";
import { recordPipelineRun, recordPipelineStage } from "./tracking.js";
import {
  publishActiveTraceIfEnabled,
  shutdownLangfuse,
  startLangfuse,
} from "../tracing/langfuse.js";

type RunPipelineInput = {
  specFolder: string;
};

export async function runPipeline(input: RunPipelineInput) {
  startLangfuse();

  const repoRoot = path.resolve(process.cwd(), "..");
  const specFolder = path.resolve(process.cwd(), input.specFolder);
  const jobId = createJobId(specFolder);
  const featureSlug = normalizeFeatureSlug(path.basename(specFolder));
  const startedAt = new Date().toISOString();
  let traceId = "";
  // Path-shaped id only — content is stored in ClickHouse ops.job_artifacts.
  const artifactRoot = path.join(repoRoot, "backend", "artifacts", jobId);

  console.log(`Starting pipeline`);
  console.log(`Job ID: ${jobId}`);
  console.log(`Spec folder: ${specFolder}`);
  console.log(`Artifacts: ops.job_artifacts (job_id=${jobId})`);
  console.log("");

  try {
    await startActiveObservation("schema-kings.pipeline", async (rootSpan) => {
      traceId = rootSpan.traceId;
      // Mark public immediately so judges can open the link without login.
      publishActiveTraceIfEnabled(rootSpan);
      rootSpan.update({
        input: {
          job_id: jobId,
          spec_folder: specFolder,
        },
        metadata: {
          pipeline: "feature-spec-to-clickhouse-schema",
          environment: process.env.NODE_ENV ?? "local",
          model: process.env.GROQ_MODEL ?? "openai/gpt-oss-20b",
        },
      });

      await recordPipelineRun({
        jobId,
        featureSlug,
        specFolder,
        status: "started",
        traceId,
        startedAt,
      });

      await ensurePipelineLayers(repoRoot);

      const context = await startActiveObservation(
        "00_context_provider",
        async (span) => {
          span.update({
            input: {
              base_context: "base_context.md",
              existing_ddl: "data/ddl.sql",
              instrumentation_notes: "data/instrumentation_notes.md",
            },
            metadata: {
              agent: "context_provider_v0",
            },
          });

          const loadedContext = await loadContextBundle(repoRoot);
          span.update({
            output: {
              generated_features:
                loadedContext.generatedContext.features.length,
              contradictions:
                loadedContext.generatedContext.contradictions.length,
            },
          });
          await recordPipelineStage({
            jobId,
            stageId: "00_context_provider",
            stageName: "Context Provider",
            status: "completed",
            stageInput: {
              base_context: "base_context.md",
              existing_ddl: "data/ddl.sql",
              instrumentation_notes: "data/instrumentation_notes.md",
            },
            stageOutput: {
              generated_features:
                loadedContext.generatedContext.features.length,
              contradictions:
                loadedContext.generatedContext.contradictions.length,
            },
          });
          return loadedContext;
        },
      );
      console.log(`[done] context_provider: loaded base + generated context`);

      const result = await runInstrumentationAgent({
        repoRoot,
        specFolder,
        jobId,
        artifactRoot,
        context,
      });

      const completedStages = new Set([
        ...completedInstrumentationStageIds,
        "12_trace_summary",
      ]);

      console.log("");
      console.log("Pipeline stage status:");
      for (const stage of pipelineStages) {
        const status = completedStages.has(stage.id) ? "done" : "planned";
        console.log(`[${status}] ${stage.id}: ${stage.name}`);
      }
      console.log(
        "[planned] stages are reserved for the Analytics Agent harness and are not executed by this instrumentation run yet.",
      );

      const runSummary = {
        job_id: jobId,
        feature_slug: result.featureSlug,
        table_name: `silver.${result.schemaPlan.table_name}`,
        row_count: result.eventProfile.row_count,
        event_names: result.manifest.event_order,
        primary_entity: result.manifest.primary_entity,
        success_event: result.manifest.success_event,
        silver_loaded: result.loadReport.validation.passed,
        silver_inserted_rows: result.loadReport.inserted_rows,
        artifacts: artifactRoot,
        model: process.env.GROQ_MODEL ?? "openai/gpt-oss-20b",
        groq_used: Boolean(process.env.GROQ_API_KEY),
        langfuse_trace_id: rootSpan.traceId,
      };

      await startActiveObservation("12_trace_summary", async (span) => {
        span.update({
          input: {
            artifact_root: artifactRoot,
          },
          metadata: {
            agent: "pipeline_orchestrator",
          },
        });
        await writeJobRootJson(artifactRoot, "run_summary.json", runSummary);
        span.update({
          output: runSummary,
        });
        await recordPipelineStage({
          jobId,
          stageId: "12_trace_summary",
          stageName: "Trace Summary",
          status: "completed",
          stageInput: {
            artifact_root: artifactRoot,
          },
          stageOutput: runSummary,
        });
      });

      await recordPipelineRun({
        jobId,
        featureSlug: result.featureSlug,
        specFolder,
        status: "completed",
        traceId,
        startedAt,
        completedAt: new Date().toISOString(),
        summary: runSummary,
      });

      rootSpan.update({
        output: {
          job_id: jobId,
          feature_slug: result.featureSlug,
          table_name: runSummary.table_name,
          artifact_root: artifactRoot,
          trace_id: rootSpan.traceId,
        },
      });

      console.log("");
      console.log(`Instrumentation agent finished for ${result.featureSlug}.`);
      console.log(`Generated table: silver.${result.schemaPlan.table_name}`);
      console.log(
        `Schema artifact: ops.job_artifacts / ${jobId} / 04_schema_generator/schema.sql`,
      );
      console.log(`Langfuse trace ID: ${rootSpan.traceId}`);
    });
  } catch (error) {
    await recordPipelineRun({
      jobId,
      featureSlug,
      specFolder,
      status: "failed",
      traceId,
      startedAt,
      completedAt: new Date().toISOString(),
      summary: {
        error: error instanceof Error ? error.message : String(error),
      },
    });
    throw error;
  } finally {
    await shutdownLangfuse();
  }
}

function normalizeFeatureSlug(folderName: string) {
  return folderName.replace(/^\d+_/, "").replace(/[^a-zA-Z0-9]+/g, "_");
}

function createJobId(specFolder: string) {
  const slug = specFolder.split("/").filter(Boolean).at(-1) ?? "unknown_spec";
  const timestamp = new Date()
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\..+/, "");
  return `${timestamp}_${slug}`;
}
