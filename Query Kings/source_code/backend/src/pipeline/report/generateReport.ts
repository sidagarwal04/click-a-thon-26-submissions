import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { assemblePipelineReport } from "./assemble.js";
import { renderReportHtml } from "./renderHtml.js";
import type { PipelineReport } from "./types.js";

export async function generatePipelineReport(input: {
  repoRoot?: string;
  jobId?: string;
}): Promise<{
  report: PipelineReport;
  htmlPath: string;
  jsonPath: string;
}> {
  const repoRoot = input.repoRoot ?? path.resolve(process.cwd(), "..");
  const report = await assemblePipelineReport({
    repoRoot,
    jobId: input.jobId,
  });

  const outDir = path.join(repoRoot, "frontend", "dist");
  await mkdir(outDir, { recursive: true });

  const htmlPath = path.join(outDir, "report.html");
  const jsonPath = path.join(outDir, "report-data.json");

  await writeFile(htmlPath, `${renderReportHtml(report)}\n`, "utf8");
  await writeFile(jsonPath, `${JSON.stringify(report, null, 2)}\n`, "utf8");

  return { report, htmlPath, jsonPath };
}
