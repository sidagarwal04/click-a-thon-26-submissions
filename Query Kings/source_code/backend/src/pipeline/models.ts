/**
 * Budget-friendly Groq model routing.
 *
 * Env (your current setup):
 *   GROQ_MODEL=openai/gpt-oss-20b          # harder reasoning (SQL, complex plan fallback)
 *   GROQ_SCHEMA_MODEL=llama-3.1-8b-instant # schema design
 *   GROQ_CRITIC_MODEL=llama-3.1-8b-instant # critic / cheap JSON tasks
 *   GROQ_FAST_MODEL=...                   # optional override for cheap stages
 *
 * Strategy: use 8b for structured parse/plan/insight (cheap + numbers-first backup),
 * keep 20b for SQL generation where inventing bad SQL is costly to recover from.
 */

export type GroqModelRole =
  | "default"
  | "fast"
  | "schema"
  | "critic"
  | "sql"
  | "insight"
  | "intent"
  | "plan";

const DEFAULT_MAIN = "openai/gpt-oss-20b";
const DEFAULT_FAST = "llama-3.1-8b-instant";

export function getGroqModel(role: GroqModelRole = "default"): string {
  const main = process.env.GROQ_MODEL ?? DEFAULT_MAIN;
  const fast =
    process.env.GROQ_FAST_MODEL ??
    process.env.GROQ_CRITIC_MODEL ??
    DEFAULT_FAST;
  const schema = process.env.GROQ_SCHEMA_MODEL ?? fast;
  const critic = process.env.GROQ_CRITIC_MODEL ?? fast;

  switch (role) {
    case "fast":
    case "intent":
    case "plan":
    case "insight":
    case "critic":
      return fast;
    case "schema":
      return schema;
    case "sql":
    case "default":
    default:
      return main;
  }
}

export function describeModelRouting() {
  return {
    default: getGroqModel("default"),
    fast: getGroqModel("fast"),
    schema: getGroqModel("schema"),
    critic: getGroqModel("critic"),
    sql: getGroqModel("sql"),
    insight: getGroqModel("insight"),
    intent: getGroqModel("intent"),
    plan: getGroqModel("plan"),
  };
}
