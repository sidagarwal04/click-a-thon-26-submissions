import path from "node:path";
import { jobIdFromArtifactRoot, saveJobArtifact } from "../jobArtifacts.js";

/**
 * Job artifacts are stored in ClickHouse `ops.job_artifacts` only.
 * `artifactRoot` is still a path-shaped id (…/artifacts/<job_id>) so existing
 * callers keep working; nothing is written to disk here.
 */
export async function writeStageJson(
  artifactRoot: string,
  stage: string,
  filename: string,
  value: unknown,
) {
  await writeStageText(
    artifactRoot,
    stage,
    filename,
    `${JSON.stringify(value, null, 2)}\n`,
  );
}

export async function writeStageText(
  artifactRoot: string,
  stage: string,
  filename: string,
  value: string,
) {
  await saveJobArtifact({
    jobId: jobIdFromArtifactRoot(artifactRoot),
    stage,
    filename,
    content: value,
  });
}

/** run_summary.json / ask_summary.json at the job root. */
export async function writeJobRootJson(
  artifactRoot: string,
  filename: string,
  value: unknown,
) {
  await writeJobRootText(
    artifactRoot,
    filename,
    `${JSON.stringify(value, null, 2)}\n`,
  );
}

export async function writeJobRootText(
  artifactRoot: string,
  filename: string,
  value: string,
) {
  await saveJobArtifact({
    jobId: jobIdFromArtifactRoot(artifactRoot),
    stage: "",
    filename,
    content: value,
  });
}

/** Kept for callers that still mkdir an artifact root path (no-op friendly). */
export function artifactJobDir(repoRoot: string, jobId: string) {
  return path.join(repoRoot, "backend", "artifacts", jobId);
}
