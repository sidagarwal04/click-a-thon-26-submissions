import { NextRequest } from 'next/server';
import { spawn } from 'child_process';
import path from 'path';
import fs from 'fs';
import { startRun, setPid, pushRawEvent, finishRun } from '@/lib/live-run-store';

// A custom_investigation prompt can span several tables (more list_tables/
// describe_table/run_query calls than a single-table spec analysis) -- match
// ingest's 20-minute budget rather than the old 4-minute one, which was found
// to kill legitimate multi-revision ingest runs mid-way with zero trace left
// behind (see app/api/ingest/route.ts's TIMEOUT_MS).
export const maxDuration = 1200;

// Counterpart to /api/ingest for the analytics half of the pipeline. Two
// trigger shapes, one endpoint: `{specName}` runs
// analytics.analytics_agent.run_analytics_for_spec(spec_name) (the existing
// "Create Insight" flow, scoped to one already-executed spec's PM questions);
// `{prompt}` runs run_analytics_for_prompt(prompt) instead -- a free-text
// investigation with no single table handed to the agent, which decides what's
// relevant itself via list_tables (see ANALYTICS_AGENT's custom_investigation
// branch in agents/prompts.py). Both stream the same trace_event/log/complete
// SSE shape /api/ingest already produces -- the right panel
// (components/agent-panel.tsx) renders both through the exact same
// TraceViewer, no branching needed there for the wire format itself. Shares
// live-run-store with ingest -- runs are tracked by runId now (see
// lib/live-run-store.ts), so an ingestion and an analytics run (or several
// analytics runs) can be genuinely active at once without colliding.
export async function POST(request: NextRequest) {
  try {
    const { specName, prompt } = await request.json();

    if (!specName && !prompt) {
      const encoder = new TextEncoder();
      return new Response(encoder.encode(`data: ${JSON.stringify({
        type: 'error', message: 'Missing specName or prompt',
      })}\n\n`), { headers: { 'Content-Type': 'text/event-stream' } });
    }

    // Generated before the stream starts so it can go on the Response's
    // headers immediately -- see app/api/ingest/route.ts's same pattern.
    const runId = startRun(specName || String(prompt).slice(0, 80), 'analytics');

    const stream = new ReadableStream({
      async start(controller) {
        const encoder = new TextEncoder();
        // See app/api/ingest/route.ts's sendEvent comment: the browser that
        // started this request can disconnect at any point without the
        // spawned python process stopping. An unguarded controller.enqueue()
        // throwing here used to abort the rest of the 'data'/'close' handler
        // it was called from, which meant pushRawEvent/finishRun for every
        // event after the disconnect never ran -- live-run-store stayed
        // stuck `active: true` forever, blocking all future runs.
        const sendEvent = (data: any) => {
          try {
            controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
          } catch { /* this browser is gone -- live-run-store below is still recorded correctly */ }
        };
        const safeClose = () => {
          try { controller.close(); } catch { /* already closed */ }
        };

        const ts = Date.now();
        const tmpScriptPath = path.join('/tmp', `analytics_${ts}.py`);
        const agentsPath = path.join(process.cwd(), '../atlys-agents');

        const pythonScript = specName ? `
import sys, json
sys.path.insert(0, ${JSON.stringify(agentsPath)})

def log_progress(stage, message):
    print(json.dumps({"type": "log", "stage": stage, "message": message}), flush=True)

log_progress("init", "Starting analytics agent...")

from analytics.analytics_agent import run_analytics_for_spec

try:
    result = run_analytics_for_spec(${JSON.stringify(specName)})
    log_progress("complete", "Analytics finished")
    print(json.dumps({"type": "result", "data": result}, default=str), flush=True)
except Exception as e:
    import traceback
    log_progress("error", f"Analytics failed: {str(e)}")
    log_progress("error", traceback.format_exc())
    print(json.dumps({"type": "result", "data": {"error": str(e), "status": "failed"}}, default=str), flush=True)
    sys.exit(1)
` : `
import sys, json
sys.path.insert(0, ${JSON.stringify(agentsPath)})

def log_progress(stage, message):
    print(json.dumps({"type": "log", "stage": stage, "message": message}), flush=True)

log_progress("init", "Starting analytics agent...")

from analytics.analytics_agent import run_analytics_for_prompt

try:
    result = run_analytics_for_prompt(${JSON.stringify(prompt)})
    log_progress("complete", "Analytics finished")
    print(json.dumps({"type": "result", "data": result}, default=str), flush=True)
except Exception as e:
    import traceback
    log_progress("error", f"Analytics failed: {str(e)}")
    log_progress("error", traceback.format_exc())
    print(json.dumps({"type": "result", "data": {"error": str(e), "status": "failed"}}, default=str), flush=True)
    sys.exit(1)
`;
        fs.writeFileSync(tmpScriptPath, pythonScript);

        sendEvent({ type: 'log', stage: 'init', message: '🚀 Starting analytics agent...' });

        const agentsDir = path.join(process.cwd(), '../atlys-agents');
        const venvPython = path.join(agentsDir, '.venv/bin/python');

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
            EMIT_TRACE_EVENTS_STDOUT: '1',
          },
        });
        // See app/api/ingest/route.ts's same call for why.
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
                // browser -- see sendEvent's comment above.
                if (parsed.type === 'trace_event') pushRawEvent(runId, parsed);
                sendEvent(parsed);
              }
            } catch (e) {
              sendEvent({ type: 'log', stage: 'output', message: line });
            }
          }
        });

        python.stderr.on('data', (data) => {
          const lines = data.toString().split('\n').filter((l: string) => l.trim());
          for (const line of lines) {
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
          try { fs.unlinkSync(tmpScriptPath); } catch { /* ignore */ }

          const result = finalResult ?? { status: 'failed', error: `Process exited with code ${code} — check run log above` };
          // finishRun FIRST, unconditionally -- see sendEvent's comment above.
          finishRun(runId, result);
          sendEvent({ type: 'complete', result });
          safeClose();
        });

        const TIMEOUT_MS = 20 * 60 * 1000;
        setTimeout(() => {
          python.kill();
          const result = { status: 'failed', error: 'Analytics timeout after 20 minutes' };
          finishRun(runId, result);
          sendEvent({ type: 'error', message: result.error });
          safeClose();
        }, TIMEOUT_MS);
      },
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
    console.error('Analytics trigger error:', error);
    const encoder = new TextEncoder();
    return new Response(encoder.encode(`data: ${JSON.stringify({
      type: 'error',
      message: error instanceof Error ? error.message : 'Failed to run analytics',
    })}\n\n`), { headers: { 'Content-Type': 'text/event-stream' } });
  }
}
