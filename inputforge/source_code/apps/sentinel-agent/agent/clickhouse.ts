import { createClient } from "@clickhouse/client";

const client = createClient({
  url: process.env.CLICKHOUSE_URL,
  username: process.env.CLICKHOUSE_USER ?? "default",
  password: process.env.CLICKHOUSE_PASSWORD,
  database: process.env.CLICKHOUSE_DATABASE ?? "default",
  request_timeout: 30_000,
});

const FORBIDDEN_KEYWORDS =
  /\b(insert|update|delete|alter|drop|truncate|create|rename|grant|revoke|attach|detach|optimize|kill|system)\b/i;
const MAX_ROWS = 500;

export class UnsafeQueryError extends Error {}

export interface QueryResult {
  rows: Record<string, unknown>[];
  rowCount: number;
}

export function validateReadOnlySql(sql: string): string {
  const trimmed = sql.trim().replace(/;\s*$/, "");
  if (!/^select\b/i.test(trimmed) && !/^with\b/i.test(trimmed)) {
    throw new UnsafeQueryError("Only SELECT/WITH queries are allowed.");
  }
  if (!trimmed || /;|--|\/\*/.test(trimmed)) {
    throw new UnsafeQueryError("Only one uncommented SELECT/WITH statement is allowed.");
  }
  if (FORBIDDEN_KEYWORDS.test(trimmed)) {
    throw new UnsafeQueryError("Query contains a keyword that is not allowed for read-only investigation.");
  }
  if (!/\blimit\s+\d+/i.test(trimmed)) {
    throw new UnsafeQueryError("Every query must include a numeric LIMIT.");
  }

  return trimmed;
}

export async function queryReadOnly(sql: string): Promise<QueryResult> {
  const trimmed = validateReadOnlySql(sql);

  const resultSet = await client.query({
    query: trimmed,
    format: "JSONEachRow",
    clickhouse_settings: {
      readonly: "1",
      max_execution_time: 30,
      max_result_rows: String(MAX_ROWS),
      result_overflow_mode: "break",
    },
  });
  const rows = await resultSet.json<Record<string, unknown>>();
  return { rows: rows.slice(0, MAX_ROWS), rowCount: rows.length };
}
