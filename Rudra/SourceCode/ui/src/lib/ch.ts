export type Row = Record<string, any>;

// Run a read-only query through the proxy; returns ClickHouse JSON `data` rows.
// `tag` refines the query_log log_comment (e.g. "curve" -> "sonyliv-dashboard:curve").
export async function chQuery(sql: string, tag?: string): Promise<Row[]> {
  const r = await fetch("/api/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql, tag }),
  });
  const j = await r.json();
  if (j.error) throw new Error(j.error);
  return (j.data ?? []) as Row[];
}

// Single scalar (first column of first row).
export async function chScalar(sql: string, tag?: string): Promise<any> {
  const rows = await chQuery(sql, tag);
  if (!rows.length) return null;
  return rows[0][Object.keys(rows[0])[0]];
}
