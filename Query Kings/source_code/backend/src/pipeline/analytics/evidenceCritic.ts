import { startActiveObservation } from "@langfuse/tracing";
import {
  writeStageJson,
  writeStageText,
} from "../instrumentation/artifacts.js";
import { recordPipelineStage } from "../tracking.js";
import { analyticsTrackingEvents } from "./trackingEvents.js";
import {
  EvidencePack,
  FinalAnalyticsAnswer,
  InsightDraft,
  QueryResult,
} from "./types.js";
import { renderDraftMarkdown } from "./insightSynthesizer.js";

export async function runEvidenceCritic(input: {
  jobId: string;
  draft: InsightDraft;
  evidencePack: EvidencePack;
  artifactRoot: string;
  traceId: string;
}): Promise<FinalAnalyticsAnswer> {
  const event = analyticsTrackingEvents.evidenceCritic;
  return startActiveObservation(event.stageId, async (span) => {
    const queryIds = new Set(
      input.evidencePack.query_results.map((result) => result.query_id),
    );
    const criticNotes: string[] = [];
    const evidence = input.draft.evidence.filter((claim) => {
      if (!queryIds.has(claim.query_id) && claim.query_id !== "context") {
        criticNotes.push(
          `Removed unsupported claim with unknown query id: ${claim.claim}`,
        );
        return false;
      }
      if (/raw rows \(not used as metric evidence\)/i.test(claim.claim)) {
        criticNotes.push(`Removed raw-dump claim: ${claim.claim}`);
        return false;
      }
      return true;
    });

    const caveats = [...input.draft.caveats];
    if (!input.evidencePack.evaluation.passed) {
      caveats.push(
        "Evidence quality checks found gaps; treat this answer as directional until follow-up queries pass.",
      );
      criticNotes.push(...input.evidencePack.evaluation.evidence_gaps);
    }

    // Soft-clean findings that still claim fake on-time rates from missing ETA fields.
    let shortAnswer = input.draft.short_answer;
    let keyFindings = [...input.draft.key_findings];
    if (
      /visa_issuance_eta_days|on-?time delivery/i.test(
        input.evidencePack.question,
      ) &&
      input.evidencePack.context.contradictions.some((item) =>
        /eta|visa_issuance/i.test(`${item.id} ${item.summary}`),
      )
    ) {
      const inventedRate =
        /\d+(\.\d+)?\s*%|0\.0+\d+|on-time delivery rate using visa_issuance/i.test(
          `${shortAnswer} ${keyFindings.join(" ")}`,
        );
      if (inventedRate || !/not computable/i.test(shortAnswer)) {
        shortAnswer =
          "On-time delivery using visa_issuance_eta_days is not computable from the current warehouse fields.";
        keyFindings = [
          "visa_issuance_eta_days is not a reliable post-issuance outcome field in this dataset.",
          ...input.evidencePack.context.contradictions
            .filter((item) =>
              /eta|visa_issuance/i.test(`${item.id} ${item.summary}`),
            )
            .map((item) => item.summary),
          "Pre-purchase tables stop at purchase_completed; issuance timing is out of scope here.",
        ];
        criticNotes.push(
          "Rewrote ETA on-time claim because context marks the field as missing/mismatched.",
        );
        caveats.push(
          "Do not treat any numeric on-time rate as measured delivery performance when the field is absent or contradicted.",
        );
      }
    }

    if (evidence.length === 0 && input.evidencePack.query_results.length > 0) {
      criticNotes.push(
        "No explicit evidence claims survived; added query-result caveat.",
      );
      caveats.push(summarizeQueryResults(input.evidencePack.query_results));
    }

    const finalAnswer: FinalAnalyticsAnswer = {
      ...input.draft,
      short_answer: shortAnswer,
      key_findings: keyFindings,
      evidence,
      caveats,
      critic_notes: criticNotes,
      artifact_root: input.artifactRoot,
      trace_id: input.traceId,
    };

    await writeStageJson(
      input.artifactRoot,
      event.stageId,
      "final_answer.json",
      finalAnswer,
    );
    await writeStageText(
      input.artifactRoot,
      event.stageId,
      "final_answer.md",
      renderDraftMarkdown(finalAnswer),
    );
    await recordPipelineStage({
      jobId: input.jobId,
      stageId: event.stageId,
      stageName: event.stageName,
      status: "completed",
      stageInput: { draft: input.draft },
      stageOutput: finalAnswer,
    });
    span.update({ output: finalAnswer });
    return finalAnswer;
  });
}

function summarizeQueryResults(results: QueryResult[]) {
  return results
    .map((result) => `${result.query_id}: ${result.row_count} rows`)
    .join("; ");
}
