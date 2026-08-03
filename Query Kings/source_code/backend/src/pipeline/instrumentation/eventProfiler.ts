import path from "node:path";
import { startActiveObservation } from "@langfuse/tracing";
import { recordPipelineStage } from "../tracking.js";
import { writeStageJson } from "./artifacts.js";
import { profileEvents } from "./eventUtils.js";
import { instrumentationTrackingEvents } from "./trackingEvents.js";

export async function runEventProfiler(input: {
  jobId: string;
  featureSlug: string;
  eventsPath: string;
  rawEvents: Record<string, unknown>[];
  artifactRoot: string;
}) {
  const stage = instrumentationTrackingEvents.eventProfiler;

  return startActiveObservation(stage.observationName, async (span) => {
    span.update({
      input: {
        feature_slug: input.featureSlug,
        events_file: input.eventsPath,
        raw_event_rows: input.rawEvents.length,
      },
      metadata: {
        agent: stage.agent,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
    });

    const profile = profileEvents(input.featureSlug, input.rawEvents);
    await writeStageJson(
      input.artifactRoot,
      stage.stageId,
      "event_profile.json",
      profile,
    );

    span.update({
      output: {
        row_count: profile.row_count,
        event_counts: profile.event_counts,
        field_count: profile.fields.length,
        artifact: path.join(
          input.artifactRoot,
          stage.stageId,
          "event_profile.json",
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
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
      stageOutput: {
        row_count: profile.row_count,
        event_counts: profile.event_counts,
        field_count: profile.fields.length,
      },
    });

    return profile;
  });
}
