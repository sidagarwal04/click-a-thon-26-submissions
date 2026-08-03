import {
  createServer,
  type IncomingMessage,
  type ServerResponse,
} from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { runAnalyticsAsk } from "../analytics.js";
import { generatePipelineReport } from "./generateReport.js";

export async function startReportServer(input?: {
  repoRoot?: string;
  port?: number;
}) {
  const repoRoot = input?.repoRoot ?? path.resolve(process.cwd(), "..");
  const port =
    input?.port ?? Number(process.env.PORT ?? process.env.REPORT_PORT ?? 8787);
  const host = process.env.HOST ?? "0.0.0.0";

  // Fresh overview on boot (ok if artifacts missing — Ask can still run).
  try {
    await generatePipelineReport({ repoRoot });
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    console.warn(`[report server] boot report skipped: ${message}`);
  }

  const server = createServer(async (req, res) => {
    try {
      await handleRequest(req, res, repoRoot);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      console.error("[report server]", message);
      json(res, 500, { error: message });
    }
  });

  await new Promise<void>((resolve) => {
    server.listen(port, host, () => resolve());
  });

  const url = `http://${host === "0.0.0.0" ? "localhost" : host}:${port}`;
  console.log("");
  console.log(`Report UI: ${url}`);
  console.log(`Listening on ${host}:${port}`);
  console.log("Ask from the page — answer lands in the same HTML.");
  console.log("Ctrl+C to stop.");
  console.log("");

  return { server, url, port };
}

async function handleRequest(
  req: IncomingMessage,
  res: ServerResponse,
  repoRoot: string,
) {
  const method = req.method ?? "GET";
  const url = new URL(req.url ?? "/", "http://127.0.0.1");

  if (method === "OPTIONS") {
    res.writeHead(204, corsHeaders());
    res.end();
    return;
  }

  if (
    method === "GET" &&
    (url.pathname === "/" || url.pathname === "/report.html")
  ) {
    const jobId = url.searchParams.get("job") ?? undefined;
    try {
      await generatePipelineReport({ repoRoot, jobId: jobId || undefined });
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      // Still serve a minimal Ask page if no artifacts are in ClickHouse yet.
      const fallback = minimalAskHtml(message);
      res.writeHead(200, {
        "content-type": "text/html; charset=utf-8",
        "cache-control": "no-store",
        ...corsHeaders(),
      });
      res.end(fallback);
      return;
    }
    const htmlPath = path.join(repoRoot, "frontend", "dist", "report.html");
    const html = await readFile(htmlPath, "utf8");
    res.writeHead(200, {
      "content-type": "text/html; charset=utf-8",
      "cache-control": "no-store",
      ...corsHeaders(),
    });
    res.end(html);
    return;
  }

  if (method === "GET" && url.pathname === "/report-data.json") {
    const jsonPath = path.join(
      repoRoot,
      "frontend",
      "dist",
      "report-data.json",
    );
    const body = await readFile(jsonPath, "utf8");
    res.writeHead(200, {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
      ...corsHeaders(),
    });
    res.end(body);
    return;
  }

  if (method === "POST" && url.pathname === "/api/ask") {
    const body = await readBody(req);
    let question = "";
    try {
      const parsed = JSON.parse(body) as { question?: string };
      question = parsed.question?.trim() ?? "";
    } catch {
      json(res, 400, { error: 'Expected JSON body: { "question": "..." }' });
      return;
    }
    if (!question) {
      json(res, 400, { error: "Missing question." });
      return;
    }

    console.log(`[ask] ${question}`);
    const answer = await runAnalyticsAsk({ question, repoRoot });
    const jobId = path.basename(answer.artifact_root);
    await generatePipelineReport({ repoRoot, jobId });

    json(res, 200, {
      job_id: jobId,
      question,
      short_answer: answer.short_answer,
      key_findings: answer.key_findings,
      evidence: answer.evidence,
      recommended_actions: answer.recommended_actions,
      caveats: answer.caveats,
      langfuse_trace_id: answer.trace_id,
      report_url: `/?job=${encodeURIComponent(jobId)}`,
    });
    return;
  }

  if (method === "GET" && url.pathname === "/api/health") {
    json(res, 200, { ok: true });
    return;
  }

  json(res, 404, { error: "Not found" });
}

function corsHeaders(): Record<string, string> {
  return {
    "access-control-allow-origin": "*",
    "access-control-allow-methods": "GET,POST,OPTIONS",
    "access-control-allow-headers": "content-type",
  };
}

function json(res: ServerResponse, status: number, payload: unknown) {
  res.writeHead(status, {
    "content-type": "application/json; charset=utf-8",
    ...corsHeaders(),
  });
  res.end(`${JSON.stringify(payload, null, 2)}\n`);
}

async function readBody(req: IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) {
    chunks.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  }
  return Buffer.concat(chunks).toString("utf8");
}

function minimalAskHtml(reason: string): string {
  const safe = reason.replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Schema Kings · Ask</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen">
  <main class="max-w-2xl mx-auto px-4 py-10 space-y-6">
    <h1 class="text-2xl font-semibold">Schema Kings</h1>
    <p class="text-slate-400 text-sm">Overview artifacts not loaded yet. Ask still runs against ClickHouse.</p>
    <p class="text-amber-200/80 text-xs font-mono break-words">${safe}</p>
    <form id="ask" class="space-y-3">
      <textarea name="question" rows="4" required
        class="w-full rounded-lg bg-slate-900 border border-slate-700 p-3 text-sm"
        placeholder="Ask a PM question…"></textarea>
      <button type="submit"
        class="rounded-lg bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-sm font-medium">Ask</button>
    </form>
    <pre id="out" class="text-xs whitespace-pre-wrap text-slate-300"></pre>
  </main>
  <script>
    document.getElementById("ask").addEventListener("submit", async (e) => {
      e.preventDefault();
      const question = new FormData(e.target).get("question");
      const out = document.getElementById("out");
      out.textContent = "Running analytics agent…";
      const res = await fetch("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      if (!res.ok) { out.textContent = data.error || res.statusText; return; }
      if (data.report_url) { location.href = data.report_url; return; }
      out.textContent = JSON.stringify(data, null, 2);
    });
  </script>
</body>
</html>
`;
}
