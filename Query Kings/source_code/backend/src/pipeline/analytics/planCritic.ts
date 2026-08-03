import { startActiveObservation } from "@langfuse/tracing";
import { writeStageJson } from "../instrumentation/artifacts.js";
import { recordPipelineStage } from "../tracking.js";
import {
  clampTablesToCatalog,
  isKnownAnalyticsTable,
  knownAnalyticsTables,
} from "./tableCatalog.js";
import { analyticsTrackingEvents } from "./trackingEvents.js";
import { AnalysisPlan, PmRelevantContext } from "./types.js";

export async function runPlanCritic(input: {
  jobId: string;
  plan: AnalysisPlan;
  context: PmRelevantContext;
  artifactRoot: string;
}): Promise<{ passed: boolean; warnings: string[]; plan: AnalysisPlan }> {
  const event = analyticsTrackingEvents.planCritic;
  return startActiveObservation(event.stageId, async (span) => {
    const warnings: string[] = [];
    const knownTables = knownAnalyticsTables(input.context);

    const clampedTables = clampTablesToCatalog(
      input.plan.tables,
      input.context,
    );
    const dropped = input.plan.tables.filter(
      (table) => !clampedTables.includes(table),
    );
    if (dropped.length > 0) {
      warnings.push(
        `Removed unknown/invented plan tables: ${dropped.join(", ")}`,
      );
    }

    const repairedPlan: AnalysisPlan = {
      ...input.plan,
      tables:
        clampedTables.length > 0
          ? clampedTables
          : input.plan.tables.filter((table) =>
              isKnownAnalyticsTable(table, knownTables),
            ),
      joins: input.plan.joins.filter(
        (join) =>
          isKnownAnalyticsTable(join.left_table, knownTables) &&
          isKnownAnalyticsTable(join.right_table, knownTables),
      ),
      queries: input.plan.queries.slice(0, 6),
      evidence_standard: {
        ...input.plan.evidence_standard,
        min_rows: 1,
      },
    };

    if (repairedPlan.queries.length === 0) {
      warnings.push("Plan does not contain any queries.");
    }
    if (repairedPlan.tables.length === 0) {
      warnings.push(
        "Plan has no known tables after catalog clamp; analytics should rely on primitives/base funnel only.",
      );
    }
    if (
      repairedPlan.evidence_standard.needs_comparison &&
      repairedPlan.queries.length < 2
    ) {
      warnings.push(
        "Question appears comparative/root-cause but plan has only one query.",
      );
    }

    const result = {
      // Warnings are OK — only block when there is nothing to run at all.
      passed: repairedPlan.queries.length > 0,
      warnings,
      plan: repairedPlan,
    };
    await writeStageJson(
      input.artifactRoot,
      event.stageId,
      "plan_review.json",
      result,
    );
    await recordPipelineStage({
      jobId: input.jobId,
      stageId: event.stageId,
      stageName: event.stageName,
      status: result.passed ? "completed" : "failed",
      stageInput: { plan: input.plan },
      stageOutput: result,
    });
    span.update({ output: result });
    return result;
  });
}
