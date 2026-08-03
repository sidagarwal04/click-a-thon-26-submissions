import { NextRequest } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import { startRun, setPid, pushRawEvent, finishRun } from '@/lib/live-run-store';

export const maxDuration = 1200; // 20 minutes -- matches the internal TIMEOUT_MS below

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const specName = formData.get('specName') as string;
    const specMarkdown = formData.get('specMarkdown') as string;
    const eventsFile = formData.get('eventsFile') as File;

    if (!specName || !specMarkdown || !eventsFile) {
      const encoder = new TextEncoder();
      return new Response(encoder.encode(`data: ${JSON.stringify({
        type: 'error',
        message: 'Missing required fields'
      })}\n\n`), {
        headers: { 'Content-Type': 'text/event-stream' }
      });
    }

    // Parse events from NDJSON file
    const eventsText = await eventsFile.text();
    const allEvents = eventsText
      .split('\n')
      .filter(line => line.trim())
      .map(line => JSON.parse(line));

    // Stratified sample, capped per event type (same PER_EVENT_SAMPLE=30 convention
    // as scripts/run_*.py) — the raw file can be thousands of rows, and sending that
    // whole thing as the propose payload blows the agent's context window entirely
    // (measured: a 6237-row unsampled file produced a >10M-token single message,
    // which LibreChat prunes to empty and then 500s on). The proposer only needs a
    // representative sample of each event's shape, not the full volume.
    const PER_EVENT_SAMPLE = 30;
    const byEventType = new Map<string, any[]>();
    for (const e of allEvents) {
      const key = e.event ?? 'unknown';
      const arr = byEventType.get(key) ?? [];
      if (arr.length < PER_EVENT_SAMPLE) { arr.push(e); byEventType.set(key, arr); }
    }
    const events = [...byEventType.values()].flat();

    if (events.length === 0) {
      const encoder = new TextEncoder();
      return new Response(encoder.encode(`data: ${JSON.stringify({
        type: 'error',
        message: 'No events found in the uploaded file'
      })}\n\n`), {
        headers: { 'Content-Type': 'text/event-stream' }
      });
    }

    // Runs are tracked by runId now, not a single global slot -- generated
    // before the stream starts so it can go on the Response's headers
    // immediately (the client needs it to poll /api/live-run?runId=... after
    // a reload, see components/agent-panel.tsx).
    const runId = startRun(specName, 'ingest');

    // Create readable stream for Server-Sent Events
    const stream = new ReadableStream({
      async start(controller) {
        const encoder = new TextEncoder();

        // The browser that started this request can disconnect at any point
        // (panel closed, tab navigated away, network blip) WITHOUT the
        // spawned python subprocess stopping -- it's an independent OS
        // process that keeps running against ClickHouse/Langfuse regardless
        // (that's the whole point of live-run-store: reconnect from any
        // browser later). Once the underlying connection is gone,
        // controller.enqueue() throws ("Controller is already closed" /
        // similar) -- previously that throw was UNCAUGHT inside the
        // 'data'/'close' handlers below, which aborted the rest of that
        // callback and meant pushRawEvent/finishRun for every event AFTER
        // the disconnect never ran. sendEvent must never be able to take
        // down its caller.
        const sendEvent = (data: any) => {
          try {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
          } catch { /* this browser is gone -- live-run-store below is still recorded correctly */ }
        };
        const safeClose = () => {
          try { controller.close(); } catch { /* already closed */ }
        };

        // Write events + spec to temp JSON files — avoids JSON→Python literal mismatch
        // (JSON false/true/null ≠ Python False/True/None)
        const ts = Date.now();
        const tmpEventsPath     = path.join('/tmp', `events_${ts}.json`);
        const tmpFullEventsPath = path.join('/tmp', `full_events_${ts}.json`);
        const tmpSpecPath       = path.join('/tmp', `spec_${ts}.md`);
        const tmpScriptPath     = path.join('/tmp', `ingest_${ts}.py`);

        fs.writeFileSync(tmpEventsPath,     JSON.stringify(events));
        fs.writeFileSync(tmpFullEventsPath, JSON.stringify(allEvents));
        fs.writeFileSync(tmpSpecPath,       specMarkdown);

        const agentsPath = path.join(process.cwd(), '../atlys-agents');
        const pythonScript = `
import sys, json
sys.path.insert(0, ${JSON.stringify(agentsPath)})

def log_progress(stage, message):
    print(json.dumps({"type": "log", "stage": stage, "message": message}), flush=True)

log_progress("init", "Starting ingestion pipeline...")

with open(${JSON.stringify(tmpEventsPath)}) as f:
    sample_events = json.load(f)

with open(${JSON.stringify(tmpFullEventsPath)}) as f:
    full_events = json.load(f)

with open(${JSON.stringify(tmpSpecPath)}) as f:
    spec_markdown = f.read()

log_progress("init", f"Loaded {len(sample_events)} sample events ({len(full_events)} full events for perf test / test harness / production insert)")

from orchestrator import ingest_spec

log_progress("orchestrator", "Calling ingest_spec...")

try:
    result = ingest_spec(
        spec_name=${JSON.stringify(specName)},
        spec_markdown=spec_markdown,
        sample_events=sample_events,
        full_events=full_events,
    )
    log_progress("complete", "Pipeline finished")
    print(json.dumps({"type": "result", "data": result}, default=str), flush=True)
except Exception as e:
    import traceback
    log_progress("error", f"Pipeline failed: {str(e)}")
    log_progress("error", traceback.format_exc())
    print(json.dumps({"type": "result", "data": {"error": str(e), "status": "failed"}}, default=str), flush=True)
    sys.exit(1)
`;
        fs.writeFileSync(tmpScriptPath, pythonScript);

        sendEvent({ type: 'log', stage: 'init', message: '🚀 Initializing pipeline...' });

        const agentsDir = path.join(process.cwd(), '../atlys-agents');
        const venvPython = path.join(agentsDir, '.venv/bin/python');

        // Load atlys-agents .env vars so the subprocess has ClickHouse/Langfuse creds
        const agentsEnv: Record<string, string> = {};
        try {
          const envFile = fs.readFileSync(path.join(agentsDir, '.env'), 'utf8');
          for (const line of envFile.split('\n')) {
            const m = line.match(/^([A-Z_][A-Z0-9_]*)=(.*)$/);
            if (m) agentsEnv[m[1]] = m[2].replace(/^["']|["']$/g, '');
          }
        } catch { /* .env not found, continue */ }

        const python = spawn(venvPython, [tmpScriptPath], {
          env: {
            ...process.env,
            ...agentsEnv,
            PYTHONPATH: agentsDir,
            PYTHONUNBUFFERED: '1',
            // dashboard/emitter.py: when set, every run.log()/span() event also
            // prints as one JSON line (type: "trace_event") on stdout, in
            // addition to its normal POST to the standalone 8787 dashboard.
            // The stdout handler below already forwards any non-"result" JSON
            // line straight through this SSE stream -- no extra parsing needed.
            EMIT_TRACE_EVENTS_STDOUT: '1',
          },
        });
        // Recorded so a stuck `active: true` can self-heal by checking
        // whether this pid is still alive, regardless of how tracking went
        // stale (dev server restart, this process getting killed, etc.) --
        // see lib/live-run-store.ts's heal().
        if (python.pid) setPid(runId, python.pid);

        let finalResult: any = null;

        python.stdout.on('data', (data) => {
          const lines = data.toString().split('\n').filter((l: string) => l.trim());
          for (const line of lines) {
            try {
              const parsed = JSON.parse(line);
              if (parsed.type === 'result') {
                finalResult = parsed.data;
              } else {
                // Record to live-run-store BEFORE trying to notify this
                // browser -- pushRawEvent must never be skipped just because
                // sendEvent's connection happens to be dead (see sendEvent's
                // comment above).
                if (parsed.type === 'trace_event') pushRawEvent(runId, parsed);
                sendEvent(parsed);
              }
            } catch (e) {
              // If not JSON, send as raw log
              sendEvent({ type: 'log', stage: 'output', message: line });
            }
          }
        });

        python.stderr.on('data', (data) => {
          const lines = data.toString().split('\n').filter((l: string) => l.trim());
          for (const line of lines) {
            // Skip noisy OTEL/tracing chatter
            if (line.includes('opentelemetry') || line.includes('OTLP') ||
                line.includes('Transient error') || line.includes('retrying in') ||
                line.includes('Failed to export') || line.includes('localhost:4317')) continue;

            const stage = line.includes('ERROR') || line.includes('Traceback') || line.includes('Exception')
              ? 'error'
              : line.includes('tool_call') || line.includes('list_context') || line.includes('run_query')
              ? 'tool'
              : line.includes('WARNING') ? 'warning'
              : 'trace';

            sendEvent({ type: 'log', stage, message: line });
          }
        });

        python.on('close', (code) => {
          for (const f of [tmpScriptPath, tmpEventsPath, tmpFullEventsPath, tmpSpecPath]) {
            try { fs.unlinkSync(f); } catch { /* ignore */ }
          }

          const result = finalResult ?? { status: 'failed', error: `Process exited with code ${code} — check run log above` };
          // finishRun FIRST, unconditionally -- this is the durable record
          // any browser reconnects to via /api/live-run. Notifying THIS
          // particular connection (sendEvent/close) is best-effort on top.
          finishRun(runId, result);
          sendEvent({ type: 'complete', result });
          safeClose();
        });

        // 4 minutes was set back when MAX_REVISIONS was 4 and the pipeline
        // was simpler -- with MAX_REVISIONS=6 and each revision running a
        // real multi-turn tool-calling propose AND review loop (10-20+ tool
        // calls each, reasoning.effort="medium"), a genuinely legitimate run
        // can take well over 4 minutes. That killed real in-progress work
        // outright, with nothing durable written yet for the killed attempt
        // (schema_proposals only gets a row once a revision's propose/review
        // cycle actually completes) -- it just vanished, no trace anywhere.
        // 20 minutes is a generous ceiling for a hackathon-scale run while
        // still bounding a genuinely stuck process.
        const TIMEOUT_MS = 20 * 60 * 1000;
        setTimeout(() => {
          python.kill();
          const result = { status: 'failed', error: `Pipeline timeout after ${TIMEOUT_MS / 60000} minutes` };
          finishRun(runId, result);
          sendEvent({ type: 'error', message: result.error });
          safeClose();
        }, TIMEOUT_MS);
      }
    });

    return new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Run-Id': runId,
      },
    });
  } catch (error) {
    console.error('Ingestion error:', error);
    const encoder = new TextEncoder();
    return new Response(encoder.encode(`data: ${JSON.stringify({
      type: 'error',
      message: error instanceof Error ? error.message : 'Failed to run ingestion'
    })}\n\n`), {
      headers: { 'Content-Type': 'text/event-stream' }
    });
  }
}
