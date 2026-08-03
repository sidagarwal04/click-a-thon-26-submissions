import { startActiveObservation } from "@langfuse/tracing";
import { writeStageJson } from "../instrumentation/artifacts.js";
import { recordPipelineStage } from "../tracking.js";
import { analyticsTrackingEvents } from "./trackingEvents.js";
import { AnalysisPlan, QueryResult, ResultEvaluation } from "./types.js";

export async function runResultEvaluator(input: {
  jobId: string;
  plan: AnalysisPlan;
  results: QueryResult[];
  executionErrors: string[];
  artifactRoot: string;
}): Promise<ResultEvaluation> {
  const event = analyticsTrackingEvents.resultEvaluator;
  return startActiveObservation(event.stageId, async (span) => {
    const evidenceGaps: string[] = [];
    const repairNotes: string[] = [...input.executionErrors];
    const requiredQueries = new Set(
      input.plan.queries
        .filter((query) => query.priority === "required")
        .map((query) => query.id),
    );
    const successfulQueries = new Set(
      input.results.map((result) => result.query_id),
    );
    const nonEmptyResults = input.results.filter(
      (result) => result.row_count > 0,
    );

    for (const queryId of requiredQueries) {
      if (!successfulQueries.has(queryId)) {
        // Primitives may still cover the question — note but don't over-penalize.
        evidenceGaps.push(
          `Required planned query did not produce a result: ${queryId}`,
        );
      }
    }

    // min_rows means "at least N non-empty result sets", not sum of JSON rows.
    // Aggregate funnels correctly return 4–20 rows total.
    const minNonEmpty = Math.max(
      1,
      Number(input.plan.evidence_standard.min_rows) || 1,
    );
    if (
      nonEmptyResults.length < minNonEmpty &&
      !input.plan.evidence_standard.can_answer_if_empty
    ) {
      evidenceGaps.push(
        `Non-empty result sets (${nonEmptyResults.length}) below minimum (${minNonEmpty}).`,
      );
    }

    if (
      nonEmptyResults.length === 0 &&
      !input.plan.evidence_standard.can_answer_if_empty
    ) {
      repairNotes.push(
        "Queries returned no rows. Broaden filters, verify table/column names, or confirm the feature is instrumented.",
      );
    }

    if (
      input.plan.evidence_standard.needs_comparison &&
      nonEmptyResults.length < 2 &&
      input.results.length < 2
    ) {
      evidenceGaps.push(
        "Question needs comparison evidence but fewer than two result sets were produced.",
      );
      repairNotes.push(
        "Add a baseline, segment, or before/after comparison query.",
      );
    }

    // Pass when we have at least one non-empty result OR schema explanation allowed empty.
    const hasUsableEvidence =
      nonEmptyResults.length > 0 ||
      input.plan.evidence_standard.can_answer_if_empty;

    const evaluation: ResultEvaluation = {
      passed: hasUsableEvidence && input.executionErrors.length === 0,
      needs_repair:
        repairNotes.length > 0 ||
        (evidenceGaps.length > 0 && nonEmptyResults.length === 0),
      repair_notes: repairNotes,
      evidence_gaps: evidenceGaps,
    };

    await writeStageJson(
      input.artifactRoot,
      event.stageId,
      "result_evaluation.json",
      evaluation,
    );
    await recordPipelineStage({
      jobId: input.jobId,
      stageId: event.stageId,
      stageName: event.stageName,
      status: evaluation.passed ? "completed" : "failed",
      stageInput: {
        result_count: input.results.length,
        non_empty_results: nonEmptyResults.length,
        execution_errors: input.executionErrors,
      },
      stageOutput: evaluation,
    });
    span.update({ output: evaluation });
    return evaluation;
  });
}
