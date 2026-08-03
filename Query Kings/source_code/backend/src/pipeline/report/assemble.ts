import {
  listJobsFromClickHouse,
  readJobArtifact,
  splitArtifactRelPath,
} from "../jobArtifacts.js";
import type {
  AskCard,
  FeatureCard,
  PipelineReport,
  ReportContradiction,
  ReportEvidence,
} from "./types.js";
import { langfuseTraceUrl } from "./langfuseUrl.js";

type JobKind = "ask" | "run";

type JobMeta = {
  job_id: string;
  /** Present when loaded from local filesystem. */
  dir?: string;
  mode: JobKind;
  mtimeMs: number;
  source: "clickhouse" | "filesystem";
};

const JUNK_ASK =
  /asdf|qwerty|ignore previous|drop table|invent a 90|numbers weird/i;

export async function assemblePipelineReport(input: {
  repoRoot: string;
  jobId?: string;
}): Promise<PipelineReport> {
  // Reports read from ClickHouse only (ops.job_artifacts).
  const jobs = await listJobsFromClickHouseMapped();

  if (jobs.length === 0) {
    throw new Error(
      `No pipeline artifacts in ClickHouse ops.job_artifacts. Run \`pnpm cli run\` / \`pnpm cli ask\` against this warehouse first.`,
    );
  }

  if (input.jobId) {
    const selected = resolveJob(jobs, input.jobId);
    if (!selected) {
      throw new Error(
        `Job not found: ${input.jobId}. Pass a full artifacts folder name or a unique prefix (e.g. 20260801T210941).`,
      );
    }
    if (selected.mode === "ask") {
      return assembleAskFocus({ jobs, job: selected });
    }
    return assembleRunFocus({ jobs, job: selected });
  }

  return assembleOverview(jobs);
}

function resolveJob(jobs: JobMeta[], query: string): JobMeta | null {
  const exact = jobs.find((job) => job.job_id === query);
  if (exact) return exact;

  const matches = jobs.filter(
    (job) => job.job_id.startsWith(query) || job.job_id.includes(query),
  );
  if (matches.length === 1) return matches[0];
  if (matches.length > 1) {
    const sample = matches
      .slice(0, 8)
      .map((job) => `  - ${job.job_id}`)
      .join("\n");
    throw new Error(
      `Ambiguous job prefix "${query}" matched ${matches.length} jobs:\n${sample}\nPass a longer prefix or the full folder name.`,
    );
  }
  return null;
}

async function assembleOverview(jobs: JobMeta[]): Promise<PipelineReport> {
  const runs = jobs.filter((j) => j.mode === "run").sort(byTimeAsc);
  const asks = jobs
    .filter((j) => j.mode === "ask")
    .sort(byTimeDesc)
    .filter((j) => !JUNK_ASK.test(j.job_id));

  const features: FeatureCard[] = [];
  for (const run of runs) {
    features.push(await loadFeatureCard(run));
  }

  // One card per feature_slug (latest run wins for details, but keep order of first appearance)
  const seen = new Set<string>();
  const uniqueFeatures: FeatureCard[] = [];
  for (const feature of features) {
    if (seen.has(feature.feature_slug)) continue;
    seen.add(feature.feature_slug);
    uniqueFeatures.push(feature);
  }

  const recentAsks: AskCard[] = [];
  for (const ask of asks.slice(0, 3)) {
    recentAsks.push(await loadAskCard(ask));
  }

  const latestRun = runs[runs.length - 1];
  const rawDiff = latestRun
    ? await readJobText(latestRun, "07_context_agent/context_diff.md")
    : null;
  const contextChangelog =
    buildFeatureListChangelog(uniqueFeatures) +
    (rawDiff
      ? `\n\n## Latest load notes\n\n${firstParagraphs(rawDiff, 10)}`
      : "");

  const contradictions = (await loadContradictionsFromLatest(runs)).slice(0, 4);

  return {
    generated_at: new Date().toISOString(),
    mode: "overview",
    job_id: null,
    title: "Pipeline report",
    subtitle:
      "What the agents produced: features instrumented into ClickHouse, how context grew, and recent PM answers — with Langfuse traces for proof.",
    features: uniqueFeatures,
    recent_asks: recentAsks,
    focus: null,
    contradictions,
    context_changelog: contextChangelog,
    stats: {
      instrumentation_runs: runs.length,
      ask_jobs: jobs.filter((j) => j.mode === "ask").length,
      features_instrumented: uniqueFeatures.length,
    },
    how_to: [
      "Features — what got instrumented into ClickHouse.",
      "Context — memory that grew after those loads.",
      "Insights — three recent PM answers (expand for evidence / schema).",
    ],
  };
}

async function assembleAskFocus(input: {
  jobs: JobMeta[];
  job: JobMeta;
}): Promise<PipelineReport> {
  const focus = await loadAskCard(input.job, { full: true });
  const relatedFeature =
    focus.feature_slug && focus.feature_slug !== "general"
      ? await findFeatureCard(input.jobs, focus.feature_slug)
      : null;

  return {
    generated_at: new Date().toISOString(),
    mode: "ask",
    job_id: input.job.job_id,
    title: "PM insight",
    subtitle: focus.question,
    features: relatedFeature ? [relatedFeature] : [],
    recent_asks: [focus],
    focus,
    contradictions: [],
    context_changelog: relatedFeature
      ? `Related feature: \`${relatedFeature.feature_slug}\` → \`${relatedFeature.table_name}\``
      : "No related instrumentation feature linked from this ask.",
    stats: {
      instrumentation_runs: input.jobs.filter((j) => j.mode === "run").length,
      ask_jobs: input.jobs.filter((j) => j.mode === "ask").length,
      features_instrumented: relatedFeature ? 1 : 0,
    },
    how_to: [
      "This page is one ask job only.",
      "Open Langfuse for intent → plan → SQL → critic.",
      "Full overview: `pnpm cli report`.",
    ],
  };
}

async function assembleRunFocus(input: {
  jobs: JobMeta[];
  job: JobMeta;
}): Promise<PipelineReport> {
  const focus = await loadFeatureCard(input.job);
  const contextChangelog =
    (await readJobText(input.job, "07_context_agent/context_diff.md")) ??
    `Instrumented \`${focus.feature_slug}\` → \`${focus.table_name}\``;

  const updated =
    (await readJobJson<{
      contradictions?: Array<{ id?: string; summary?: string }>;
    }>(input.job, "07_context_agent/updated_context.json")) ?? {};

  return {
    generated_at: new Date().toISOString(),
    mode: "run",
    job_id: input.job.job_id,
    title: "Instrumentation run",
    subtitle: `Spec → schema → Silver for ${focus.feature_slug}`,
    features: [focus],
    recent_asks: [],
    focus,
    contradictions: (updated.contradictions ?? [])
      .slice(0, 4)
      .map((c) => ({ id: c.id ?? "?", summary: c.summary ?? "" })),
    context_changelog: firstParagraphs(contextChangelog, 16),
    stats: {
      instrumentation_runs: 1,
      ask_jobs: input.jobs.filter((j) => j.mode === "ask").length,
      features_instrumented: 1,
    },
    how_to: [
      "This page is one instrumentation job only.",
      "Expand schema SQL if judges ask about ORDER BY / partition.",
      "Full overview: `pnpm cli report`.",
    ],
  };
}

async function findFeatureCard(
  jobs: JobMeta[],
  featureSlug: string,
): Promise<FeatureCard | null> {
  const runs = jobs.filter((j) => j.mode === "run").sort(byTimeDesc);
  for (const run of runs) {
    const card = await loadFeatureCard(run);
    if (
      card.feature_slug === featureSlug ||
      featureSlug.includes(card.feature_slug) ||
      card.feature_slug.includes(featureSlug)
    ) {
      return card;
    }
  }
  return null;
}

async function loadFeatureCard(job: JobMeta): Promise<FeatureCard> {
  const summary =
    (await readJobJson<Record<string, unknown>>(job, "run_summary.json")) ?? {};
  const plan =
    (await readJobJson<{
      engine?: string;
      order_by?: string[];
      partition_by?: string;
      table_name?: string;
    }>(job, "04_schema_generator/schema_plan.json")) ?? {};
  const sql = (await readJobText(job, "04_schema_generator/schema.sql")) ?? "";
  const contextDiff =
    (await readJobText(job, "07_context_agent/context_diff.md")) ?? "";
  const traceId = str(summary.langfuse_trace_id) ?? "";

  const featureSlug = str(summary.feature_slug) ?? job.job_id;
  return {
    job_id: job.job_id,
    feature_slug: featureSlug,
    table_name:
      str(summary.table_name) ??
      (plan.table_name
        ? `silver.${plan.table_name}`
        : `silver.${featureSlug}_events`),
    event_names: strArray(summary.event_names),
    success_event: str(summary.success_event) ?? "—",
    primary_entity: str(summary.primary_entity) ?? "—",
    row_count:
      typeof summary.silver_inserted_rows === "number"
        ? summary.silver_inserted_rows
        : typeof summary.row_count === "number"
          ? summary.row_count
          : null,
    langfuse_trace_id: traceId,
    langfuse_trace_url: langfuseTraceUrl(traceId),
    schema_preview: sql.trim() || "(schema.sql missing)",
    order_by: plan.order_by ?? [],
    partition_by: plan.partition_by ?? "",
    engine: plan.engine ?? "—",
    context_diff_excerpt: firstParagraphs(contextDiff, 8),
  };
}

async function loadAskCard(
  job: JobMeta,
  options?: { full?: boolean },
): Promise<AskCard> {
  const full = options?.full ?? false;
  const summary =
    (await readJobJson<Record<string, unknown>>(job, "ask_summary.json")) ?? {};
  const finalAnswer =
    (await readJobJson<Record<string, unknown>>(
      job,
      "11_evidence_critic/final_answer.json",
    )) ??
    (await readJobJson<Record<string, unknown>>(
      job,
      "10_insight_synthesizer/answer.json",
    )) ??
    {};
  const intent =
    (await readJobJson<{ feature_hints?: string[] }>(
      job,
      "08a_query_understanding/intent.json",
    )) ?? {};

  const traceId =
    str(summary.langfuse_trace_id) ?? str(finalAnswer.trace_id) ?? "";
  const allEvidence = asEvidence(finalAnswer.evidence);
  const humanEvidence = allEvidence.filter(
    (e) =>
      !/^primitive_/i.test(e.claim) &&
      !/^(metric_lookup_|trend_)\w*\s*\(/i.test(e.claim),
  );
  const evidenceLimit = full ? 8 : 3;
  const evidence =
    humanEvidence.length > 0
      ? humanEvidence.slice(0, evidenceLimit)
      : allEvidence.slice(0, evidenceLimit);

  const findings = strArray(finalAnswer.key_findings);
  const caveats = strArray(finalAnswer.caveats);
  const actions = strArray(finalAnswer.recommended_actions);

  return {
    job_id: job.job_id,
    question: str(summary.question) ?? job.job_id,
    short_answer:
      str(finalAnswer.short_answer) ??
      str(summary.answer) ??
      "No answer artifact found.",
    feature_slug: intent.feature_hints?.[0] ?? "general",
    key_findings: full ? findings.slice(0, 12) : findings.slice(0, 3),
    evidence,
    recommended_actions: full ? actions.slice(0, 6) : actions.slice(0, 2),
    caveats: full
      ? caveats
          .filter((c) => !/^Context known-issue note:/i.test(c))
          .slice(0, 5)
      : [],
    langfuse_trace_id: traceId,
    langfuse_trace_url: langfuseTraceUrl(traceId),
  };
}

async function loadContradictionsFromLatest(
  runs: JobMeta[],
): Promise<ReportContradiction[]> {
  for (let i = runs.length - 1; i >= 0; i -= 1) {
    const updated =
      (await readJobJson<{
        contradictions?: Array<{ id?: string; summary?: string }>;
      }>(runs[i], "07_context_agent/updated_context.json")) ?? {};
    if (updated.contradictions?.length) {
      return updated.contradictions.slice(0, 10).map((c) => ({
        id: c.id ?? "?",
        summary: c.summary ?? "",
      }));
    }
  }
  return [];
}

function buildFeatureListChangelog(features: FeatureCard[]): string {
  const lines = [
    "# Context changelog",
    "",
    "## Instrumented features (from artifacts)",
    "",
    ...features.map(
      (f) =>
        `- \`${f.feature_slug}\` → \`${f.table_name}\` (${f.event_names.join(" → ") || "events n/a"})`,
    ),
  ];
  return lines.join("\n");
}

async function listJobsFromClickHouseMapped(): Promise<JobMeta[]> {
  const chJobs = await listJobsFromClickHouse();
  return chJobs.map((job) => ({
    job_id: job.job_id,
    mode: job.mode,
    mtimeMs: job.mtimeMs,
    source: "clickhouse" as const,
  }));
}

function asEvidence(value: unknown): ReportEvidence[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (!item || typeof item !== "object") return null;
      const row = item as Record<string, unknown>;
      const claim = str(row.claim);
      if (!claim) return null;
      return {
        claim,
        query_id: str(row.query_id) ?? "?",
        confidence: str(row.confidence) ?? "medium",
      };
    })
    .filter((row): row is ReportEvidence => row !== null);
}

function str(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function strArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((v): v is string => typeof v === "string");
}

function firstParagraphs(markdown: string, maxLines: number): string {
  const lines = markdown
    .split(/\r?\n/)
    .filter((line) => line.trim().length > 0);
  return lines.slice(0, maxLines).join("\n");
}

function byTimeAsc(a: JobMeta, b: JobMeta) {
  return a.mtimeMs - b.mtimeMs;
}

function byTimeDesc(a: JobMeta, b: JobMeta) {
  return b.mtimeMs - a.mtimeMs;
}

async function readJobJson<T>(
  job: JobMeta,
  relativePath: string,
): Promise<T | null> {
  const text = await readJobText(job, relativePath);
  if (text == null) return null;
  try {
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
}

async function readJobText(
  job: JobMeta,
  relativePath: string,
): Promise<string | null> {
  const { stage, filename } = splitArtifactRelPath(relativePath);
  return readJobArtifact(job.job_id, stage, filename);
}
