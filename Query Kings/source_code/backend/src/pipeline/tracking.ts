import { executeClickHouse } from "./clickhouse.js";

export async function ensureTrackingTables() {
  await executeClickHouse("CREATE DATABASE IF NOT EXISTS ops");
  await executeClickHouse(`
CREATE TABLE IF NOT EXISTS ops.pipeline_runs
(
    job_id String,
    feature_slug LowCardinality(String),
    spec_folder String,
    status LowCardinality(String),
    trace_id String,
    started_at DateTime64(3),
    completed_at Nullable(DateTime64(3)),
    summary_json String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (job_id)
`);

  await executeClickHouse(`
CREATE TABLE IF NOT EXISTS ops.pipeline_stages
(
    job_id String,
    stage_id LowCardinality(String),
    stage_name LowCardinality(String),
    status LowCardinality(String),
    input_json String,
    output_json String,
    error String,
    recorded_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY (job_id, stage_id, recorded_at)
`);

  await executeClickHouse(`
CREATE TABLE IF NOT EXISTS ops.data_loads
(
    load_id String,
    load_type LowCardinality(String),
    status LowCardinality(String),
    trace_id String,
    started_at DateTime64(3),
    completed_at Nullable(DateTime64(3)),
    summary_json String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (load_id)
`);

  await executeClickHouse(`
CREATE TABLE IF NOT EXISTS ops.data_load_tables
(
    load_id String,
    table_name String,
    source_path String,
    expected_rows Nullable(UInt64),
    actual_rows UInt64,
    status LowCardinality(String),
    validation_json String,
    loaded_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(loaded_at)
ORDER BY (load_id, table_name)
`);

  await executeClickHouse(`
CREATE TABLE IF NOT EXISTS ops.analytics_queries
(
    job_id String,
    query_id String,
    purpose String,
    priority LowCardinality(String),
    status LowCardinality(String),
    sql String,
    guardrail_warnings_json String,
    row_count Nullable(UInt64),
    duration_ms Nullable(UInt64),
    error String,
    recorded_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = MergeTree
ORDER BY (job_id, query_id, recorded_at)
`);

  await executeClickHouse(`
CREATE TABLE IF NOT EXISTS ops.job_artifacts
(
    job_id String,
    stage LowCardinality(String),
    filename String,
    content String,
    updated_at DateTime64(3) DEFAULT now64(3)
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY (job_id, stage, filename)
`);
}

export async function recordPipelineRun(input: {
  jobId: string;
  featureSlug: string;
  specFolder: string;
  status: "started" | "completed" | "failed";
  traceId?: string;
  startedAt: string;
  completedAt?: string | null;
  summary?: Record<string, unknown>;
}) {
  await ensureTrackingTables();
  await executeClickHouse(`INSERT INTO ops.pipeline_runs FORMAT JSONEachRow
${JSON.stringify({
  job_id: input.jobId,
  feature_slug: input.featureSlug,
  spec_folder: input.specFolder,
  status: input.status,
  trace_id: input.traceId ?? "",
  started_at: input.startedAt,
  completed_at: input.completedAt ?? null,
  summary_json: JSON.stringify(input.summary ?? {}),
})}
`);
}

export async function recordPipelineStage(input: {
  jobId: string;
  stageId: string;
  stageName: string;
  status: "started" | "completed" | "failed";
  stageInput?: Record<string, unknown>;
  stageOutput?: Record<string, unknown>;
  error?: string;
}) {
  await ensureTrackingTables();
  await executeClickHouse(`INSERT INTO ops.pipeline_stages FORMAT JSONEachRow
${JSON.stringify({
  job_id: input.jobId,
  stage_id: input.stageId,
  stage_name: input.stageName,
  status: input.status,
  input_json: JSON.stringify(input.stageInput ?? {}),
  output_json: JSON.stringify(input.stageOutput ?? {}),
  error: input.error ?? "",
})}
`);
}

export async function recordDataLoad(input: {
  loadId: string;
  loadType: string;
  status: "started" | "completed" | "failed";
  traceId?: string;
  startedAt: string;
  completedAt?: string | null;
  summary?: Record<string, unknown>;
}) {
  await ensureTrackingTables();
  await executeClickHouse(`INSERT INTO ops.data_loads FORMAT JSONEachRow
${JSON.stringify({
  load_id: input.loadId,
  load_type: input.loadType,
  status: input.status,
  trace_id: input.traceId ?? "",
  started_at: input.startedAt,
  completed_at: input.completedAt ?? null,
  summary_json: JSON.stringify(input.summary ?? {}),
})}
`);
}

export async function recordDataLoadTable(input: {
  loadId: string;
  tableName: string;
  sourcePath: string;
  expectedRows?: number | null;
  actualRows: number;
  status: "completed" | "failed";
  validation?: Record<string, unknown>;
}) {
  await ensureTrackingTables();
  await executeClickHouse(`INSERT INTO ops.data_load_tables FORMAT JSONEachRow
${JSON.stringify({
  load_id: input.loadId,
  table_name: input.tableName,
  source_path: input.sourcePath,
  expected_rows: input.expectedRows ?? null,
  actual_rows: input.actualRows,
  status: input.status,
  validation_json: JSON.stringify(input.validation ?? {}),
})}
`);
}

export async function recordAnalyticsQuery(input: {
  jobId: string;
  queryId: string;
  purpose: string;
  priority: "required" | "nice_to_have" | string;
  status: "blocked" | "completed" | "failed";
  sql: string;
  guardrailWarnings?: string[];
  rowCount?: number | null;
  durationMs?: number | null;
  error?: string;
}) {
  await ensureTrackingTables();
  await executeClickHouse(`INSERT INTO ops.analytics_queries FORMAT JSONEachRow
${JSON.stringify({
  job_id: input.jobId,
  query_id: input.queryId,
  purpose: input.purpose,
  priority: input.priority,
  status: input.status,
  sql: input.sql,
  guardrail_warnings_json: JSON.stringify(input.guardrailWarnings ?? []),
  row_count: input.rowCount ?? null,
  duration_ms: input.durationMs ?? null,
  error: input.error ?? "",
})}
`);
}
