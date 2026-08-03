import { NodeSDK } from "@opentelemetry/sdk-node";
import { LangfuseSpanProcessor } from "@langfuse/otel";
import { setActiveTraceAsPublic } from "@langfuse/tracing";

if (!process.env.LANGFUSE_BASE_URL && process.env.LANGFUSE_HOST) {
  process.env.LANGFUSE_BASE_URL = process.env.LANGFUSE_HOST;
}

export const langfuseSdk = new NodeSDK({
  // Export every Langfuse span (not only LLM scopes). Needed so
  // langfuse.trace.public on the root span actually reaches Cloud.
  spanProcessors: [
    new LangfuseSpanProcessor({
      shouldExportSpan: () => true,
    }),
  ],
});

export function assertLangfuseEnv() {
  const missing = [
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_BASE_URL",
  ].filter((key) => !process.env[key]);

  if (missing.length > 0) {
    throw new Error(
      `Missing Langfuse env vars: ${missing.join(", ")}. Copy backend/.env.example to backend/.env and add your project API keys.`,
    );
  }
}

export function startLangfuse() {
  assertLangfuseEnv();
  langfuseSdk.start();
}

export async function shutdownLangfuse() {
  try {
    await langfuseSdk.shutdown();
  } catch (error) {
    console.warn(
      `Langfuse shutdown/export failed; pipeline data was still written. Check LANGFUSE_* keys and host. ${error}`,
    );
  }
}

type PublicizableSpan = {
  setTraceAsPublic?: () => unknown;
};

/**
 * Mark the current Langfuse trace public so the URL works without login.
 * Prefer calling this at the START of the root observation (pass rootSpan).
 * Enabled when LANGFUSE_MAKE_TRACES_PUBLIC=1/true, or automatically when
 * LANGFUSE_BASE_URL points at Langfuse Cloud. Opt out with =0/false.
 */
export function publishActiveTraceIfEnabled(rootSpan?: PublicizableSpan) {
  if (!shouldPublishTraces()) return;
  try {
    if (typeof rootSpan?.setTraceAsPublic === "function") {
      rootSpan.setTraceAsPublic();
    } else {
      setActiveTraceAsPublic();
    }
    console.log(
      "Langfuse: marked active trace as public (shareable without login).",
    );
  } catch (error) {
    console.warn(`Could not mark Langfuse trace public: ${error}`);
  }
}

function shouldPublishTraces() {
  const flag = process.env.LANGFUSE_MAKE_TRACES_PUBLIC?.trim().toLowerCase();
  if (flag === "0" || flag === "false" || flag === "no" || flag === "off") {
    return false;
  }
  if (flag === "1" || flag === "true" || flag === "yes" || flag === "on") {
    return true;
  }
  const base = (
    process.env.LANGFUSE_BASE_URL ??
    process.env.LANGFUSE_HOST ??
    ""
  ).toLowerCase();
  return base.includes("cloud.langfuse.com");
}
