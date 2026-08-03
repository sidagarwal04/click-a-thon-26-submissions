import type { ClickHouseClient } from "@clickhouse/client";

import { getPool } from "./db.js";

/**
 * Discovers candidate raw measures and dimensions directly from ClickHouse
 * schema (`system.columns`), instead of a hand-maintained list — so a new
 * column landing in metrics_hourly, or a new dimension table getting joined
 * in, shows up as a candidate automatically, no code deploy needed to know
 * it exists.
 *
 * This is DISCOVERY, not registration: a discovered column is a candidate,
 * not yet a usable raw measure/dimension — an engineer still promotes a
 * discovered candidate into the real registry (metric_definitions'
 * raw-measure references / dimension_definitions), which is a deliberate,
 * cheap, human-in-the-loop step, not automatic. The reason: not everything
 * that fits the type heuristic below should become PM-facing (an internal
 * flag column, say) — discovery finds the candidates, a person still curates.
 *
 * The heuristic (validated against inmobi's actual schema):
 *   - numeric (UInt, Int, Float family) columns on metrics_hourly/segment_metrics_hourly,
 *     excluding the grouping keys (dow, hod) → candidate raw measures
 *   - LowCardinality(String) columns on ad_events or a joined dimension table
 *     → candidate dimensions (plain String columns are join keys / high-
 *     cardinality IDs, e.g. app_id — excluded by construction, not by name)
 *   - join keys are discovered too: any column name present in BOTH
 *     ad_events and another table is treated as the join key between them
 */

export interface DiscoveredMeasure {
  table: string;
  column: string;
  type: string;
}

export interface DiscoveredDimension {
  table: string;
  column: string;
  type: string;
  joinKey: string | null; // null = column lives directly on ad_events
}

interface ColumnRow {
  table: string;
  name: string;
  type: string;
}

async function getColumns(ch: ClickHouseClient, database: string): Promise<ColumnRow[]> {
  const rs = await ch.query({
    query: `SELECT table, name, type FROM system.columns WHERE database = {database:String} ORDER BY table, position`,
    query_params: { database },
    format: "JSONEachRow",
  });
  return rs.json<ColumnRow>();
}

const NUMERIC_TYPES = /^(U?Int\d+|Float\d+)$/;
const GROUPING_KEYS = new Set(["dow", "hod"]);

export async function discoverRawMeasures(
  ch: ClickHouseClient,
  database: string,
  table: string,
): Promise<DiscoveredMeasure[]> {
  const columns = await getColumns(ch, database);
  return columns
    .filter((c) => c.table === table && NUMERIC_TYPES.test(c.type) && !GROUPING_KEYS.has(c.name))
    .map((c) => ({ table: c.table, column: c.name, type: c.type }));
}

export async function discoverDimensions(
  ch: ClickHouseClient,
  database: string,
  eventTable: string,
  candidateJoinTables: string[],
): Promise<DiscoveredDimension[]> {
  const columns = await getColumns(ch, database);
  const eventCols = columns.filter((c) => c.table === eventTable);
  const eventColNames = new Set(eventCols.map((c) => c.name));

  const dims: DiscoveredDimension[] = [];

  // Dimensions living directly on the event table.
  for (const c of eventCols) {
    if (c.type === "LowCardinality(String)") {
      dims.push({ table: eventTable, column: c.name, type: c.type, joinKey: null });
    }
  }

  // Dimensions on a joined table — join key = any column name shared with
  // the event table (discovered, not assumed to be named "*_id").
  for (const table of candidateJoinTables) {
    const tableCols = columns.filter((c) => c.table === table);
    const joinKey = tableCols.find((c) => eventColNames.has(c.name))?.name ?? null;
    if (!joinKey) continue; // no discoverable relationship to the event table
    for (const c of tableCols) {
      if (c.type === "LowCardinality(String)") {
        dims.push({ table, column: c.name, type: c.type, joinKey });
      }
    }
  }

  return dims;
}

/** Upserts discovered candidates into Postgres's discovered_dimensions
 * cache — `promoted` is never touched here (only a human promotion action
 * sets it), so re-running discovery can't silently un-promote something. */
export async function syncDiscoveredDimensions(dims: DiscoveredDimension[]): Promise<void> {
  const pool = getPool();
  for (const d of dims) {
    await pool.query(
      `INSERT INTO discovered_dimensions (ch_table, ch_column, ch_type, join_key)
       VALUES ($1, $2, $3, $4)
       ON CONFLICT (ch_table, ch_column) DO UPDATE SET ch_type = EXCLUDED.ch_type, join_key = EXCLUDED.join_key`,
      [d.table, d.column, d.type, d.joinKey],
    );
  }
}
