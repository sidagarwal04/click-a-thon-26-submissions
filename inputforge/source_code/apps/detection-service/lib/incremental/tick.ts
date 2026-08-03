import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { queryJson, runSqlText } from "../clickhouse.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SQL_DIR = path.join(__dirname, "..", "..", "sql");

export interface StepResult {
  step: string;
  ok: boolean;
  skipped?: boolean;
  statements: number;
  elapsedMs: number;
  error?: string;
}

async function runFile(step: string, relPath: string): Promise<StepResult> {
  const t0 = Date.now();
  try {
    const sql = await readFile(path.join(SQL_DIR, relPath), "utf8");
    const statements = await runSqlText(sql);
    return {
      step,
      ok: true,
      statements: statements.length,
      elapsedMs: Date.now() - t0,
    };
  } catch (err) {
    return {
      step,
      ok: false,
      statements: 0,
      elapsedMs: Date.now() - t0,
      error: err instanceof Error ? err.message : String(err),
    };
  }
}

/** One-time setup: core schema, segment schema, config seed, the sql/mv/
 * chain (reactive on ad_events, refreshable everywhere cascaded), the
 * analyst view. Not part of any recurring job — run via `npm run
 * setup:local` or once before first deploy. Order matters:
 *   - schema + seed run first (MVs reference detection_config and write to
 *     tables that must already exist).
 *   - mv_noise_baseline_daily (sql/mv/06) before mv_zr_hourly (sql/mv/02):
 *     zr INNER JOINs metric_noise_baseline, so an empty baseline table
 *     means zero zr rows until the first refresh completes. On a brand-new
 *     environment, force that first refresh
 *     (`SYSTEM REFRESH VIEW inmobi.mv_noise_baseline_daily`) rather than
 *     waiting up to 24h for it to fire on its own schedule. Same applies to
 *     mv_zr_hourly itself (10-minute cadence) and mv_detect_global/
 *     mv_incidents, which DEPENDS ON their upstream view rather than racing
 *     it on an independent timer — see sql/mv/README.md.
 *   - segment_schema (segment/01) before mv_segment_metrics_hourly
 *     (sql/mv/07), before mv_segment_detect_global (sql/mv/08).
 *
 * Two execution models, deliberately: mv_metrics_hourly and
 * mv_segment_metrics_hourly are REACTIVE (fire on ad_events INSERTs) —
 * proven reliable even under a large bulk load, since they're a single hop
 * off the raw fact table. Everything cascaded from them (zr, detection,
 * incidents) is REFRESHABLE instead, because a *cascaded* MV (sourced from
 * another MV's target table, not ad_events directly) was found in
 * production to silently stop firing on a large bulk INSERT — the fix
 * isn't a smarter trigger, it's not depending on triggering at all. See
 * sql/mv/README.md for the full design.
 */
export async function runSetup(): Promise<StepResult[]> {
  return [
    await runFile("core_schema", "00_schema.sql"),
    await runFile("detection_config_seed", "01_detection_config_seed.sql"),
    await runFile("segment_schema", "segment/01_schema.sql"),
    await runFile(
      "mv_noise_baseline_daily",
      "mv/06_mv_noise_baseline_daily.sql",
    ),
    await runFile("mv_metrics_hourly", "mv/01_mv_metrics_hourly.sql"),
    await runFile("mv_zr_hourly", "mv/02_mv_zr_hourly.sql"),
    await runFile("mv_detect_global", "mv/03_mv_detect_global.sql"),
    await runFile(
      "mv_segment_metrics_hourly",
      "mv/07_mv_segment_metrics_hourly.sql",
    ),
    await runFile(
      "mv_segment_detect_global",
      "mv/08_mv_segment_detect_global.sql",
    ),
    await runFile(
      "mv_segment_zr_hourly",
      "mv/09_mv_segment_zr_hourly.sql",
    ),
    await runFile("mv_incidents", "mv/12_mv_incidents.sql"),
    await runFile(
      "mv_segment_incident_evidence",
      "mv/10_mv_segment_incident_evidence.sql",
    ),
    await runFile("analyst_view", "incremental/07_analyst_view.sql"),
  ];
}

export interface AnomalyRow {
  metric: string;
  method: string;
  time_window: string;
  observed: number | null;
  expected: number | null;
  delta: number | null;
  z: number;
  detected_at: string;
}

export async function fetchFreshAnomalies(
  since: Date,
  limit = 50,
): Promise<AnomalyRow[]> {
  const sinceStr = since.toISOString().slice(0, 19).replace("T", " ");
  return queryJson<AnomalyRow>(`
    SELECT metric, method, time_window, observed, expected, delta, z, detected_at
    FROM inmobi.anomalies
    WHERE detected_at >= '${sinceStr}'
    ORDER BY abs(z) DESC
    LIMIT ${limit}
  `);
}

export interface SegmentAnomalyRow extends AnomalyRow {
  dimension: string;
  segment: string;
}

export async function fetchFreshSegmentAnomalies(
  since: Date,
  limit = 50,
): Promise<SegmentAnomalyRow[]> {
  const sinceStr = since.toISOString().slice(0, 19).replace("T", " ");
  return queryJson<SegmentAnomalyRow>(`
    SELECT dimension, segment, metric, method, time_window, observed, expected, delta, z, detected_at
    FROM inmobi.segment_anomalies
    WHERE detected_at >= '${sinceStr}'
    ORDER BY abs(z) DESC
    LIMIT ${limit}
  `);
}
