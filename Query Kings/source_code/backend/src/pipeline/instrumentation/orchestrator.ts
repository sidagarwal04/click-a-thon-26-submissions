import path from "node:path";
import { ContextBundle } from "../context.js";
import { runBronzeIngest } from "./bronzeIngest.js";
import { runContextUpdater } from "./contextUpdater.js";
import { normalizeFeatureSlug } from "./eventUtils.js";
import { runEventProfiler } from "./eventProfiler.js";
import { runSchemaCritic } from "./schemaCritic.js";
import { runSchemaGenerator } from "./schemaGenerator.js";
import { runSilverLoader } from "./silverLoader.js";
import { runSpecParser } from "./specParser.js";
import { writeStageJson } from "./artifacts.js";
import {
  EventProfile,
  FeatureManifest,
  MappingPlan,
  SchemaPlan,
  SilverLoadReport,
} from "./types.js";

const MAX_SCHEMA_LOAD_ATTEMPTS = 2;

type RepairAttempt = {
  attempt: number;
  status: "failed" | "completed";
  feedback: string[];
};

type SchemaLoadResult = {
  schemaPlan: SchemaPlan;
  schemaSql: string;
  mappingPlan: MappingPlan;
  loadReport: SilverLoadReport;
};

export async function runInstrumentationAgent(input: {
  repoRoot: string;
  specFolder: string;
  jobId: string;
  artifactRoot: string;
  context: ContextBundle;
}) {
  const specPath = path.join(input.specFolder, "spec.md");
  const eventsPath = path.join(input.specFolder, "events.ndjson");
  const featureSlug = normalizeFeatureSlug(path.basename(input.specFolder));

  const bronze = await runBronzeIngest({
    jobId: input.jobId,
    featureSlug,
    specPath,
    eventsPath,
    artifactRoot: input.artifactRoot,
  });

  const eventProfile = await runEventProfiler({
    jobId: input.jobId,
    featureSlug,
    eventsPath,
    rawEvents: bronze.rawEvents,
    artifactRoot: input.artifactRoot,
  });

  const manifest = await runSpecParser({
    jobId: input.jobId,
    featureSlug,
    specMarkdown: bronze.specMarkdown,
    eventProfile,
    context: input.context,
    artifactRoot: input.artifactRoot,
  });

  const { schemaPlan, schemaSql, mappingPlan, loadReport } =
    await runSchemaLoadRepairLoop({
      jobId: input.jobId,
      featureSlug,
      manifest,
      eventProfile,
      context: input.context,
      rawEvents: bronze.rawEvents,
      artifactRoot: input.artifactRoot,
    });

  await runContextUpdater({
    jobId: input.jobId,
    featureSlug,
    manifest,
    schemaPlan,
    eventProfile,
    loadReport,
    artifactRoot: input.artifactRoot,
  });

  return {
    featureSlug,
    eventProfile,
    manifest,
    schemaPlan,
    schemaSql,
    mappingPlan,
    loadReport,
  };
}

async function runSchemaLoadRepairLoop(input: {
  jobId: string;
  featureSlug: string;
  manifest: FeatureManifest;
  eventProfile: EventProfile;
  context: ContextBundle;
  rawEvents: Record<string, unknown>[];
  artifactRoot: string;
}): Promise<SchemaLoadResult> {
  let executionFeedback: string[] = [];
  const repairAttempts: RepairAttempt[] = [];

  for (let attempt = 1; attempt <= MAX_SCHEMA_LOAD_ATTEMPTS; attempt += 1) {
    const generated = await runSchemaGenerator({
      jobId: input.jobId,
      featureSlug: input.featureSlug,
      manifest: input.manifest,
      eventProfile: input.eventProfile,
      context: input.context,
      artifactRoot: input.artifactRoot,
      executionFeedback,
    });

    const schemaReview = await runSchemaCritic({
      jobId: input.jobId,
      schemaPlan: generated.schemaPlan,
      eventProfile: input.eventProfile,
      manifest: input.manifest,
      artifactRoot: input.artifactRoot,
    });

    if (schemaReview.warnings.length > 0) {
      executionFeedback = [
        `Schema critic blocked attempt ${attempt}: ${schemaReview.warnings.join("; ")}`,
      ];
      repairAttempts.push(failedAttempt(attempt, executionFeedback));
      if (attempt < MAX_SCHEMA_LOAD_ATTEMPTS) {
        continue;
      }
      await writeRepairLoopArtifact(input.artifactRoot, repairAttempts);
      throw new Error(executionFeedback[0]);
    }

    try {
      const loadReport = await runSilverLoader({
        jobId: input.jobId,
        schemaPlan: generated.schemaPlan,
        schemaSql: generated.schemaSql,
        eventProfile: input.eventProfile,
        manifest: input.manifest,
        rawEvents: input.rawEvents,
        artifactRoot: input.artifactRoot,
      });
      repairAttempts.push({
        attempt,
        status: "completed",
        feedback: [],
      });
      await writeRepairLoopArtifact(input.artifactRoot, repairAttempts);
      return { ...generated, loadReport };
    } catch (error) {
      executionFeedback = [
        `Silver load or validation failed on attempt ${attempt}: ${error instanceof Error ? error.message : String(error)}`,
      ];
      repairAttempts.push(failedAttempt(attempt, executionFeedback));
      if (attempt >= MAX_SCHEMA_LOAD_ATTEMPTS) {
        await writeRepairLoopArtifact(input.artifactRoot, repairAttempts);
        throw error;
      }
    }
  }

  await writeRepairLoopArtifact(input.artifactRoot, repairAttempts);
  throw new Error("Instrumentation repair loop ended without a loaded schema.");
}

function failedAttempt(attempt: number, feedback: string[]): RepairAttempt {
  return {
    attempt,
    status: "failed",
    feedback,
  };
}

async function writeRepairLoopArtifact(
  artifactRoot: string,
  attempts: RepairAttempt[],
) {
  await writeStageJson(
    artifactRoot,
    "04_schema_generator",
    "repair_loop.json",
    {
      max_attempts: MAX_SCHEMA_LOAD_ATTEMPTS,
      attempts,
    },
  );
}
