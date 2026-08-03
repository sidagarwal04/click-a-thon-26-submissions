type ClickHouseConfig = {
  url: string;
  user: string;
  password: string;
  database: string;
};

export function getClickHouseConfig(): ClickHouseConfig {
  return {
    url: process.env.CLICKHOUSE_URL ?? "http://localhost:8123",
    user: process.env.CLICKHOUSE_USER ?? "schema_kings",
    password: process.env.CLICKHOUSE_PASSWORD ?? "schema_kings",
    database: process.env.CLICKHOUSE_DATABASE ?? "schema_kings",
  };
}

export async function executeClickHouse(sql: string) {
  await clickHouseRequest(sql);
}

export async function queryClickHouseText(sql: string) {
  return clickHouseRequest(sql);
}

export async function insertClickHouseFormat(input: {
  query: string;
  data: Buffer;
  contentType?: string;
}) {
  const config = getClickHouseConfig();
  const url = new URL(config.url);
  url.searchParams.set("query", input.query);
  const requestBody = new Uint8Array(input.data);

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `Basic ${Buffer.from(`${config.user}:${config.password}`).toString("base64")}`,
      "Content-Type": input.contentType ?? "application/octet-stream",
      "X-ClickHouse-Database": config.database,
    },
    body: requestBody,
  });

  const responseBody = await response.text();
  if (!response.ok) {
    throw new Error(
      `ClickHouse insert failed: ${response.status} ${responseBody}`,
    );
  }
  return responseBody;
}

async function clickHouseRequest(sql: string) {
  const config = getClickHouseConfig();
  const response = await fetch(config.url, {
    method: "POST",
    headers: {
      Authorization: `Basic ${Buffer.from(`${config.user}:${config.password}`).toString("base64")}`,
      "Content-Type": "text/plain; charset=utf-8",
      "X-ClickHouse-Database": config.database,
    },
    body: sql,
  });

  const body = await response.text();
  if (!response.ok) {
    throw new Error(`ClickHouse request failed: ${response.status} ${body}`);
  }
  return body;
}

export function sqlString(value: string) {
  return `'${value.replace(/\\/g, "\\\\").replace(/'/g, "\\'")}'`;
}
