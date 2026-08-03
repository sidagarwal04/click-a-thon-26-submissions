import { defineInstrumentation } from "eve/instrumentation";
import { registerTelemetry } from "ai";
import { LangfuseSpanProcessor } from "@langfuse/otel";
import { LangfuseVercelAiSdkIntegration } from "@langfuse/vercel-ai-sdk";
import { OTLPHttpProtoTraceExporter, registerOTel } from "@vercel/otel";
import { BatchSpanProcessor, type SpanProcessor } from "@opentelemetry/sdk-trace-base";

const presentationNames: Record<string, string> = {
  query_clickhouse_evidence: "ClickHouse Evidence Query",
  retrieve_anomaly_evidence: "Retrieve Anomaly Evidence",
};

/**
 * AI SDK and eve use compact machine-oriented span names by default. Rename
 * those observations before export so the Langfuse trace view tells the
 * investigation story in presentation-ready language.
 */
const presentationNameProcessor: SpanProcessor = {
  onStart(span, _parentContext) {
    const name = presentationNames[span.name]
      ?? (span.name.startsWith("chat ") ? "Sentinel Chat Orchestrator" : undefined)
      ?? (span.name.startsWith("invoke_agent ") ? "Delegate: Root-Cause Analyst" : undefined)
      ?? (/^step \d+$/.test(span.name) ? "Investigation Reasoning Step" : undefined);
    if (name) span.updateName(name);
  },
  onEnd() {},
  forceFlush: async () => {},
  shutdown: async () => {},
};

function langfuseProcessor(): SpanProcessor | undefined {
  const publicKey = process.env.LANGFUSE_PUBLIC_KEY;
  const secretKey = process.env.LANGFUSE_SECRET_KEY;
  if (!publicKey || !secretKey) return undefined;

  return new LangfuseSpanProcessor({
    publicKey,
    secretKey,
    baseUrl: process.env.LANGFUSE_BASE_URL ?? "https://cloud.langfuse.com",
    exportMode: "immediate",
  });
}

function clickstackProcessor(): SpanProcessor | undefined {
  const apiKey = process.env.HYPERDX_API_KEY;
  if (!apiKey) return undefined;

  const endpoint = process.env.HYPERDX_OTLP_ENDPOINT ?? "https://in-otel.hyperdx.io";

  return new BatchSpanProcessor(
    new OTLPHttpProtoTraceExporter({
      url: `${endpoint}/v1/traces`,
      headers: { authorization: apiKey },
    }),
  );
}

export default defineInstrumentation({
  setup: ({ agentName }) => {
    // This must be first: it renames spans before Langfuse and ClickStack
    // receive them.
    const spanProcessors = [presentationNameProcessor, langfuseProcessor(), clickstackProcessor()].filter(
      (processor): processor is SpanProcessor => processor !== undefined,
    );
    if (spanProcessors.length > 0) {
      registerOTel({ serviceName: agentName, spanProcessors });
    }

    // AI SDK 7 emits generation spans only after this integration is
    // registered. Langfuse uses those spans' model and token usage to compute
    // per-call cost for the direct OpenAI provider.
    if (process.env.LANGFUSE_PUBLIC_KEY && process.env.LANGFUSE_SECRET_KEY) {
      registerTelemetry(new LangfuseVercelAiSdkIntegration());
    }
  },
  // Shown as the AI SDK function / agent identity in Langfuse instead of the
  // package slug. Tool and subagent observation names remain their explicit
  // filesystem-derived IDs (for example, query_clickhouse_evidence).
  functionId: "Sentinel Root-Cause Analyst",
  traceChannelRequests: true,
});
