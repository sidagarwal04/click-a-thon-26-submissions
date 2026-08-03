import { startActiveObservation } from "@langfuse/tracing";
import { getGroqModel, GroqModelRole } from "./models.js";

type GroqMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

type GroqChatCompletion = {
  usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
  };
  choices?: Array<{
    message?: {
      content?: string;
      reasoning?: string;
    };
  }>;
};

export async function callGroqJson<T>(input: {
  messages: GroqMessage[];
  model?: string;
  /** Budget routing role — ignored when `model` is set explicitly. */
  modelRole?: GroqModelRole;
  temperature?: number;
  maxTokens?: number;
  strictJson?: boolean;
  traceName?: string;
  traceInput?: Record<string, unknown>;
}): Promise<T> {
  const apiKey = process.env.GROQ_API_KEY;
  if (!apiKey) {
    throw new Error("GROQ_API_KEY is required for LLM-backed pipeline stages.");
  }

  const model = input.model ?? getGroqModel(input.modelRole ?? "default");
  const temperature = input.temperature ?? 0.1;
  const strictJson = input.strictJson ?? true;

  return startActiveObservation(
    input.traceName ?? "groq.json_completion",
    async (generation) => {
      generation.update({
        input:
          input.traceInput ??
          input.messages.map((message) => ({
            role: message.role,
            content_length: message.content.length,
          })),
        model,
        modelParameters: {
          temperature,
          ...(input.maxTokens ? { max_tokens: input.maxTokens } : {}),
          response_format: strictJson ? "json_object" : "text",
        },
        metadata: {
          provider: "groq",
        },
      });

      const response = await fetch(
        "https://api.groq.com/openai/v1/chat/completions",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${apiKey}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            model,
            messages: input.messages,
            temperature,
            ...(input.maxTokens ? { max_tokens: input.maxTokens } : {}),
            ...(strictJson ? { response_format: { type: "json_object" } } : {}),
          }),
        },
      );

      if (!response.ok) {
        const body = await response.text();
        generation.update({
          level: "ERROR",
          statusMessage: `Groq request failed: ${response.status}`,
          output: {
            status: response.status,
            body_preview: body.slice(0, 500),
          },
        });
        throw new Error(`Groq request failed: ${response.status} ${body}`);
      }

      const completion = (await response.json()) as GroqChatCompletion;
      const message = completion.choices?.[0]?.message;
      const content = message?.content || message?.reasoning;
      if (!content) {
        generation.update({
          output: { parsed: false, reason: "empty_completion" },
          level: "ERROR",
        });
        throw new Error("Groq returned an empty completion.");
      }

      generation.update({
        output: {
          parsed: true,
          content_length: content.length,
        },
        usageDetails: {
          input: completion.usage?.prompt_tokens ?? 0,
          output: completion.usage?.completion_tokens ?? 0,
          total: completion.usage?.total_tokens ?? 0,
        },
      });

      return parseJsonContent<T>(content);
    },
    { asType: "generation" },
  );
}

function parseJsonContent<T>(content: string): T {
  const cleaned = stripCodeFences(content).trim();
  try {
    return JSON.parse(cleaned) as T;
  } catch {
    const extracted = extractFirstJsonObject(cleaned);
    if (!extracted) {
      throw new Error("Groq returned content without a parseable JSON object.");
    }
    try {
      return JSON.parse(extracted) as T;
    } catch {
      // Last try: repair common trailing-comma / smart-quote noise lightly.
      const repaired = extracted
        .replace(/,\s*([}\]])/g, "$1")
        .replace(/[“”]/g, '"')
        .replace(/[‘’]/g, "'");
      return JSON.parse(repaired) as T;
    }
  }
}

function stripCodeFences(content: string) {
  return content
    .replace(/^```(?:json|JSON)?\s*/m, "")
    .replace(/```\s*$/m, "")
    .replace(/```(?:json|JSON)?\n([\s\S]*?)\n```/g, "$1");
}

function extractFirstJsonObject(content: string): string | null {
  const start = content.indexOf("{");
  if (start < 0) {
    return null;
  }

  let depth = 0;
  let inString = false;
  let escaping = false;
  for (let index = start; index < content.length; index += 1) {
    const char = content[index];

    if (escaping) {
      escaping = false;
      continue;
    }
    if (char === "\\") {
      escaping = true;
      continue;
    }
    if (char === '"') {
      inString = !inString;
      continue;
    }
    if (inString) {
      continue;
    }
    if (char === "{") {
      depth += 1;
    }
    if (char === "}") {
      depth -= 1;
      if (depth === 0) {
        return content.slice(start, index + 1);
      }
    }
  }

  return null;
}
