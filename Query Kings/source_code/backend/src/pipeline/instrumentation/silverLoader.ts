import path from "node:path";
import { startActiveObservation } from "@langfuse/tracing";
import {
  executeClickHouse,
  getClickHouseConfig,
  queryClickHouseText,
  sqlString,
} from "../clickhouse.js";
import { recordPipelineStage } from "../tracking.js";
import { writeStageJson } from "./artifacts.js";
import { getPath } from "./eventUtils.js";
import { instrumentationTrackingEvents } from "./trackingEvents.js";
import {
  EventProfile,
  FeatureManifest,
  SchemaPlan,
  SilverLoadReport,
} from "./types.js";

export async function runSilverLoader(input: {
  jobId: string;
  schemaPlan: SchemaPlan;
  schemaSql: string;
  eventProfile: EventProfile;
  manifest: FeatureManifest;
  rawEvents: Record<string, unknown>[];
  artifactRoot: string;
}) {
  const stage = instrumentationTrackingEvents.silverLoader;

  return startActiveObservation(stage.observationName, async (span) => {
    span.update({
      input: {
        table: `silver.${input.schemaPlan.table_name}`,
        row_count: input.eventProfile.row_count,
        clickhouse_url: getClickHouseConfig().url,
      },
      metadata: {
        agent: stage.agent,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
    });

    const normalizedRows = input.rawEvents.map((event) =>
      normalizeEventForInsert({
        event,
        jobId: input.jobId,
        schemaPlan: input.schemaPlan,
      }),
    );
    const insertColumns = input.schemaPlan.columns
      .filter((column) => column.name !== "ingested_at")
      .map((column) => column.name);
    const jsonEachRow = normalizedRows
      .map((row) => JSON.stringify(row))
      .join("\n");

    await recreateGeneratedTables(input.schemaPlan);
    await executeClickHouse(input.schemaSql);
    for (const view of input.schemaPlan.materialized_views) {
      await executeClickHouse(view.target_table_sql);
      await executeClickHouse(view.view_sql);
    }
    await executeClickHouse(`INSERT INTO silver.${input.schemaPlan.table_name}
(${insertColumns.join(", ")})
FORMAT JSONEachRow
${jsonEachRow}
`);

    const validation = await validateSilverLoad({
      jobId: input.jobId,
      schemaPlan: input.schemaPlan,
      eventProfile: input.eventProfile,
      manifest: input.manifest,
    });

    const report: SilverLoadReport = {
      job_id: input.jobId,
      table: `silver.${input.schemaPlan.table_name}`,
      inserted_rows: normalizedRows.length,
      validation,
      loaded_at: new Date().toISOString(),
    };

    await writeStageJson(
      input.artifactRoot,
      stage.stageId,
      "load_report.json",
      report,
    );

    span.update({
      output: {
        table: report.table,
        inserted_rows: report.inserted_rows,
        validation_passed: validation.passed,
        artifact: path.join(
          input.artifactRoot,
          stage.stageId,
          "load_report.json",
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
          table: `silver.${input.schemaPlan.table_name}`,
          expected_rows: input.eventProfile.row_count,
          source_layer: stage.sourceLayer,
          target_layer: stage.targetLayer,
        },
        stageOutput: report,
        error: validation.failures.join("; "),
      });
      throw new Error(
        `Silver load validation failed for ${report.table}: ${validation.failures.join("; ")}`,
      );
    }

    await recordPipelineStage({
      jobId: input.jobId,
      stageId: stage.stageId,
      stageName: stage.stageName,
      status: "completed",
      stageInput: {
        table: `silver.${input.schemaPlan.table_name}`,
        expected_rows: input.eventProfile.row_count,
        source_layer: stage.sourceLayer,
        target_layer: stage.targetLayer,
      },
      stageOutput: report,
    });

    return report;
  });
}

async function recreateGeneratedTables(schemaPlan: SchemaPlan) {
  for (const view of schemaPlan.materialized_views) {
    await executeClickHouse(`DROP VIEW IF EXISTS ${qualifiedName(view.name)}`);
  }

  for (const view of schemaPlan.materialized_views) {
    await executeClickHouse(
      `DROP TABLE IF EXISTS ${qualifiedName(view.target_table)}`,
    );
  }

  await executeClickHouse(
    `DROP TABLE IF EXISTS ${qualifiedName(`silver.${schemaPlan.table_name}`)}`,
  );
}

function qualifiedName(name: string) {
  const parts = name.split(".");
  if (
    parts.length === 0 ||
    parts.length > 2 ||
    parts.some((part) => !/^[a-zA-Z_][a-zA-Z0-9_]*$/.test(part))
  ) {
    throw new Error(`Unsafe ClickHouse identifier: ${name}`);
  }
  return parts.join(".");
}

function normalizeEventForInsert(input: {
  event: Record<string, unknown>;
  jobId: string;
  schemaPlan: SchemaPlan;
}) {
  const row: Record<string, unknown> = {};
  for (const column of input.schemaPlan.columns) {
    if (column.name === "ingested_at") {
      continue;
    }

    if (column.name === "job_id") {
      row[column.name] = input.jobId;
      continue;
    }

    if (column.name === "raw_json") {
      row[column.name] = JSON.stringify(input.event);
      continue;
    }

    if (column.name === "event_name") {
      row[column.name] = input.event.event ?? "";
      continue;
    }

    if (column.name === "event_id") {
      row[column.name] = input.event.id ?? "";
      continue;
    }

    const value = column.source_path
      ? getPath(input.event, column.source_path)
      : null;
    row[column.name] = normalizeValueForClickHouse(value, column.type);
  }
  return row;
}

function normalizeValueForClickHouse(value: unknown, columnType: string) {
  if (value === undefined || value === "") {
    return columnType.includes("Nullable(") ? null : defaultValue(columnType);
  }

  if (value === null) {
    return columnType.includes("Nullable(") ? null : defaultValue(columnType);
  }

  if (columnType.includes("DateTime")) {
    return String(value).replace("T", " ").replace("Z", "");
  }

  return value;
}

function defaultValue(columnType: string) {
  if (columnType.includes("String")) {
    return "";
  }
  if (columnType.includes("Bool")) {
    return false;
  }
  if (
    columnType.includes("UInt") ||
    columnType.includes("Int") ||
    columnType.includes("Float")
  ) {
    return 0;
  }
  return "";
}

async function validateSilverLoad(input: {
  jobId: string;
  schemaPlan: SchemaPlan;
  eventProfile: EventProfile;
  manifest: FeatureManifest;
}) {
  const table = `silver.${input.schemaPlan.table_name}`;
  const jobFilter = `job_id = ${sqlString(input.jobId)}`;
  const rowCount = Number(
    (
      await queryClickHouseText(
        `SELECT count() FROM ${table} WHERE ${jobFilter} FORMAT TabSeparated`,
      )
    ).trim(),
  );
  const eventNames = (
    await queryClickHouseText(
      `SELECT event_name FROM ${table} WHERE ${jobFilter} GROUP BY event_name ORDER BY event_name FORMAT TabSeparated`,
    )
  )
    .trim()
    .split("\n")
    .filter(Boolean);
  const eventIdMissing = Number(
    (
      await queryClickHouseText(
        `SELECT countIf(event_id = '') FROM ${table} WHERE ${jobFilter} FORMAT TabSeparated`,
      )
    ).trim(),
  );
  const timestampMinMax = (
    await queryClickHouseText(
      `SELECT min(timestamp), max(timestamp) FROM ${table} WHERE ${jobFilter} FORMAT TabSeparated`,
    )
  ).trim();

  const expectedEvents = Object.keys(input.eventProfile.event_counts).sort();
  const failures: string[] = [];

  if (rowCount !== input.eventProfile.row_count) {
    failures.push(
      `row_count_mismatch expected=${input.eventProfile.row_count} actual=${rowCount}`,
    );
  }

  const missingEvents = expectedEvents.filter(
    (eventName) => !eventNames.includes(eventName),
  );
  if (missingEvents.length > 0) {
    failures.push(`missing_events ${missingEvents.join(",")}`);
  }

  if (eventIdMissing > 0) {
    failures.push(`missing_event_id_count=${eventIdMissing}`);
  }

  if (
    input.manifest.success_event &&
    !eventNames.includes(input.manifest.success_event)
  ) {
    failures.push(`missing_success_event=${input.manifest.success_event}`);
  }

  return {
    passed: failures.length === 0,
    failures,
    expected_rows: input.eventProfile.row_count,
    actual_rows: rowCount,
    expected_events: expectedEvents,
    actual_events: eventNames,
    timestamp_min_max: timestampMinMax,
  };
}
