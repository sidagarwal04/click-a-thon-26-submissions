import { readdir, readFile, stat } from "node:fs/promises";
import path from "node:path";
import { executeClickHouse, queryClickHouseText, sqlString } from "./clickhouse.js";

/** Root-level job files (run_summary.json, ask_summary.json) use this stage key. */
export const ARTIFACT_ROOT_STAGE = "_root";

let ensured = false;

export async function ensureJobArtifactsTable() {
  if (ensured) return;
  await executeClickHouse("CREATE DATABASE IF NOT EXISTS ops");
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
  ensured = true;
}

export function jobIdFromArtifactRoot(artifactRoot: string): string {
  return path.basename(artifactRoot);
}

export async function saveJobArtifact(input: {
  jobId: string;
  stage: string;
  filename: string;
  content: string;
}) {
  await ensureJobArtifactsTable();
  await executeClickHouse(`INSERT INTO ops.job_artifacts FORMAT JSONEachRow
${JSON.stringify({
  job_id: input.jobId,
  stage: input.stage || ARTIFACT_ROOT_STAGE,
  filename: input.filename,
  content: input.content,
})}
`);
}

export async function readJobArtifact(
  jobId: string,
  stage: string,
  filename: string,
): Promise<string | null> {
  await ensureJobArtifactsTable();
  const stageKey = stage || ARTIFACT_ROOT_STAGE;
  const sql = `
SELECT content
FROM ops.job_artifacts FINAL
WHERE job_id = ${sqlString(jobId)}
  AND stage = ${sqlString(stageKey)}
  AND filename = ${sqlString(filename)}
LIMIT 1
FORMAT JSONEachRow
`;
  try {
    const body = await queryClickHouseText(sql);
    const line = body.split("\n").find((row) => row.trim());
    if (!line) return null;
    const parsed = JSON.parse(line) as { content?: string };
    return typeof parsed.content === "string" ? parsed.content : null;
  } catch {
    return null;
  }
}

export type StoredJobMeta = {
  job_id: string;
  mode: "ask" | "run";
  mtimeMs: number;
};

export async function listJobsFromClickHouse(): Promise<StoredJobMeta[]> {
  await ensureJobArtifactsTable();
  const sql = `
SELECT
  job_id,
  max(updated_at) AS updated_at,
  countIf(stage = ${sqlString(ARTIFACT_ROOT_STAGE)} AND filename = 'ask_summary.json') AS has_ask,
  countIf(stage = ${sqlString(ARTIFACT_ROOT_STAGE)} AND filename = 'run_summary.json') AS has_run
FROM ops.job_artifacts FINAL
GROUP BY job_id
HAVING has_ask > 0 OR has_run > 0
FORMAT JSONEachRow
`;
  try {
    const body = await queryClickHouseText(sql);
    const jobs: StoredJobMeta[] = [];
    for (const line of body.split("\n")) {
      if (!line.trim()) continue;
      const row = JSON.parse(line) as {
        job_id: string;
        updated_at: string;
        has_ask: string | number;
        has_run: string | number;
      };
      const hasAsk = Number(row.has_ask) > 0;
      jobs.push({
        job_id: row.job_id,
        mode: hasAsk ? "ask" : "run",
        mtimeMs:
          Date.parse(String(row.updated_at).replace(" ", "T") + "Z") || 0,
      });
    }
    return jobs;
  } catch {
    return [];
  }
}

/** Push an on-disk artifacts/<job>/ tree into ops.job_artifacts (one-time / migrate). */
export async function pushArtifactsDirToClickHouse(artifactsRoot: string) {
  await ensureJobArtifactsTable();
  let jobIds: string[] = [];
  try {
    jobIds = await readdir(artifactsRoot);
  } catch {
    throw new Error(`No artifacts directory at ${artifactsRoot}`);
  }

  let files = 0;
  for (const jobId of jobIds) {
    const jobDir = path.join(artifactsRoot, jobId);
    let info;
    try {
      info = await stat(jobDir);
    } catch {
      continue;
    }
    if (!info.isDirectory() || jobId.startsWith(".")) continue;

    const stack = [jobDir];
    while (stack.length) {
      const dir = stack.pop()!;
      const entries = await readdir(dir, { withFileTypes: true });
      for (const entry of entries) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) {
          stack.push(full);
          continue;
        }
        if (!entry.isFile()) continue;
        const rel = path.relative(jobDir, full);
        const parts = rel.split(path.sep);
        const stage =
          parts.length === 1
            ? ARTIFACT_ROOT_STAGE
            : parts.slice(0, -1).join("/");
        const filename = parts[parts.length - 1];
        const content = await readFile(full, "utf8");
        await saveJobArtifact({ jobId, stage, filename, content });
        files += 1;
      }
    }
  }
  return { jobs: jobIds.length, files };
}

export function splitArtifactRelPath(relativePath: string): {
  stage: string;
  filename: string;
} {
  const normalized = relativePath.replace(/\\/g, "/");
  const parts = normalized.split("/");
  if (parts.length === 1) {
    return { stage: ARTIFACT_ROOT_STAGE, filename: parts[0] };
  }
  return {
    stage: parts.slice(0, -1).join("/"),
    filename: parts[parts.length - 1],
  };
}
