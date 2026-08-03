import { executeClickHouse } from "../clickhouse.js";

export async function insertJsonRows(
  tableName: string,
  rows: Record<string, unknown>[],
) {
  if (rows.length === 0) {
    return;
  }
  await executeClickHouse(`INSERT INTO ${tableName} FORMAT JSONEachRow
${rows.map((row) => JSON.stringify(row)).join("\n")}
`);
}
