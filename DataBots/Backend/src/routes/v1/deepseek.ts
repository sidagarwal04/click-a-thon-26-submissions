import { FastifyInstance } from "fastify";
import { executeDeepSeekCompletion } from "../../services/deepseekService.js";

export default async function deepseekRoutes(fastify: FastifyInstance) {
  // DeepSeek status and credential check route
  fastify.get("/v1/deepseek/status", async () => {
    const hasDeepSeekKey = Boolean(process.env.DEEPSEEK_API_KEY);
    const hasLangfusePublic = Boolean(process.env.LANGFUSE_PUBLIC_KEY);
    const hasLangfuseSecret = Boolean(process.env.LANGFUSE_SECRET_KEY);
    const langfuseHost = process.env.LANGFUSE_HOST || process.env.LANGFUSE_BASE_URL || "https://cloud.langfuse.com";

    const missingCredentials: string[] = [];
    if (!hasDeepSeekKey) missingCredentials.push("DEEPSEEK_API_KEY");
    if (!hasLangfusePublic) missingCredentials.push("LANGFUSE_PUBLIC_KEY");
    if (!hasLangfuseSecret) missingCredentials.push("LANGFUSE_SECRET_KEY");

    return {
      status: missingCredentials.length === 0 ? "ready" : "missing_credentials",
      configured: {
        deepseekApiKeySet: hasDeepSeekKey,
        langfusePublicKeySet: hasLangfusePublic,
        langfuseSecretKeySet: hasLangfuseSecret,
        langfuseHost,
        defaultModel: process.env.DEEPSEEK_MODEL || "deepseek-chat",
        baseUrl: process.env.DEEPSEEK_BASE_URL || "https://api.deepseek.com",
      },
      missingCredentials,
      instruction:
        missingCredentials.length > 0
          ? `Please provide the following environment variables in your .env file: ${missingCredentials.join(", ")}`
          : "All DeepSeek & Langfuse credentials are configured properly.",
    };
  });

  // Fastify route to trigger DeepSeek completion and return prompt/token/latency/trace metrics
  fastify.post("/v1/deepseek/chat", async (request, reply) => {
    const body = (request.body || {}) as any;
    let { prompt, messages, model, temperature, max_tokens, userId, sessionId, tags, metadata } = body;

    // Support single prompt string or messages array
    if (!messages || !Array.isArray(messages)) {
      if (typeof prompt === "string" && prompt.trim().length > 0) {
        messages = [{ role: "user", content: prompt.trim() }];
      } else {
        reply.status(400);
        return {
          error: "Invalid request payload",
          details: "Either 'prompt' (string) or 'messages' (array of { role, content }) is required.",
        };
      }
    }

    try {
      const result = await executeDeepSeekCompletion({
        messages,
        model,
        temperature,
        max_tokens,
        userId: userId || (request.headers["x-user-id"] as string) || "user-anon",
        sessionId,
        tags,
        metadata: {
          ...metadata,
          userAgent: request.headers["user-agent"],
          clientIp: request.ip,
        },
      });

      return {
        success: true,
        data: result,
      };
    } catch (err: any) {
      request.log.error("DeepSeek API execution failed:", err);
      reply.status(500);
      return {
        success: false,
        error: "DeepSeek execution failed",
        message: err?.message || String(err),
      };
    }
  });
}
