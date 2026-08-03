import { createClient, type ClickHouseClient } from "@clickhouse/client";

let client: ClickHouseClient | undefined;

export function getClient(): ClickHouseClient {
  if (client) return client;
  const url = process.env.CLICKHOUSE_URL;
  const username = process.env.CLICKHOUSE_USER;
  const password = process.env.CLICKHOUSE_PASSWORD;
  if (!url || !username || !password) {
    throw new Error(
      "CLICKHOUSE_URL / CLICKHOUSE_USER / CLICKHOUSE_PASSWORD must be set",
    );
  }
  client = createClient({ url, username, password });
  return client;
}

/** Split a .sql file into individual statements. Strips `--` line comments,
 * splits on top-level ';'. Assumes no ';' inside string literals — true for
 * every file in sql/; if that changes, replace this with a real tokenizer. */
export function splitStatements(sql: string): string[] {
  const stripped = sql.replace(/--[^\n]*/g, "");
  return stripped
    .split(";")
    .map((s) => s.trim())
    .filter(Boolean);
}

export interface StatementResult {
  preview: string;
  summary: string | undefined;
}

export async function runSqlText(sql: string): Promise<StatementResult[]> {
  const ch = getClient();
  const statements = splitStatements(sql);
  const results: StatementResult[] = [];
  for (const stmt of statements) {
    const { summary } = await ch.command({ query: stmt });
    results.push({
      preview: stmt.slice(0, 80).replace(/\n/g, " "),
      summary: summary ? JSON.stringify(summary) : undefined,
    });
  }
  return results;
}

/** Run a query expected to return rows. */
export async function queryJson<T = Record<string, unknown>>(
  sql: string,
): Promise<T[]> {
  const ch = getClient();
  const resultSet = await ch.query({ query: sql, format: "JSONEachRow" });
  return resultSet.json<T>();
}
