import path from "path";
import fs from "fs";
import { Document, SummaryIndex, VectorStoreIndex, SimpleDirectoryReader, Settings, DeepSeekLLM, HuggingFaceEmbedding } from "llamaindex";

let index: VectorStoreIndex | null = null;

export function getIndex(): VectorStoreIndex | null {
  return index;
}

export function isIndexInitialized(): boolean {
  return index !== null;
}

export async function initializeIndex(): Promise<boolean> {
  const apiKey = process.env.DEEPSEEK_API_KEY || process.env.OPENAI_API_KEY;
  if (!apiKey) {
    console.warn(
      "WARNING: DEEPSEEK_API_KEY environment variable is not set. LlamaIndex index creation skipped until key is provided.",
    );
    return false;
  }

  try {
    const model = (process.env.DEEPSEEK_MODEL as any) || "deepseek-chat";
    console.log(`Initializing LlamaIndex with DeepSeek model: ${model}`);

    // Configure DeepSeek LLM
    Settings.llm = new DeepSeekLLM({
      apiKey,
      model,
    });

    // Background asynchronous embedding load to keep server startup instant
    (async () => {
      try {
        Settings.embedModel = new HuggingFaceEmbedding();
        const dataDir = path.resolve(process.cwd(), "data");
        if (fs.existsSync(dataDir)) {
          const files = fs.readdirSync(dataDir);
          if (files.length > 0) {
            const reader = new SimpleDirectoryReader();
            const documents = await reader.loadData({ directoryPath: dataDir });
            index = await VectorStoreIndex.fromDocuments(documents);
            console.log("LlamaIndex vectorized document index initialized.");
          }
        }
      } catch (embedErr) {
        console.log("Note: VectorStoreIndex background initialization skipped; Settings.llm active for narration & chat.");
      }
    })();

    return true;
  } catch (error) {
    console.error("Error initializing LlamaIndex with DeepSeek API:", error);
    return false;
  }
}

export interface LlmNarrationResult {
  diagnosis: string;
  metrics: {
    model: string;
    provider: string;
    latencyMs: number;
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
  };
}

export async function generateRcaDiagnosisWithLlamaIndex(evidence: any): Promise<LlmNarrationResult> {
  if (!Settings.llm) {
    throw new Error("LlamaIndex LLM is not configured");
  }

  const topSegments = Array.isArray(evidence?.top_contributing_segments)
    ? evidence.top_contributing_segments.slice(0, 3)
    : [];
  const ruledOut = Array.isArray(evidence?.ruled_out)
    ? evidence.ruled_out.slice(0, 3)
    : [];

  const readableEvidence = [
    `Metric: ${evidence?.metric || "revenue"}`,
    `Window: ${evidence?.window_start || "unknown"} to ${evidence?.window_end || "unknown"}`,
    `Baseline value: ${evidence?.baseline_value ?? "unknown"}`,
    `Current value: ${evidence?.current_value ?? "unknown"}`,
    `Percent change: ${evidence?.pct_change ?? "unknown"}`,
    `Z-score: ${evidence?.z_score ?? "unknown"}`,
    `Primary driver factor: ${evidence?.factor_decomposition?.primary_driver_factor || evidence?.factor_decomposition?.primary_factor || "unknown"}`,
    `Top contributing segments: ${topSegments.length > 0
      ? topSegments.map((segment: any) => `${segment.dimension}=${segment.value} (share_of_delta=${segment.share_of_delta})`).join("; ")
      : "none listed"}`,
    `Ruled out checks: ${ruledOut.length > 0
      ? ruledOut.map((item: any) => typeof item === "string" ? item : JSON.stringify(item)).join("; ")
      : "none listed"}`,
  ].join("\n");

  const evidenceDocument = new Document({
    text: readableEvidence,
    metadata: {
      source: "rca_evidence_bundle",
      metric: String(evidence?.metric || "revenue"),
      window_start: String(evidence?.window_start || ""),
      window_end: String(evidence?.window_end || ""),
    },
  });

  const summaryIndex = await SummaryIndex.fromDocuments([evidenceDocument]);
  const queryEngine = summaryIndex.asQueryEngine();

  const llmModel = (process.env.DEEPSEEK_MODEL as string) || "deepseek-chat";
  const startMs = Date.now();

  const result = await queryEngine.query({
    query: [
      "You are the RCA narrator for an ad-tech anomaly investigation.",
      "Write 3-4 complete sentences that read like a clear human RCA diagnosis.",
      "Start with the main cause, then explain the supporting evidence, then mention what was ruled out.",
      "State the metric name, time window, baseline vs current value, percent change, primary driver factor, top contributing segment(s), and at least one ruled-out factor.",
      "Prefer concrete details over generic wording, but do not invent or infer any number not present in the evidence.",
      "Every number you mention must appear verbatim in the evidence document.",
      "If the evidence is insufficient, say so explicitly instead of guessing.",
      "Avoid fragments, table-like output, and vague filler like 'the system noted'.",
    ].join(" "),
  });

  const latencyMs = Date.now() - startMs;

  // Extract token usage from the raw LLM response if available
  const rawUsage = (result as any)?.sourceNodes?.[0]?.metadata?.usage ||
    (result as any)?.metadata?.usage ||
    (result as any)?.response?.raw?.usage ||
    {};

  return {
    diagnosis: result.response,
    metrics: {
      model: llmModel,
      provider: "DeepSeek",
      latencyMs,
      promptTokens: rawUsage?.prompt_tokens ?? 0,
      completionTokens: rawUsage?.completion_tokens ?? 0,
      totalTokens: rawUsage?.total_tokens ?? 0,
    },
  };
}
