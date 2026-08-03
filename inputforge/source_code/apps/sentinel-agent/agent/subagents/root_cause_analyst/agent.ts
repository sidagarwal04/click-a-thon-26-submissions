import { openai } from "@ai-sdk/openai";
import { defineAgent } from "eve";
import { z } from "zod";

export const anomalyAnalysisSchema = z.object({
  verdict: z.object({
    label: z.enum([
      "confirmed_anomaly",
      "likely_anomaly",
      "inconclusive",
      "false_positive",
    ]),
    summary: z.string(),
    confidence: z.number().min(0).max(1),
    severity: z.enum(["low", "medium", "high", "critical"]),
  }),
  sliceAndDice: z.array(
    z.object({
      slice: z.string(),
      finding: z.string(),
      evidence: z.string(),
    }),
  ),
});

export default defineAgent({
  description:
    "Investigate one detected InMobi anomaly with Sentinel's read-only ClickHouse tools and return a structured verdict and slice-and-dice analysis.",
  model: openai("gpt-5.6-terra"),
  outputSchema: anomalyAnalysisSchema,
});
