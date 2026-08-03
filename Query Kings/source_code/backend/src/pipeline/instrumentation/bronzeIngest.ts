import { readFile } from "node:fs/promises";
import path from "node:path";
import { startActiveObservation } from "@langfuse/tracing";
import {
  executeClickHouse,
  queryClickHouseText,
  sqlString,
} from "../clickhouse.js";
import { recordPipelineStage } from "../tracking.js";
import { writeStageJson } from "./artifacts.js";
import { parseNdjson } from "./eventUtils.js";
import { instrumentationTrackingEvents } from "./trackingEvents.js";

export async function runBronzeIngest(input: {
  jobId: string;
  featureSlug: string;
  specPath: string;
  eventsPath: string;
  artifactRoot: string;
}) {
  const stage = instrumentationTrackingEvents.bronzeIngest;

  return startActiveObservation(stage.observationName, async (span) => {
    span.update({
      input: {
        job_id: input.jobId,
        feature_slug: input.featureSlug,
        spec_path: input.specPath,
        events_path: input.eventsPath,
      },
      metadata: {
        agent: stage.agent,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
    });

    const [specMarkdown, eventsNdjson] = await Promise.all([
      readFile(input.specPath, "utf8"),
      readFile(input.eventsPath, "utf8"),
    ]);
    const rawEvents = parseNdjson(eventsNdjson);

    await executeClickHouse(`INSERT INTO bronze.feature_specs
(job_id, feature_slug, source_path, spec_markdown)
FORMAT JSONEachRow
${JSON.stringify({
  job_id: input.jobId,
  feature_slug: input.featureSlug,
  source_path: input.specPath,
  spec_markdown: specMarkdown,
})}
`);

    const bronzeRows = rawEvents.map((event, index) => ({
      job_id: input.jobId,
      feature_slug: input.featureSlug,
      source_path: input.eventsPath,
      source_line: index + 1,
      event_name: String(event.event ?? "unknown_event"),
      raw_json: JSON.stringify(event),
    }));

    if (bronzeRows.length > 0) {
      await executeClickHouse(`INSERT INTO bronze.feature_events
(job_id, feature_slug, source_path, source_line, event_name, raw_json)
FORMAT JSONEachRow
${bronzeRows.map((row) => JSON.stringify(row)).join("\n")}
`);
    }

    const report = {
      job_id: input.jobId,
      feature_slug: input.featureSlug,
      spec_path: input.specPath,
      events_path: input.eventsPath,
      spec_bytes: Buffer.byteLength(specMarkdown),
      events_bytes: Buffer.byteLength(eventsNdjson),
      spec_rows_inserted: 1,
      event_rows_inserted: bronzeRows.length,
      bronze_spec_table: "bronze.feature_specs",
      bronze_event_table: "bronze.feature_events",
      ingested_at: new Date().toISOString(),
    };

    await writeStageJson(
      input.artifactRoot,
      stage.stageId,
      "bronze_report.json",
      report,
    );

    const validation = await validateBronzeIngest({
      jobId: input.jobId,
      expectedEventRows: bronzeRows.length,
    });

    span.update({
      output: {
        ...report,
        validation,
        artifact: path.join(
          input.artifactRoot,
          stage.stageId,
          "bronze_report.json",
        ),
      },
      level: validation.passed ? "DEFAULT" : "ERROR",
    });

    if (!validation.passed) {
      await recordPipelineStage({
        jobId: input.jobId,
        stageId: stage.stageId,
        stageName: stage.stageName,
        status: "failed",
        stageInput: {
          feature_slug: input.featureSlug,
          spec_path: input.specPath,
          events_path: input.eventsPath,
          source_layer: stage.sourceLayer,
          target_layer: stage.targetLayer,
        },
        stageOutput: { ...report, validation },
        error: validation.failures.join("; "),
      });
      throw new Error(
        `Bronze ingest validation failed: ${validation.failures.join("; ")}`,
      );
    }

    await recordPipelineStage({
      jobId: input.jobId,
      stageId: stage.stageId,
      stageName: stage.stageName,
      status: "completed",
      stageInput: {
        feature_slug: input.featureSlug,
        spec_path: input.specPath,
        events_path: input.eventsPath,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
      stageOutput: {
        ...report,
        validation,
      },
    });

    return {
      specMarkdown,
      eventsNdjson,
      rawEvents,
      report,
    };
  });
}

async function validateBronzeIngest(input: {
  jobId: string;
  expectedEventRows: number;
}) {
  const jobFilter = `job_id = ${sqlString(input.jobId)}`;
  const [specCountText, eventCountText] = await Promise.all([
    executeAndTrim(
      `SELECT count() FROM bronze.feature_specs WHERE ${jobFilter} FORMAT TabSeparated`,
    ),
    executeAndTrim(
      `SELECT count() FROM bronze.feature_events WHERE ${jobFilter} FORMAT TabSeparated`,
    ),
  ]);
  const specRows = Number(specCountText);
  const eventRows = Number(eventCountText);
  const failures: string[] = [];

  if (specRows !== 1) {
    failures.push(`spec_row_count_mismatch expected=1 actual=${specRows}`);
  }
  if (eventRows !== input.expectedEventRows) {
    failures.push(
      `event_row_count_mismatch expected=${input.expectedEventRows} actual=${eventRows}`,
    );
  }

  return {
    passed: failures.length === 0,
    failures,
    expected_spec_rows: 1,
    actual_spec_rows: specRows,
    expected_event_rows: input.expectedEventRows,
    actual_event_rows: eventRows,
  };
}

async function executeAndTrim(sql: string) {
  return queryClickHouseText(sql).then((value) => value.trim());
}
