#!/usr/bin/env node
// Run the pipeline and leave a trace behind.
//
// WHY THIS EXISTS AND scripts/ch DOES NOT REPLACE IT
// The unseen-day rule is "no pipeline evidence, no credit", and hand-computed
// answers score zero. `scripts/ch -f` runs the same SQL, but it leaves nothing
// behind except terminal output that could have been typed by anyone. This
// emits one trace per run, one span per stage and per statement, each carrying
// the rows it touched -- evidence produced BY the run, which is the only kind
// that proves the run happened.
//
// Usage:
//   scripts/run_pipeline.mjs                     # all stages
//   scripts/run_pipeline.mjs sql/30_gold.sql     # named files, in order
//   OTEL_SDK_DISABLED=true scripts/run_pipeline.mjs   # no telemetry, still runs
//
// Telemetry is fail-open: with the collector down this behaves exactly like
// scripts/ch, just noisier. It never gates the pipeline.

import { readFileSync } from "node:fs";
import { resolve, dirname, basename } from "node:path";
import { fileURLToPath } from "node:url";

// FIRST import, and it starts the SDK as a side effect -- see telemetry.js.
// A `startTelemetry()` call here would be hoisted below every other import.
process.env.OTEL_SERVICE_NAME ??= "trueccu-pipeline";
const { span, stopTelemetry, freshnessLag, telemetryEnabled } = await import(
  "../app/server/src/telemetry.js"
);

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const STAGES = [
  { file: "sql/00_bronze.sql", label: "bronze" },
  { file: "sql/10_language.sql", label: "language" },
  { file: "sql/20_silver.sql", label: "silver" },
  { file: "sql/30_gold.sql", label: "gold" },
];

// --- env + client ------------------------------------------------------------

function loadEnv() {
  const env = { ...process.env };
  try {
    for (const line of readFileSync(resolve(ROOT, ".env.local"), "utf8").split("\n")) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/);
      if (m) env[m[1]] ??= m[2];
    }
  } catch {
    /* fall through to process.env */
  }
  if (!env.CH_HOST) throw new Error("CH_HOST not set (expected .env.local at repo root)");
  return env;
}
const ENV = loadEnv();
const AUTH = "Basic " + Buffer.from(`${ENV.CH_USER}:${ENV.CH_PASS}`).toString("base64");

async function exec(sql) {
  const res = await fetch(`${ENV.CH_HOST}/?default_format=JSON`, {
    method: "POST",
    headers: { Authorization: AUTH, "Content-Type": "text/plain" },
    body: sql,
  });
  const body = await res.text();
  if (!res.ok) throw new Error(`ClickHouse ${res.status}: ${body.slice(0, 400)}`);
  const summary = JSON.parse(res.headers.get("x-clickhouse-summary") ?? "{}");
  let rows = [];
  try {
    rows = JSON.parse(body).data ?? [];
  } catch {
    /* DDL returns an empty body, which is not JSON. Not an error. */
  }
  return {
    rows,
    readRows: Number(summary.read_rows ?? 0),
    writtenRows: Number(summary.written_rows ?? 0),
    readBytes: Number(summary.read_bytes ?? 0),
  };
}

/**
 * Split a file into statements.
 *
 * `--` comments are stripped first: a `;` inside one would otherwise cut a
 * statement in half, and the resulting error points at a line that looks fine.
 * Mirrors what `scripts/ch -f` does, deliberately -- the two must not disagree
 * about what a statement is.
 */
function statements(sql) {
  const stripped = sql
    .split("\n")
    .map((l) => l.replace(/--.*$/, ""))
    .join("\n");
  return stripped
    .split(";")
    .map((s) => s.trim())
    .filter(Boolean);
}

const firstLine = (s) => s.split("\n")[0].slice(0, 90);

// --- run ---------------------------------------------------------------------

const files = process.argv.slice(2);
const stages = files.length
  ? files.map((f) => ({ file: f, label: basename(f, ".sql") }))
  : STAGES;

console.log(
  `pipeline: ${stages.length} stage(s)  ·  telemetry ${
    telemetryEnabled ? `-> ${process.env.OTEL_EXPORTER_OTLP_ENDPOINT ?? "http://localhost:4318"}` : "off"
  }`,
);

let failed = false;
// A check that reports FAIL is not an exception -- the SQL ran fine. It still
// has to make the process exit non-zero, or a broken pipeline passes CI.
const failedChecks = [];

await span("pipeline.run", { "pipeline.stages": stages.length }, async (runSpan) => {
  const runStarted = Date.now();

  for (const stage of stages) {
    const sql = readFileSync(resolve(ROOT, stage.file), "utf8");
    const stmts = statements(sql);

    await span(
      `pipeline.stage.${stage.label}`,
      { "pipeline.stage": stage.label, "pipeline.file": stage.file, "pipeline.statements": stmts.length },
      async (stageSpan) => {
        const t0 = Date.now();
        let written = 0;

        for (const [i, stmt] of stmts.entries()) {
          const head = firstLine(stmt);
          const r = await span(
            "pipeline.statement",
            { "pipeline.stage": stage.label, "pipeline.statement_index": i, "db.statement": head },
            async (s) => {
              const out = await exec(stmt);
              s.setAttributes({
                "clickhouse.read_rows": out.readRows,
                "clickhouse.written_rows": out.writtenRows,
                "clickhouse.read_bytes": out.readBytes,
              });
              return out;
            },
          );
          written += r.writtenRows;
          process.stdout.write(
            `  ${stage.label.padEnd(9)} ${String(i + 1).padStart(2)}/${stmts.length}  ${
              r.writtenRows ? `${r.writtenRows.toLocaleString()} rows  ` : ""
            }${head}\n`,
          );

          // A statement that RETURNS rows is a check, not a build step -- print
          // it. A verification stage whose verdicts only exist inside a span is
          // no better than not running it: the operator has to see PASS/FAIL at
          // the moment they run it, not go looking in a trace store.
          for (const row of r.rows) {
            const verdict = String(row.verdict ?? "");
            const mark = verdict.startsWith("PASS") ? "PASS" : verdict.startsWith("FAIL") ? "FAIL" : "    ";
            if (mark === "FAIL") failedChecks.push(row);
            const fields = Object.entries(row)
              .filter(([k]) => k !== "verdict")
              .map(([k, v]) => `${k}=${v}`)
              .join("  ");
            console.log(`       ${mark}  ${fields}${verdict ? `  :: ${verdict}` : ""}`);
          }
        }

        stageSpan.setAttributes({ "pipeline.rows_written": written, "pipeline.duration_ms": Date.now() - t0 });
        console.log(`  → ${stage.label}: ${written.toLocaleString()} rows written in ${Date.now() - t0}ms\n`);
      },
    );
  }

  // --- freshness, measured rather than claimed ------------------------------
  //
  // Event time -> queryable time. On a historical backfill the honest reading
  // is not "now minus the newest event" (that would be days, and would say
  // nothing about the pipeline) -- it is how long after the run STARTED the
  // newest event became queryable in gold. That is the number the NFR asks
  // for, and it is the one a replay or the unseen day will also produce.
  const { rows } = await exec(
    "SELECT max(minute) AS newest, count() AS rows FROM gold_ccu_minute",
  );
  const lagSeconds = (Date.now() - runStarted) / 1000;
  freshnessLag.record(lagSeconds, { stage: "gold" });
  runSpan.setAttributes({
    "pipeline.gold_rows": Number(rows[0]?.rows ?? 0),
    "pipeline.newest_minute": String(rows[0]?.newest ?? ""),
    "pipeline.freshness_lag_s": lagSeconds,
  });
  console.log(
    `gold: ${Number(rows[0]?.rows ?? 0).toLocaleString()} rows, newest ${rows[0]?.newest}` +
      `  ·  queryable ${lagSeconds.toFixed(1)}s after the run started`,
  );
  if (failedChecks.length) {
    runSpan.setAttributes({ "pipeline.failed_checks": failedChecks.length });
    runSpan.setStatus({ code: 2, message: `${failedChecks.length} check(s) failed` });
  }
}).catch((err) => {
  failed = true;
  console.error(`\nFAILED: ${err.message}`);
});

if (failedChecks.length) {
  console.error(`\n${failedChecks.length} check(s) FAILED — see above.`);
  failed = true;
}

// Short-lived process: without an explicit flush the spans for the run we just
// made evidence of are dropped on exit.
await stopTelemetry();
process.exit(failed ? 1 : 0);
