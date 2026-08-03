import path from "node:path";
import { startActiveObservation } from "@langfuse/tracing";
import { loadContextBundle } from "../context.js";
import { writeJobRootJson } from "../instrumentation/artifacts.js";
import { describeModelRouting } from "../models.js";
import { recordPipelineRun } from "../tracking.js";
import {
  publishActiveTraceIfEnabled,
  shutdownLangfuse,
  startLangfuse,
} from "../../tracing/langfuse.js";
import { runAnalysisPlanner } from "./analysisPlanner.js";
import { retrievePmContext } from "./contextRetriever.js";
import { runEvidenceCritic } from "./evidenceCritic.js";
import {
  isAnalyticsStrictFailure,
  isLlmInfrastructureError,
  unavailableAnswer,
} from "./graceful.js";
import { runInsightSynthesizer } from "./insightSynthesizer.js";
import { buildNumbersFirstDraft } from "./numbersFirst.js";
import { runPlanCritic } from "./planCritic.js";
import { runAnalyticsPrimitives } from "./primitives.js";
import { runQueryExecutor } from "./queryExecutor.js";
import { runQueryUnderstanding } from "./queryUnderstanding.js";
import { runResultEvaluator } from "./resultEvaluator.js";
import { runSqlGenerator } from "./sqlGenerator.js";
import { runSqlGuardrail } from "./sqlGuardrail.js";
import { EvidencePack, FinalAnalyticsAnswer } from "./types.js";

const MAX_ANALYTICS_ATTEMPTS = 2;

export async function runAnalyticsAsk(input: {
  question: string;
  repoRoot?: string;
}): Promise<FinalAnalyticsAnswer> {
  startLangfuse();

  const repoRoot = input.repoRoot ?? path.resolve(process.cwd(), "..");
  const jobId = createAskJobId(input.question);
  const featureSlug = "pm_query";
  const startedAt = new Date().toISOString();
  // Path-shaped id only — content is stored in ClickHouse ops.job_artifacts.
  const artifactRoot = path.join(repoRoot, "backend", "artifacts", jobId);

  let traceId = "";
  try {
    const answer = await startActiveObservation(
      "schema-kings.analytics_ask",
      async (rootSpan) => {
        traceId = rootSpan.traceId;
        // Mark public immediately so judges can open the link without login.
        publishActiveTraceIfEnabled(rootSpan);
        rootSpan.update({
          input: {
            question: input.question,
            artifact_root: artifactRoot,
          },
          metadata: {
            pipeline: "pm-question-to-clickhouse-insight",
            environment: process.env.NODE_ENV ?? "local",
            model_routing: describeModelRouting(),
            strict_mode: true,
          },
        });

        await recordPipelineRun({
          jobId,
          featureSlug,
          specFolder: "ask",
          status: "started",
          traceId,
          startedAt,
          summary: { question: input.question },
        });

        try {
          const context = await loadContextBundle(repoRoot);
          const intent = await runQueryUnderstanding({
            jobId,
            question: input.question,
            artifactRoot,
          });

          // Short-circuit uninterpretable prompts — no multi-stage warehouse blast.
          if (
            intent.ambiguity_notes.some((note) =>
              note.startsWith("UNINTERPRETABLE_QUESTION"),
            )
          ) {
            const draft = {
              short_answer:
                "I could not interpret that as a product analytics question. Please ask about a feature, funnel, segment, metric, or table.",
              key_findings: [
                "The prompt did not contain enough analytics intent to plan safe ClickHouse queries.",
              ],
              evidence: [],
              recommended_actions: [
                "Rephrase with a feature name (e.g. express checkout) or base funnel step.",
                "Ask for funnel drop-off, segment comparison, data quality, or available tables/metrics.",
              ],
              caveats: intent.ambiguity_notes,
            };
            const finalAnswer = await runEvidenceCritic({
              jobId,
              draft,
              evidencePack: {
                question: input.question,
                intent,
                context: {
                  features: [],
                  workflows: [],
                  columns: [],
                  metrics: [],
                  joins: [],
                  schema_quality: [],
                  contradictions: [],
                  base_context_excerpt: "",
                  retrieval_notes: intent.ambiguity_notes,
                },
                plan: {
                  interpreted_question: input.question,
                  answer_type: "schema_explanation",
                  tables: [],
                  joins: [],
                  queries: [],
                  evidence_standard: {
                    needs_comparison: false,
                    needs_segment_cut: false,
                    min_rows: 1,
                    can_answer_if_empty: true,
                  },
                  assumptions: [],
                  risks: [],
                },
                query_results: [],
                evaluation: {
                  passed: true,
                  needs_repair: false,
                  repair_notes: [],
                  evidence_gaps: [],
                },
              },
              artifactRoot,
              traceId,
            });
            await writeJobRootJson(artifactRoot, "ask_summary.json", {
              job_id: jobId,
              question: input.question,
              status: "uninterpretable",
              answer: finalAnswer.short_answer,
              artifact_root: artifactRoot,
              langfuse_trace_id: traceId,
            });
            await recordPipelineRun({
              jobId,
              featureSlug,
              specFolder: "ask",
              status: "completed",
              traceId,
              startedAt,
              completedAt: new Date().toISOString(),
              summary: {
                question: input.question,
                status: "uninterpretable",
              },
            });
            rootSpan.update({
              output: {
                status: "uninterpretable",
                answer: finalAnswer.short_answer,
              },
            });
            return finalAnswer;
          }

          const pmContext = await retrievePmContext({
            jobId,
            question: input.question,
            intent,
            context,
            artifactRoot,
          });

          let repairNotes: string[] = [];
          let evidencePack: EvidencePack | null = null;

          for (
            let attempt = 1;
            attempt <= MAX_ANALYTICS_ATTEMPTS;
            attempt += 1
          ) {
            const plan = await runAnalysisPlanner({
              jobId,
              question: input.question,
              intent,
              context: pmContext,
              artifactRoot,
              repairNotes,
            });
            const planReview = await runPlanCritic({
              jobId,
              plan,
              context: pmContext,
              artifactRoot,
            });
            if (!planReview.passed) {
              repairNotes = planReview.warnings;
              if (attempt < MAX_ANALYTICS_ATTEMPTS) {
                continue;
              }
            }

            // LLM SQL may be partial/empty under strict mode; primitives are the backbone.
            const sqlQueries = await runSqlGenerator({
              jobId,
              question: input.question,
              intent,
              context: pmContext,
              plan: planReview.plan,
              artifactRoot,
              executionFeedback: repairNotes,
            });
            const primitiveQueries = await runAnalyticsPrimitives({
              jobId,
              intent,
              context: pmContext,
              plan: planReview.plan,
              artifactRoot,
            });
            const merged = mergeQueries(sqlQueries, primitiveQueries);
            if (merged.length === 0) {
              throw new Error(
                "No grounded SQL queries available (LLM omitted SQL and no primitives matched).",
              );
            }

            const guardedQueries = await runSqlGuardrail({
              jobId,
              queries: merged,
              artifactRoot,
            });
            const executed = await runQueryExecutor({
              jobId,
              queries: guardedQueries,
              artifactRoot,
            });
            const evaluation = await runResultEvaluator({
              jobId,
              plan: planReview.plan,
              results: executed.results,
              executionErrors: executed.errors,
              artifactRoot,
            });

            evidencePack = {
              question: input.question,
              intent,
              context: pmContext,
              plan: planReview.plan,
              query_results: executed.results,
              evaluation,
            };

            // Retry only when we have zero usable rows and repair notes exist.
            const hasRows = executed.results.some(
              (result) => result.row_count > 0,
            );
            if (
              hasRows ||
              !evaluation.needs_repair ||
              attempt >= MAX_ANALYTICS_ATTEMPTS
            ) {
              break;
            }
            repairNotes = [
              ...evaluation.repair_notes,
              ...evaluation.evidence_gaps,
              ...guardedQueries.flatMap((query) =>
                query.guardrail.warnings.map(
                  (warning) => `${query.id}: ${warning}`,
                ),
              ),
            ];
          }

          if (!evidencePack) {
            return await finalizeUnavailable({
              jobId,
              featureSlug,
              question: input.question,
              artifactRoot,
              traceId,
              startedAt,
              rootSpan,
              stage: "analytics_loop",
              reason: "No evidence pack was produced.",
            });
          }

          const hasRows = evidencePack.query_results.some(
            (result) => result.row_count > 0,
          );

          // Strict: if no warehouse evidence, do not invent an answer.
          if (
            !hasRows &&
            !evidencePack.plan.evidence_standard.can_answer_if_empty
          ) {
            return await finalizeUnavailable({
              jobId,
              featureSlug,
              question: input.question,
              artifactRoot,
              traceId,
              startedAt,
              rootSpan,
              stage: "09_gold_query_executor",
              reason:
                evidencePack.evaluation.evidence_gaps.join("; ") ||
                "Queries returned no usable rows.",
            });
          }

          let draft;
          try {
            draft = await runInsightSynthesizer({
              jobId,
              evidencePack,
              artifactRoot,
            });
          } catch (error) {
            if (hasRows) {
              // Numbers-first from real rows is allowed; fabricated narrative is not.
              draft = buildNumbersFirstDraft(evidencePack);
              draft.caveats = [
                ...draft.caveats,
                `Insight LLM failed (${error instanceof Error ? error.message : String(error)}); used numbers-first warehouse summary only.`,
              ];
            } else {
              return await finalizeUnavailable({
                jobId,
                featureSlug,
                question: input.question,
                artifactRoot,
                traceId,
                startedAt,
                rootSpan,
                stage: "10_insight_synthesizer",
                reason: error instanceof Error ? error.message : String(error),
              });
            }
          }

          const finalAnswer = await runEvidenceCritic({
            jobId,
            draft,
            evidencePack,
            artifactRoot,
            traceId,
          });

          const runSummary = {
            job_id: jobId,
            question: input.question,
            answer: finalAnswer.short_answer,
            artifact_root: artifactRoot,
            langfuse_trace_id: traceId,
            evaluation_passed: evidencePack.evaluation.passed,
            evidence_queries: evidencePack.query_results.map((result) => ({
              query_id: result.query_id,
              row_count: result.row_count,
            })),
          };
          await writeJobRootJson(artifactRoot, "ask_summary.json", runSummary);
          await recordPipelineRun({
            jobId,
            featureSlug,
            specFolder: "ask",
            status: "completed",
            traceId,
            startedAt,
            completedAt: new Date().toISOString(),
            summary: runSummary,
          });

          rootSpan.update({ output: runSummary });
          return finalAnswer;
        } catch (error) {
          // Graceful unavailable for LLM/infra failures — never crash the CLI with a stack for judges.
          if (
            isLlmInfrastructureError(error) ||
            isAnalyticsStrictFailure(error)
          ) {
            return await finalizeUnavailable({
              jobId,
              featureSlug,
              question: input.question,
              artifactRoot,
              traceId,
              startedAt,
              rootSpan,
              stage: isAnalyticsStrictFailure(error)
                ? error.stage
                : "analytics_ask",
              reason: error instanceof Error ? error.message : String(error),
            });
          }
          throw error;
        }
      },
    );

    return answer;
  } catch (error) {
    // Last-resort graceful response so CLI still prints something usable.
    const fallback = unavailableAnswer({
      question: input.question,
      artifactRoot,
      traceId,
      stage: "orchestrator",
      reason: error instanceof Error ? error.message : String(error),
    });
    await writeJobRootJson(artifactRoot, "ask_summary.json", {
      job_id: jobId,
      question: input.question,
      status: "unavailable",
      error: error instanceof Error ? error.message : String(error),
      answer: fallback.short_answer,
      artifact_root: artifactRoot,
      langfuse_trace_id: traceId,
    });
    await recordPipelineRun({
      jobId,
      featureSlug,
      specFolder: "ask",
      status: "failed",
      traceId,
      startedAt,
      completedAt: new Date().toISOString(),
      summary: {
        question: input.question,
        error: error instanceof Error ? error.message : String(error),
        graceful: true,
      },
    });
    return fallback;
  } finally {
    await shutdownLangfuse();
  }
}

async function finalizeUnavailable(input: {
  jobId: string;
  featureSlug: string;
  question: string;
  artifactRoot: string;
  traceId: string;
  startedAt: string;
  rootSpan: { update: (value: Record<string, unknown>) => void };
  stage: string;
  reason: string;
}): Promise<FinalAnalyticsAnswer> {
  const answer = unavailableAnswer({
    question: input.question,
    artifactRoot: input.artifactRoot,
    traceId: input.traceId,
    stage: input.stage,
    reason: input.reason,
  });
  await writeJobRootJson(input.artifactRoot, "unavailable_answer.json", answer);
  await writeJobRootJson(input.artifactRoot, "ask_summary.json", {
    job_id: input.jobId,
    question: input.question,
    status: "unavailable",
    stage: input.stage,
    reason: input.reason,
    answer: answer.short_answer,
    artifact_root: input.artifactRoot,
    langfuse_trace_id: input.traceId,
  });
  await recordPipelineRun({
    jobId: input.jobId,
    featureSlug: input.featureSlug,
    specFolder: "ask",
    status: "failed",
    traceId: input.traceId,
    startedAt: input.startedAt,
    completedAt: new Date().toISOString(),
    summary: {
      question: input.question,
      status: "unavailable",
      stage: input.stage,
      reason: input.reason,
      graceful: true,
    },
  });
  input.rootSpan.update({
    output: {
      status: "unavailable",
      stage: input.stage,
      reason: input.reason,
    },
  });
  return answer;
}

function createAskJobId(question: string) {
  const timestamp = new Date()
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\..+/, "");
  const slug = question
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "")
    .slice(0, 48);
  return `${timestamp}_ask_${slug || "question"}`;
}

function mergeQueries<T extends { id: string }>(primary: T[], secondary: T[]) {
  const seen = new Set<string>();
  return [...primary, ...secondary].filter((query) => {
    if (seen.has(query.id)) {
      return false;
    }
    seen.add(query.id);
    return true;
  });
}
