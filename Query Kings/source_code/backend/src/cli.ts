import "dotenv/config";
import path from "node:path";
import { runAnalyticsAsk } from "./pipeline/analytics.js";
import { bootstrapContext } from "./pipeline/context.js";
import {
  generatePipelineReport,
  startReportServer,
} from "./pipeline/report/index.js";
import { runPipeline } from "./pipeline/runPipeline.js";
import { runSetup } from "./pipeline/setup.js";

const [, , command, ...args] = process.argv;
const specFolder = args[0];

function printHelp() {
  console.log(`
Schema Kings CLI

Usage:
  pnpm cli setup
  pnpm cli context:bootstrap
  pnpm cli run <spec-folder>
  pnpm cli ask <question>
  pnpm cli report [job_id]
  pnpm cli serve [--port 8787]
  pnpm pipeline <spec-folder>

Examples:
  pnpm cli setup
  pnpm cli context:bootstrap
  pnpm cli run ../specs/05_instant_forex
  pnpm cli ask "Why is express checkout completion lower on iOS?"
  pnpm cli report
  pnpm cli report 20260801T210941
  pnpm cli serve
  pnpm pipeline ../specs/01_express_checkout
`);
}

function parseReportArgs(argv: string[]): { jobId?: string } {
  let jobId: string | undefined;
  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i];
    if (arg === "--job") {
      jobId = argv[i + 1];
      i += 1;
      continue;
    }
    if (arg.startsWith("--job=")) {
      jobId = arg.slice("--job=".length);
      continue;
    }
    if (!arg.startsWith("-") && !jobId) {
      jobId = arg;
    }
  }
  return { jobId };
}

async function main() {
  if (
    !command ||
    command === "help" ||
    command === "--help" ||
    command === "-h"
  ) {
    printHelp();
    return;
  }

  if (command === "context:bootstrap") {
    const repoRoot = path.resolve(process.cwd(), "..");
    const registry = await bootstrapContext(repoRoot);
    console.log("Context bootstrap completed.");
    console.log(`Features in context: ${registry.features.length}`);
    console.log(`Open contradictions: ${registry.contradictions.length}`);
    return;
  }

  if (command === "setup") {
    const repoRoot = path.resolve(process.cwd(), "..");
    await runSetup({ repoRoot });
    return;
  }

  if (command === "ask") {
    const question = args.join(" ").trim();
    if (!question) {
      console.error("Missing required <question> argument.");
      printHelp();
      process.exitCode = 1;
      return;
    }
    const answer = await runAnalyticsAsk({ question });
    console.log("");
    console.log(answer.short_answer);
    if (answer.key_findings.length > 0) {
      console.log("");
      console.log("Key findings:");
      for (const finding of answer.key_findings) {
        console.log(`- ${finding}`);
      }
    }
    if (answer.evidence.length > 0) {
      console.log("");
      console.log("Evidence (claim → query → confidence):");
      for (const claim of answer.evidence) {
        console.log(
          `- [${claim.confidence}] ${claim.claim} (query: ${claim.query_id})`,
        );
      }
    }
    if (answer.recommended_actions.length > 0) {
      console.log("");
      console.log("Recommended actions:");
      for (const action of answer.recommended_actions) {
        console.log(`- ${action}`);
      }
    }
    if (answer.caveats.length > 0) {
      console.log("");
      console.log("Caveats:");
      for (const caveat of answer.caveats) {
        console.log(`- ${caveat}`);
      }
    }
    console.log("");
    console.log(`Artifacts: ${answer.artifact_root}`);
    console.log(`Langfuse trace ID: ${answer.trace_id}`);

    const jobId = path.basename(answer.artifact_root);
    const repoRoot = path.resolve(process.cwd(), "..");
    try {
      const { htmlPath } = await generatePipelineReport({
        repoRoot,
        jobId,
      });
      console.log("");
      console.log(`HTML report (same answer): ${htmlPath}`);
      console.log(`Re-open later: pnpm cli report ${jobId}`);
    } catch (error) {
      console.log("");
      console.log(
        `Report HTML skipped: ${error instanceof Error ? error.message : String(error)}`,
      );
      console.log(`Generate manually: pnpm cli report ${jobId}`);
    }

    if (
      /temporarily unavailable|Strict analytics mode refused/i.test(
        `${answer.short_answer}\n${answer.caveats.join("\n")}`,
      )
    ) {
      process.exitCode = 2;
    }
    return;
  }

  if (command === "serve") {
    const repoRoot = path.resolve(process.cwd(), "..");
    let port = Number(process.env.PORT ?? process.env.REPORT_PORT ?? 8787);
    for (let i = 0; i < args.length; i += 1) {
      if (args[i] === "--port") {
        port = Number(args[i + 1] ?? port);
        i += 1;
      } else if (args[i].startsWith("--port=")) {
        port = Number(args[i].slice("--port=".length));
      }
    }
    await startReportServer({ repoRoot, port });
    // Keep process alive.
    await new Promise(() => {});
    return;
  }

  if (command === "report") {
    const { jobId } = parseReportArgs(args);
    const repoRoot = path.resolve(process.cwd(), "..");
    const { report, htmlPath, jsonPath } = await generatePipelineReport({
      repoRoot,
      jobId,
    });
    console.log("");
    console.log(`Report: ${report.mode} — ${report.title}`);
    if (report.job_id) {
      console.log(`Focus job: ${report.job_id}`);
      console.log(
        report.mode === "ask"
          ? "Single ask page (not the full overview)."
          : "Single instrumentation page (not the full overview).",
      );
    } else {
      console.log(
        `Features: ${report.stats.features_instrumented} · runs: ${report.stats.instrumentation_runs} · asks: ${report.stats.ask_jobs}`,
      );
    }
    console.log(`HTML: ${htmlPath}`);
    console.log(`JSON: ${jsonPath}`);
    console.log("");
    console.log("Open the HTML in a browser.");
    return;
  }

  if (command !== "run") {
    console.error(`Unknown command: ${command}`);
    printHelp();
    process.exitCode = 1;
    return;
  }

  if (!specFolder) {
    console.error("Missing required <spec-folder> argument.");
    printHelp();
    process.exitCode = 1;
    return;
  }

  await runPipeline({ specFolder });
}

main().catch((error) => {
  console.error("CLI failed:");
  console.error(error);
  process.exitCode = 1;
});
