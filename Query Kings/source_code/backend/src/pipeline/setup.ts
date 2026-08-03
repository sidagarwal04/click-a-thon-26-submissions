import { spawn } from "node:child_process";
import path from "node:path";
import { startActiveObservation } from "@langfuse/tracing";
import { getClickHouseConfig, queryClickHouseText } from "./clickhouse.js";
import { bootstrapContext } from "./context.js";
import { ensurePipelineLayers } from "./layers.js";
import { recordDataLoad, recordDataLoadTable } from "./tracking.js";
import { shutdownLangfuse, startLangfuse } from "../tracing/langfuse.js";

const baseTables = [
  {
    table: "destination_card_clicked",
    file: "destination_card_clicked.parquet",
  },
  { table: "application_started", file: "application_started.parquet" },
  { table: "document_uploaded", file: "document_uploaded.parquet" },
  { table: "purchase_completed", file: "purchase_completed.parquet" },
  { table: "search_typed", file: "search_typed.parquet" },
  { table: "landing_page_scrolled", file: "landing_page_scrolled.parquet" },
  { table: "auth_completed", file: "auth_completed.parquet" },
  { table: "pay_now_clicked", file: "pay_now_clicked.parquet" },
] as const;

export async function runSetup(input: { repoRoot: string }) {
  startLangfuse();

  const loadId = `base_${new Date()
    .toISOString()
    .replace(/[-:]/g, "")
    .replace(/\..+/, "")}`;
  const startedAt = new Date().toISOString();
  let traceId = "";

  try {
    await startActiveObservation(
      "schema-kings.local-setup",
      async (rootSpan) => {
        traceId = rootSpan.traceId;
        rootSpan.update({
          input: {
            load_id: loadId,
            clickhouse_url: getClickHouseConfig().url,
            clickhouse_database: getClickHouseConfig().database,
          },
          metadata: {
            pipeline: "local-setup",
            includes: ["base_data_load", "context_bootstrap"],
          },
        });

        await recordDataLoad({
          loadId,
          loadType: "base_tables_and_context",
          status: "started",
          traceId,
          startedAt,
        });

        const skipBaseLoad = isTruthyEnv(process.env.SETUP_SKIP_BASE_LOAD);

        const loadSummary = await startActiveObservation(
          "setup.load_base_tables",
          async (span) => {
            span.update({
              input: {
                tables: baseTables.map((table) => table.table),
                loader: skipBaseLoad
                  ? "skipped (SETUP_SKIP_BASE_LOAD)"
                  : "data/load.sh",
                skip_base_load: skipBaseLoad,
              },
              metadata: {
                target_database: getClickHouseConfig().database,
              },
            });

            const loadScriptResult = skipBaseLoad
              ? {
                  stdout:
                    "Skipped data/load.sh because SETUP_SKIP_BASE_LOAD is set. Validating existing tables only.",
                  stderr: "",
                }
              : await runLoadScript(input.repoRoot);

            if (skipBaseLoad) {
              console.log(
                "SETUP_SKIP_BASE_LOAD=1 — skipping data/load.sh (expect base tables already loaded).",
              );
            }

            const results = [];
            for (const table of baseTables) {
              const sourcePath = path.join(input.repoRoot, "data", table.file);
              const actualRows = Number(
                (
                  await queryClickHouseText(
                    `SELECT count() FROM ${table.table} FORMAT TabSeparated`,
                  )
                ).trim(),
              );

              if (!Number.isFinite(actualRows) || actualRows <= 0) {
                throw new Error(
                  `Base table ${table.table} is missing or empty (${actualRows} rows). ` +
                    (skipBaseLoad
                      ? "Base tables missing/empty while SETUP_SKIP_BASE_LOAD=1. Load data first, then retry setup."
                      : "data/load.sh did not leave a usable table."),
                );
              }

              const result = {
                table_name: table.table,
                source_path: sourcePath,
                actual_rows: actualRows,
                status: "completed" as const,
              };
              results.push(result);
              await recordDataLoadTable({
                loadId,
                tableName: table.table,
                sourcePath,
                actualRows,
                status: "completed",
                validation: {
                  row_count_positive: actualRows > 0,
                  load_skipped: skipBaseLoad,
                },
              });
            }

            span.update({
              output: {
                loader_stdout: loadScriptResult.stdout.slice(-2000),
                loaded_tables: results.length,
                total_rows: results.reduce(
                  (sum, result) => sum + result.actual_rows,
                  0,
                ),
                results,
                skip_base_load: skipBaseLoad,
              },
            });

            return {
              loaded_tables: results.length,
              total_rows: results.reduce(
                (sum, result) => sum + result.actual_rows,
                0,
              ),
              tables: results,
              skip_base_load: skipBaseLoad,
            };
          },
        );

        await startActiveObservation("setup.pipeline_layers", async (span) => {
          span.update({
            input: {
              source: "infra/clickhouse/init/01_layers.sql",
            },
          });
          await ensurePipelineLayers(input.repoRoot);
          span.update({
            output: {
              databases: ["bronze", "silver", "gold"],
              status: "ensured",
            },
          });
          console.log(
            "Pipeline layers ensured: bronze / silver / gold (+ bronze tables).",
          );
        });

        const contextSummary = await startActiveObservation(
          "setup.context_bootstrap",
          async (span) => {
            span.update({
              input: {
                documents: [
                  "base_context.md",
                  "data/ddl.sql",
                  "data/instrumentation_notes.md",
                ],
              },
            });

            const registry = await bootstrapContext(input.repoRoot);
            span.update({
              output: {
                features: registry.features.length,
                contradictions: registry.contradictions.length,
              },
            });
            return {
              features: registry.features.length,
              contradictions: registry.contradictions.length,
            };
          },
        );

        const summary = {
          load_id: loadId,
          base_data: loadSummary,
          context: contextSummary,
          trace_id: traceId,
        };

        await recordDataLoad({
          loadId,
          loadType: "base_tables_and_context",
          status: "completed",
          traceId,
          startedAt,
          completedAt: new Date().toISOString(),
          summary,
        });

        rootSpan.update({
          output: summary,
        });

        console.log("Local setup completed.");
        console.log(`Load ID: ${loadId}`);
        console.log(`Base tables loaded: ${loadSummary.loaded_tables}`);
        console.log(`Base rows loaded: ${loadSummary.total_rows}`);
        console.log(
          `Open context contradictions: ${contextSummary.contradictions}`,
        );
        console.log(`Langfuse trace ID: ${traceId}`);
      },
    );
  } catch (error) {
    await recordDataLoad({
      loadId,
      loadType: "base_tables_and_context",
      status: "failed",
      traceId,
      startedAt,
      completedAt: new Date().toISOString(),
      summary: {
        error: error instanceof Error ? error.message : String(error),
      },
    });
    throw error;
  } finally {
    await shutdownLangfuse();
  }
}

async function runLoadScript(repoRoot: string) {
  const dataDir = path.join(repoRoot, "data");
  const childEnv = {
    ...process.env,
    CH: process.env.CH ?? defaultLoadCommand(repoRoot),
    DB: process.env.CLICKHOUSE_DATABASE ?? "schema_kings",
  };

  return new Promise<{ stdout: string; stderr: string }>((resolve, reject) => {
    const child = spawn("bash", ["load.sh"], {
      cwd: dataDir,
      env: childEnv,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code === 0) {
        resolve({ stdout, stderr });
        return;
      }

      reject(
        new Error(
          `data/load.sh failed with exit code ${code}\nSTDOUT:\n${stdout}\nSTDERR:\n${stderr}`,
        ),
      );
    });
  });
}

function defaultLoadCommand(_repoRoot: string) {
  const config = getClickHouseConfig();
  const url = new URL(config.url);

  // Local: use the fixed container_name from docker-compose.yml.
  // Do NOT use `docker compose -f <path>` — repo paths can contain spaces
  // (e.g. "Query Kings") and load.sh cannot safely word-split those.
  // Do NOT wrap password in quotes — they'd become part of the password value.
  if (["localhost", "127.0.0.1", "::1"].includes(url.hostname)) {
    const container =
      process.env.CLICKHOUSE_DOCKER_CONTAINER?.trim() ||
      "schema-kings-clickhouse";
    // `-i` keeps stdin open so load.sh can pipe Parquet/SQL into clickhouse-client.
    // Do not use `-T` here — that flag exists on `docker compose exec`, not `docker exec`.
    return `docker exec -i ${container} clickhouse-client --user ${config.user} --password ${config.password}`;
  }

  // Homebrew / modern installs expose `clickhouse client`, not `clickhouse-client`.
  const secure = url.protocol === "https:" ? " --secure" : "";
  const nativePort =
    process.env.CLICKHOUSE_NATIVE_PORT ??
    (url.port === "8443" ? "9440" : url.port || "");
  const port = nativePort ? ` --port ${nativePort}` : "";
  return `clickhouse client --host ${url.hostname}${port} --user ${config.user} --password ${config.password}${secure}`;
}

function isTruthyEnv(value: string | undefined) {
  if (!value) return false;
  return ["1", "true", "yes", "on"].includes(value.trim().toLowerCase());
}
