import { OpenAI } from "openai";
import { Langfuse } from "langfuse";

function getDeepSeekKey() {
  return process.env.DEEPSEEK_API_KEY || "";
}

function getDeepSeekBaseUrl() {
  return process.env.DEEPSEEK_BASE_URL || "https://api.deepseek.com";
}

function getDeepSeekModel() {
  return process.env.DEEPSEEK_MODEL || "deepseek-chat";
}

function getLangfusePublicKey() {
  return process.env.LANGFUSE_PUBLIC_KEY || "";
}

function getLangfuseSecretKey() {
  return process.env.LANGFUSE_SECRET_KEY || "";
}

function getLangfuseHost() {
  return process.env.LANGFUSE_HOST || process.env.LANGFUSE_BASE_URL || "https://cloud.langfuse.com";
}

/**
 * Helper to obtain a DeepSeek OpenAI client instance
 */
export function getDeepSeekClient(): OpenAI {
  return new OpenAI({
    apiKey: getDeepSeekKey() || "placeholder-key",
    baseURL: getDeepSeekBaseUrl(),
  });
}

/**
 * Helper to obtain a Langfuse tracing instance
 */
export function getLangfuseClient(): Langfuse {
  const publicKey = getLangfusePublicKey();
  const secretKey = getLangfuseSecretKey();
  const baseUrl = getLangfuseHost();

  const client = new Langfuse({
    publicKey,
    secretKey,
    baseUrl,
    enabled: Boolean(publicKey && secretKey),
  });

  client.on("error", (err) => {
    console.error("[Langfuse SDK Error]:", err?.message || err);
  });

  return client;
}

export interface DeepSeekRequestOptions {
  messages: Array<{ role: "system" | "user" | "assistant"; content: string }>;
  model?: string;
  temperature?: number;
  max_tokens?: number;
  userId?: string;
  sessionId?: string;
  tags?: string[];
  metadata?: Record<string, any>;
}

export interface DeepSeekResponsePayload {
  response: string;
  model: string;
  usage: {
    promptTokens: number;
    completionTokens: number;
    totalTokens: number;
    reasoningTokens?: number;
  };
  latencyMs: number;
  langfuse: {
    traceId?: string;
    generationId?: string;
    traceUrl?: string;
    status: "traced" | "disabled_missing_credentials";
  };
  rawUsage: any;
}

/**
 * Executes a DeepSeek LLM completion request and traces prompts, completions,
 * token usage, latency, and metadata to Langfuse.
 */
export async function executeDeepSeekCompletion(
  options: DeepSeekRequestOptions
): Promise<DeepSeekResponsePayload> {
  const {
    messages,
    model = getDeepSeekModel(),
    temperature = 0.1,
    max_tokens = 450,
    userId = "anon-user",
    sessionId,
    tags = ["fastify", "deepseek"],
    metadata = {},
  } = options;

  const publicKey = getLangfusePublicKey();
  const secretKey = getLangfuseSecretKey();
  const host = getLangfuseHost();
  const isLangfuseConfigured = Boolean(publicKey && secretKey);

  const langfuse = getLangfuseClient();
  const deepseekClient = getDeepSeekClient();
  const startTime = Date.now();

  let trace: any = null;
  let generation: any = null;

  if (isLangfuseConfigured) {
    try {
      // Create Langfuse trace
      trace = langfuse.trace({
        name: "deepseek-fastify-chat",
        userId,
        sessionId,
        tags,
        input: messages,
        metadata: {
          ...metadata,
          model,
          framework: "Fastify",
          provider: "DeepSeek",
        },
      });

      // Create Langfuse generation span
      generation = trace.generation({
        name: "deepseek-generation",
        model,
        modelParameters: {
          temperature,
          max_tokens,
        },
        input: messages,
        startTime: new Date(startTime),
      });
    } catch (err) {
      console.warn("Failed to initialize Langfuse trace:", err);
    }
  }

  try {
    // Call DeepSeek API via OpenAI-compatible SDK
    const completion = await deepseekClient.chat.completions.create({
      model,
      messages,
      temperature,
      max_tokens,
    });

    const durationMs = Date.now() - startTime;
    const choice = completion.choices[0];
    const responseContent = choice?.message?.content || "";
    const usage = completion.usage || { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 };

    // Extract reasoning tokens if present (e.g. DeepSeek R1 / reasoner)
    const reasoningTokens = (usage as any)?.completion_tokens_details?.reasoning_tokens || 0;

    const tokenUsage = {
      promptTokens: usage.prompt_tokens,
      completionTokens: usage.completion_tokens,
      totalTokens: usage.total_tokens,
      ...(reasoningTokens ? { reasoningTokens } : {}),
    };

    // Finalize Langfuse tracing
    if (trace) {
      trace.update({
        output: responseContent,
      });
    }

    if (generation) {
      generation.end({
        output: responseContent,
        endTime: new Date(),
        usage: {
          promptTokens: usage.prompt_tokens,
          completionTokens: usage.completion_tokens,
          totalTokens: usage.total_tokens,
        },
        metadata: {
          finishReason: choice?.finish_reason,
          durationMs,
        },
      });
    }

    if (isLangfuseConfigured) {
      // Flush tracing events to Langfuse backend
      await langfuse.flushAsync().catch((err) => {
        console.warn("Langfuse flush error:", err);
      });
    }

    const hostBase = host.replace(/\/$/, "");
    const traceUrl = trace?.getTraceUrl ? trace.getTraceUrl() : (trace?.id ? `${hostBase}/trace/${trace.id}` : undefined);

    return {
      response: responseContent,
      model: completion.model || model,
      usage: tokenUsage,
      latencyMs: durationMs,
      langfuse: {
        traceId: trace?.id,
        generationId: generation?.id,
        traceUrl,
        status: isLangfuseConfigured ? "traced" : "disabled_missing_credentials",
      },
      rawUsage: usage,
    };
  } catch (error: any) {
    const durationMs = Date.now() - startTime;

    if (generation) {
      generation.end({
        statusMessage: error.message || String(error),
        level: "ERROR",
        endTime: new Date(),
      });
    }

    if (isLangfuseConfigured) {
      await langfuse.flushAsync().catch(() => {});
    }

    throw error;
  }
}
