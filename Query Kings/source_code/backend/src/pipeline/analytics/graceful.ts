import { FinalAnalyticsAnswer, InsightDraft } from "./types.js";

/**
 * Strict-mode philosophy:
 * - Never invent metrics/tables/answers when the LLM or warehouse path fails.
 * - Prefer a clear "unavailable" response over a wrong one.
 * - Real ClickHouse rows may still be summarized deterministically (numbers-first).
 */

export class AnalyticsStrictFailure extends Error {
  readonly reason: string;
  readonly stage: string;

  constructor(stage: string, reason: string) {
    super(`[${stage}] ${reason}`);
    this.name = "AnalyticsStrictFailure";
    this.stage = stage;
    this.reason = reason;
  }
}

export function isAnalyticsStrictFailure(
  error: unknown,
): error is AnalyticsStrictFailure {
  return error instanceof AnalyticsStrictFailure;
}

export function unavailableDraft(input: {
  question: string;
  stage?: string;
  reason?: string;
}): InsightDraft {
  const stageNote = input.stage ? ` (stage: ${input.stage})` : "";
  const detail = input.reason ? ` Details: ${input.reason}` : "";
  return {
    short_answer:
      "Analytics is temporarily unavailable for a reliable answer. Please try again in a moment.",
    key_findings: [
      "The analysis loop could not complete with trustworthy LLM output or grounded warehouse evidence.",
      "No invented metrics were returned — no reply is better than a wrong one.",
    ],
    evidence: [],
    recommended_actions: [
      "Retry the same question once.",
      "If it keeps failing, check Langfuse for the failing stage and confirm ClickHouse + GROQ_API_KEY are healthy.",
    ],
    caveats: [
      `Strict analytics mode refused to guess${stageNote}.${detail}`,
      `Original question: ${input.question}`,
    ],
  };
}

export function unavailableAnswer(input: {
  question: string;
  artifactRoot: string;
  traceId: string;
  stage?: string;
  reason?: string;
}): FinalAnalyticsAnswer {
  return {
    ...unavailableDraft(input),
    critic_notes: [
      "Returned graceful unavailable response instead of a fabricated answer.",
    ],
    artifact_root: input.artifactRoot,
    trace_id: input.traceId,
  };
}

export function isLlmInfrastructureError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error);
  return (
    /Groq request failed|json_validate_failed|empty completion|unusable|omitted SQL|GROQ_API_KEY|fetch failed|ECONNRESET|ETIMEDOUT|529|rate limit/i.test(
      message,
    ) || isAnalyticsStrictFailure(error)
  );
}
