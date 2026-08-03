'use client';

import { useEffect, useRef, useState, useLayoutEffect, useCallback } from 'react';
import { X, FolderOpen, Play, Loader2, CheckCircle, XCircle, RotateCcw, ExternalLink, LineChart } from 'lucide-react';
import { usePanelCtx } from '@/lib/panel-context';
import { TraceViewer } from '@/components/trace/TraceViewer';
import type { AgentEvent } from '@/components/trace/types';
import type { SpecSummary } from '@/app/api/specs/route';
import type { LiveRunSnapshot } from '@/lib/live-run-store';

// ── types ─────────────────────────────────────────────────────────────────────

type Mode = 'idle' | 'folder-selected' | 'running' | 'done';

interface LogEntry {
  id: string;
  stage: string;
  message: string;
  ts: number;
}

export interface RunResult {
  status: string;
  proposal_id?: string;
  table_name?: string;
  ddl?: string;
  revisions?: number;
  regression_passed?: boolean;
  trace_url?: string;
  reason?: string;
  error?: string;
  // analytics-mode fields (run_analytics_for_spec's return shape — see
  // atlys-agents/analytics/analytics_agent.py)
  insight_id?: string;
  title?: string;
  confidence?: number;
}

// ── helpers ───────────────────────────────────────────────────────────────────

const STAGE_COLOR: Record<string, string> = {
  init:     '#2563eb',
  trace:    '#7c3aed',
  tool:     '#d97706',
  complete: '#16a34a',
  error:    '#dc2626',
  warning:  '#d97706',
  output:   '#4a4540',
};

function stageColor(stage: string) {
  return STAGE_COLOR[stage] ?? '#9c9088';
}

function elapsedStr(ts: number) {
  const s = (Date.now() - ts) / 1000;
  if (s < 2)  return 'now';
  if (s < 60) return `${Math.floor(s)}s`;
  return `${Math.floor(s / 60)}m`;
}

// Strip leading number prefix: "01_express_checkout" → "express_checkout"
function folderToSpecName(folder: string): string {
  return folder.replace(/^\d+_/, '');
}

// Tool-call input/output arrive as JSON-encoded STRINGS, not objects -- both
// live (Python's runner.py logs the raw function_call.arguments string
// straight through) and persisted (agent_meta.trace_events is a String
// column, everything non-string gets json.dumps'd -- see langfuse_wrapper.py's
// _stringify). The widgets (SqlWidget, PythonWidget, GenerationWidget's usage
// display, ...) expect real objects, so parse back before handing off.
function tryParseJSON(v: unknown): unknown {
  if (typeof v !== 'string' || v === '') return v;
  try { return JSON.parse(v); } catch { return v; }
}

// Handles two related-but-distinct raw shapes with one function:
//   - live SSE trace_event: raw.ts in seconds, raw.spec, usage/metadata
//     already objects (dashboard/emitter.py never stringifies them)
//   - persisted /api/specs/[name]/events row: raw.ts_ms, raw.spec_name,
//     usage/metadata as JSON strings (agent_meta.trace_events is all-String)
function normalizeTraceEvent(raw: Record<string, any>): AgentEvent {
  const rawKind: string = raw.kind ?? 'log';
  const kind = ['span_start', 'span_end', 'trace_start', 'trace_end'].includes(raw.event)
    ? raw.event
    : rawKind;
  const usage = tryParseJSON(raw.usage) as AgentEvent['usage'] | undefined;
  const metadata = tryParseJSON(raw.metadata) as Record<string, any> | undefined;
  return {
    id: crypto.randomUUID(),
    ts: raw.ts_ms ?? (raw.ts ?? Date.now() / 1000) * 1000,
    kind,
    step: raw.step ?? raw.event ?? '',
    agent: raw.agent,
    spec: raw.spec ?? raw.spec_name,
    trace_id: raw.trace_id,
    trace_url: raw.trace_url,
    input: tryParseJSON(raw.input),
    output: tryParseJSON(raw.output),
    reasoning: raw.reasoning || undefined,
    model_reasoning: metadata?.model_reasoning ?? undefined,
    usage: usage && typeof usage === 'object' && Object.keys(usage).length ? usage : undefined,
    n_tool_calls: metadata?.n_tool_calls,
  };
}

// ── log row ───────────────────────────────────────────────────────────────────

function LogRow({ entry }: { entry: LogEntry }) {
  const [expanded, setExpanded] = useState(false);
  const color  = stageColor(entry.stage);
  const isLong = entry.message.length > 100;

  return (
    <div
      className="flex items-start gap-2 py-1.5 border-b last:border-0"
      style={{ borderColor: '#f0ece6', cursor: isLong ? 'pointer' : 'default' }}
      onClick={() => isLong && setExpanded(v => !v)}
    >
      <span className="mt-1.5 h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ backgroundColor: color }} />
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-1.5">
          <span className="flex-shrink-0 text-[9px] font-bold uppercase tracking-widest"
            style={{ color }}>{entry.stage}</span>
          <p className="flex-1 text-[11.5px]"
            style={{
              color: '#4a4540',
              whiteSpace: expanded ? 'pre-wrap' : 'nowrap',
              overflow: expanded ? 'visible' : 'hidden',
              textOverflow: expanded ? 'clip' : 'ellipsis',
              fontFamily: expanded ? 'ui-monospace, monospace' : 'inherit',
            }}>
            {entry.message}
          </p>
          <span className="flex-shrink-0 text-[10px]" style={{ color: '#c0b8b0' }}>
            {elapsedStr(entry.ts)}
          </span>
        </div>
        {isLong && !expanded && (
          <p className="text-[9px] mt-0.5" style={{ color: '#c0b8b0' }}>tap to expand</p>
        )}
      </div>
    </div>
  );
}

// ── main panel ────────────────────────────────────────────────────────────────

export function AgentPanel() {
  const { close, mode: panelMode, historySpec, historyInsight, analyticsSpec } = usePanelCtx();

  // ── history mode: the real persisted trace (agent_meta.trace_events) for
  // EITHER how a spec was most recently ingested (historySpec — propose/
  // review/execute, agent='pipeline') OR one specific insight's own analytics
  // run (historyInsight — agent='analytics'). A spec can have several
  // insights now that analytics is an explicit, re-runnable step (see
  // lib/panel-context.tsx's HistoryInsightTarget), so "this spec's trace"
  // isn't specific enough once you're looking at one particular insight —
  // hence the separate endpoint keyed by insight_id
  // (/api/insights/[id]/events) rather than spec_name.
  //
  // Gap this closes for historySpec (the original case): clicking a spec row
  // always opened history mode, which only ever looked at trace_events -- but
  // that table is only populated by ONE bulk insert at traced_run()'s END
  // (see lib/live-run-store.ts's docstring for why). If you reload and click
  // the spec that's STILL running, history mode found nothing there yet and
  // showed "no persisted trace", even though the run was actively producing a
  // real trace this whole time. Check live-run-store FIRST for this exact
  // spec; only fall back to the persisted fetch if it isn't the one currently
  // in flight. (historyInsight skips this reconnect path entirely — a past
  // insight's trace is always a finished, persisted run.)
  const [historyEvents, setHistoryEvents]   = useState<AgentEvent[]>([]);
  const [historyMeta,   setHistoryMeta]     = useState<{ status?: string } | null>(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError,   setHistoryError]   = useState<string | null>(null);
  const [historyIsLive,  setHistoryIsLive]  = useState(false);

  useEffect(() => {
    if (panelMode !== 'history' || (!historySpec && !historyInsight)) return;
    let pollTimer: ReturnType<typeof setInterval> | null = null;
    setHistoryLoading(true);
    setHistoryError(null);
    setHistoryIsLive(false);

    if (historyInsight) {
      fetch(`/api/insights/${historyInsight.insightId}/events`)
        .then(r => r.json())
        .then(eventsRes => setHistoryEvents((eventsRes.events ?? []).map(normalizeTraceEvent)))
        .catch(e => setHistoryError(String(e)))
        .finally(() => setHistoryLoading(false));
      return;
    }

    const loadPersisted = () => {
      Promise.all([
        fetch(`/api/specs/${historySpec}/events`).then(r => r.json()),
        fetch(`/api/specs/${historySpec}/runs`).then(r => r.json()),
      ])
        .then(([eventsRes, runsRes]) => {
          setHistoryEvents((eventsRes.events ?? []).map(normalizeTraceEvent));
          setHistoryMeta({ status: runsRes.proposals?.[0]?.status });
        })
        .catch(e => setHistoryError(String(e)))
        .finally(() => setHistoryLoading(false));
    };

    const pollLive = (runId: string) => {
      fetch(`/api/live-run?runId=${runId}`).then(r => r.json()).then((d: LiveRunSnapshot | null) => {
        if (!d) { if (pollTimer) { clearInterval(pollTimer); pollTimer = null; } loadPersisted(); return; }
        setHistoryEvents(d.events.map(normalizeTraceEvent));
        if (!d.active) {
          if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
          setHistoryIsLive(false);
          loadPersisted(); // the run just finished -- switch to the durable record
        }
      }).catch(() => {});
    };

    // historySpec always means "this spec's ingestion trace" -- an in-flight
    // analytics run for this same (already-executed) spec is a DIFFERENT run
    // (its own runId, kind 'analytics') and must never be shown here (see
    // lib/live-run-store.ts's kind doc). Multiple ingestions can be active at
    // once now -- find the one (if any) whose label matches this spec.
    fetch('/api/live-run?kind=ingest').then(r => r.json()).then((d: { runs: LiveRunSnapshot[] }) => {
      const match = d.runs.find(r => r.label === historySpec);
      if (match) {
        setHistoryIsLive(true);
        setHistoryLoading(false);
        setHistoryEvents(match.events.map(normalizeTraceEvent));
        setHistoryMeta({ status: 'running' });
        pollTimer = setInterval(() => pollLive(match.runId), 1500);
      } else {
        loadPersisted();
      }
    }).catch(loadPersisted);

    return () => { if (pollTimer) clearInterval(pollTimer); };
  }, [panelMode, historySpec, historyInsight]);

  const [mode,     setMode]     = useState<Mode>('idle');
  const [specName, setSpecName] = useState('');
  const [specFile, setSpecFile] = useState<File | null>(null);
  const [eventsFile, setEventsFile] = useState<File | null>(null);
  const [logs,     setLogs]     = useState<LogEntry[]>([]);
  const [traceEvents, setTraceEvents] = useState<AgentEvent[]>([]);
  const [result,   setResult]   = useState<RunResult | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const traceEndRef = useRef<HTMLDivElement>(null);
  const folderRef  = useRef<HTMLInputElement>(null);

  // Resizable
  const [width, setWidth] = useState(560);
  const dragging   = useRef(false);
  const dragStartX = useRef(0);
  const dragStartW = useRef(0);

  const onDragStart = useCallback((e: React.MouseEvent) => {
    dragging.current = true;
    dragStartX.current = e.clientX;
    dragStartW.current = width;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [width]);

  useLayoutEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const delta = dragStartX.current - e.clientX;
      setWidth(Math.min(920, Math.max(300, dragStartW.current + delta)));
    };
    const onUp = () => {
      dragging.current = false;
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
    return () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
  }, []);

  useEffect(() => { logsEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [logs]);
  useEffect(() => { traceEndRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [traceEvents]);

  const addLog = (stage: string, message: string) =>
    setLogs(prev => [...prev, { id: crypto.randomUUID(), stage, message, ts: Date.now() }]);

  // Reattach to an in-progress (or just-finished) run on mount -- /api/ingest
  // and /api/analytics's SSE streams are both tied to the browser request
  // that started them, so a page reload loses it entirely otherwise (see
  // lib/live-run-store.ts, shared by both). Relevant in 'new' AND 'analytics'
  // mode -- history mode already fetches its own data.
  useEffect(() => {
    if (panelMode !== 'new' && panelMode !== 'analytics') return;
    let pollTimer: ReturnType<typeof setInterval> | null = null;

    // Only reconnect into 'running' -- a leftover FINISHED run must never
    // hijack a fresh panel open into showing a stale result (finished runs
    // stay in the store for a while so a reload during the trailing "Done"
    // screen doesn't lose it, not so the NEXT unrelated panel open inherits
    // it). Several runs of this kind can be active at once now -- this one
    // panel instance just reconnects to the most recent (listActiveRuns
    // returns newest-first).
    const expectedKind = panelMode === 'analytics' ? 'analytics' : 'ingest';
    const applyRun = (run: LiveRunSnapshot | undefined | null): boolean => {
      if (!run || !run.active) return false;
      setSpecName(run.label);
      setTraceEvents(run.events.map(normalizeTraceEvent));
      setMode('running');
      return true;
    };

    fetch(`/api/live-run?kind=${expectedKind}`).then(r => r.json()).then((data: { runs: LiveRunSnapshot[] }) => {
      const current = data.runs[0];
      const active = applyRun(current);
      if (active) {
        const runId = current.runId;
        pollTimer = setInterval(() => {
          fetch(`/api/live-run?runId=${runId}`).then(r => r.json()).then((d: LiveRunSnapshot | null) => {
            const stillActive = applyRun(d);
            if (!stillActive) {
              if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
              if (d?.result) { setResult(d.result as RunResult); setMode('done'); }
            }
          }).catch(() => {});
        }, 1500);
      } else if (panelMode === 'analytics') {
        // Nothing currently running -- initialize into the spec picker, or
        // straight to the confirm step if opened pre-targeted at one spec.
        setResult(null); setTraceEvents([]); setLogs([]);
        if (analyticsSpec) { setSpecName(analyticsSpec); setMode('folder-selected'); }
        else { setSpecName(''); setMode('idle'); }
      }
    }).catch(() => {});

    return () => { if (pollTimer) clearInterval(pollTimer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [panelMode, analyticsSpec]);

  // Analytics mode's spec picker: only specs whose latest proposal actually
  // reached 'executed' are eligible (same gate analytics_agent.py's
  // run_analytics_for_spec enforces server-side -- this is just the UI's
  // early filter so an ineligible spec never even shows up to click).
  const [eligibleSpecs, setEligibleSpecs] = useState<SpecSummary[]>([]);
  const [eligibleLoading, setEligibleLoading] = useState(false);

  // Analytics mode has two ways in: pick an already-executed spec (existing
  // flow, scoped to that spec's own PM questions), or type a free-text
  // question with no single table in mind -- run_analytics_for_prompt, see
  // ANALYTICS_AGENT's custom_investigation branch in agents/prompts.py. Kept
  // as a separate `customPrompt` state rather than overloading `specName`
  // (which the running/done screens already use as a display label) so the
  // POST payload and the label text can't accidentally diverge.
  const [analyticsTab, setAnalyticsTab] = useState<'spec' | 'custom'>('spec');
  const [customPrompt, setCustomPrompt] = useState('');

  useEffect(() => {
    if (panelMode !== 'analytics') return;
    setEligibleLoading(true);
    fetch('/api/specs')
      .then(r => r.json())
      .then(d => setEligibleSpecs(Array.isArray(d) ? d.filter((s: SpecSummary) => s.latest_status === 'executed') : []))
      .catch(() => setEligibleSpecs([]))
      .finally(() => setEligibleLoading(false));
  }, [panelMode]);

  // /api/ingest's stderr handler forwards EVERY line from the Python
  // subprocess as a log entry, most classified 'trace'/'tool'/'warning' --
  // that's raw hyperdx/MCP logging passthrough, not agent activity (the real
  // reasoning/tool-call trace now comes from trace_event/TraceViewer). The
  // 'init'/'complete' lines ("Initializing pipeline...", "Loaded N sample
  // events...") were real but redundant too -- the live phase spinner and
  // the status banner already say that. Only genuine errors are worth
  // surfacing here.
  const visibleLogs = logs.filter(l => l.stage === 'error');

  // ── folder picker ───────────────────────────────────────────────────────────

  const handleFolderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files ?? []);
    if (!files.length) return;

    // Folder name from first file's relative path
    const folderName = files[0].webkitRelativePath.split('/')[0];
    const derivedName = folderToSpecName(folderName);

    // Find spec.md and events file
    const md   = files.find(f => f.name.endsWith('.md'));
    const ndjson = files.find(f => f.name.endsWith('.ndjson') || f.name.endsWith('.jsonl'));

    setSpecName(derivedName);
    setSpecFile(md ?? null);
    setEventsFile(ndjson ?? null);
    setMode('folder-selected');
  };

  // ── run ─────────────────────────────────────────────────────────────────────
  // Shared SSE consumption for BOTH /api/ingest and /api/analytics -- both
  // routes emit the identical trace_event/log/complete/error wire shape (see
  // app/api/analytics/route.ts's docstring), so only the request that kicks
  // each one off differs.
  const consumeSSEStream = async (res: Response) => {
    const reader = res.body!.getReader();
    const dec    = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const line of dec.decode(value).split('\n\n')) {
        if (!line.startsWith('data: ')) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if (data.type === 'trace_event') {
            setTraceEvents(prev => [...prev, normalizeTraceEvent(data)]);
          } else if (data.type === 'log') {
            addLog(data.stage ?? 'info', data.message);
          } else if (data.type === 'complete') {
            setResult(data.result);
            setMode('done');
          } else if (data.type === 'error') {
            addLog('error', data.message);
            setResult({ status: 'failed', error: data.message });
            setMode('done');
          }
        } catch { /* bad json */ }
      }
    }
  };

  const handleRun = async () => {
    if (!specFile || !eventsFile) return;
    setMode('running');
    setLogs([]);
    setTraceEvents([]);
    setResult(null);

    const specMarkdown = await specFile.text();
    const formData = new FormData();
    formData.append('specName', specName);
    formData.append('specMarkdown', specMarkdown);
    formData.append('eventsFile', eventsFile);

    try {
      const res = await fetch('/api/ingest', { method: 'POST', body: formData });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await consumeSSEStream(res);
    } catch (err) {
      addLog('error', String(err));
      setResult({ status: 'failed', error: String(err) });
      setMode('done');
    }
  };

  const handleRunAnalytics = async () => {
    const isCustom = analyticsTab === 'custom';
    if (isCustom ? !customPrompt.trim() : !specName) return;
    setMode('running');
    setLogs([]);
    setTraceEvents([]);
    setResult(null);

    try {
      const res = await fetch('/api/analytics', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(isCustom ? { prompt: customPrompt.trim() } : { specName }),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      await consumeSSEStream(res);
    } catch (err) {
      addLog('error', String(err));
      setResult({ status: 'failed', error: String(err) });
      setMode('done');
    }
  };

  // Tell the specs/insights list to refetch on ANY completion, not just
  // success -- this used to fire only on a successful outcome, so a run that
  // failed/timed out (a real, common outcome: needs_rework after exhausting
  // MAX_REVISIONS, or the 4-minute kill) never refreshed the list at all. The
  // row was always there in ClickHouse (durable regardless of this refetch
  // trigger) -- an already-open list page just kept showing its stale
  // pre-run snapshot until a manual reload. Auto-close/navigate-away stays
  // success-only: a failure should stay on screen so the error is actually
  // readable, not vanish after 1.8s. Analytics mode never auto-closes even on
  // success -- the insight report link in the DONE screen is the point of
  // staying open (see the DONE block below).
  useEffect(() => {
    if (mode !== 'done' || !specName) return;
    window.dispatchEvent(new Event(panelMode === 'analytics' ? 'insights-updated' : 'specs-updated'));
    if (panelMode === 'new' && result?.status === 'executed') {
      const t = setTimeout(() => close(), 1800);
      return () => clearTimeout(t);
    }
  }, [mode, result, specName, panelMode, close]);

  const reset = () => {
    setMode(panelMode === 'analytics' ? (analyticsSpec ? 'folder-selected' : 'idle') : 'idle');
    setLogs([]);
    setTraceEvents([]);
    setResult(null);
    if (panelMode !== 'analytics') setSpecName('');
    setSpecFile(null);
    setEventsFile(null);
    if (folderRef.current) folderRef.current.value = '';
  };

  const success = panelMode === 'analytics' ? result?.status === 'completed' : result?.status === 'executed';

  // Whichever event set is currently on screen (live ingest or history) —
  // every event on a trace shares the same trace_url, so the first one found
  // is enough.
  const activeTraceUrl = panelMode === 'history'
    ? historyEvents.find(e => e.trace_url)?.trace_url
    : traceEvents.find(e => e.trace_url)?.trace_url;

  return (
    <div
      className="relative flex h-screen flex-shrink-0 flex-col border-l"
      style={{ width, backgroundColor: '#ffffff', borderColor: '#e5dfd6' }}
    >
      {/* Drag handle */}
      <div onMouseDown={onDragStart}
        className="absolute left-0 top-0 z-10 h-full w-1 cursor-col-resize transition-colors hover:bg-blue-400/30" />

      {/* Hidden folder input */}
      <input
        ref={folderRef}
        type="file"
        className="hidden"
        // @ts-ignore — webkitdirectory is not in standard types
        webkitdirectory=""
        multiple
        onChange={handleFolderChange}
      />

      {/* Header */}
      <div className="flex h-14 flex-shrink-0 items-center justify-between border-b px-4"
        style={{ borderColor: '#e5dfd6' }}>
        <div className="flex items-center gap-2 min-w-0">
          {panelMode === 'history' ? (
            <>
              {(historyLoading || historyIsLive) && <Loader2 className="h-4 w-4 animate-spin text-blue-500 flex-shrink-0" />}
              {!historyLoading && !historyIsLive && (
                historyInsight
                  ? <LineChart className="h-4 w-4 flex-shrink-0" style={{ color: '#9c9088' }} />
                  : <FolderOpen className="h-4 w-4 flex-shrink-0" style={{ color: '#9c9088' }} />
              )}
              <span className="text-sm font-semibold truncate" style={{ color: '#1c1814' }}>
                {historyInsight ? (historyInsight.title || 'Insight trace') : (
                  <span className="font-mono">{historySpec}</span>
                )}
              </span>
              {historyInsight?.specName && (
                <span className="flex-shrink-0 text-[10px] font-mono truncate max-w-[120px]" style={{ color: '#c0b8b0' }}>
                  {historyInsight.specName}
                </span>
              )}
              {!historyLoading && !historyInsight && historyMeta && (
                // Same fix as specs/page.tsx's StatusDot: "Running" means
                // ACTUALLY live right now (historyIsLive, from live-run-store),
                // never derived from the proposal status enum -- a finished
                // run that ended in needs_rework/etc. is done, not stuck.
                <span className="flex-shrink-0 text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded"
                  style={{ color: '#7a7068', backgroundColor: '#f0ece6' }}>
                  {historyIsLive ? 'Running' : 'Completed'}
                </span>
              )}
            </>
          ) : (
            <>
              {mode === 'running' && <Loader2 className="h-4 w-4 animate-spin text-blue-500" />}
              {mode === 'done' && success   && <CheckCircle className="h-4 w-4 text-green-600" />}
              {mode === 'done' && !success  && <XCircle className="h-4 w-4 text-red-500" />}
              {(mode === 'idle' || mode === 'folder-selected') && (
                panelMode === 'analytics'
                  ? <LineChart className="h-4 w-4" style={{ color: '#9c9088' }} />
                  : <FolderOpen className="h-4 w-4" style={{ color: '#9c9088' }} />
              )}
              <span className="text-sm font-semibold" style={{ color: '#1c1814' }}>
                {mode === 'idle' && (panelMode === 'analytics' ? 'Create Insight' : 'New Spec')}
                {mode === 'folder-selected' && specName}
                {mode === 'running' && (panelMode === 'analytics' ? `Analyzing ${specName}…` : `Running ${specName}…`)}
                {mode === 'done' && (success ? 'Done' : 'Failed')}
              </span>
            </>
          )}
        </div>
        <div className="flex items-center gap-2">
          {activeTraceUrl && (
            <a href={activeTraceUrl} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs font-medium hover:opacity-70"
              style={{ color: '#2563eb' }}>
              View trace <ExternalLink className="h-3 w-3" />
            </a>
          )}
          {(panelMode === 'new' || panelMode === 'analytics') && mode === 'done' && (
            <button onClick={reset} className="flex items-center gap-1 text-xs hover:opacity-70"
              style={{ color: '#7a7068' }}>
              <RotateCcw className="h-3 w-3" /> Run another
            </button>
          )}
          <button onClick={() => { reset(); close(); }}
            className="flex h-7 w-7 items-center justify-center rounded-lg hover:bg-stone-100 transition-colors"
            style={{ color: '#9c9088' }}>
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto">

        {/* HISTORY — how a past spec was ingested: reconstructed from
            schema_proposals/schema_reviews as the same generation widgets
            used live, no tool-call granularity (not persisted after a run
            ends) but the real revision-by-revision propose/review story. */}
        {panelMode === 'history' && (
          <div className="p-4">
            {historyLoading && (
              <p className="py-8 text-center text-xs" style={{ color: '#c0b8b0' }}>Loading…</p>
            )}
            {historyError && (
              <p className="py-8 text-center text-xs" style={{ color: '#dc2626' }}>{historyError}</p>
            )}
            {!historyLoading && !historyError && historyEvents.length === 0 && (
              <p className="py-8 text-center text-xs" style={{ color: '#c0b8b0' }}>
                {historyInsight
                  ? 'No persisted trace found for this insight.'
                  : 'No persisted trace for this spec — it may have been ingested before trace persistence was added. Re-run it to see the full reasoning + tool-call history here.'}
              </p>
            )}
            {!historyLoading && historyEvents.length > 0 && (
              <TraceViewer events={historyEvents} active={historyIsLive} />
            )}
          </div>
        )}

        {/* IDLE — prompt to pick a folder */}
        {panelMode === 'new' && mode === 'idle' && (
          <div className="flex h-full flex-col items-center justify-center gap-4 p-8 text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl"
              style={{ backgroundColor: '#f0ece6' }}>
              <FolderOpen className="h-7 w-7" style={{ color: '#9c9088' }} />
            </div>
            <div>
              <p className="text-sm font-medium" style={{ color: '#1c1814' }}>Select a spec folder</p>
              <p className="mt-1 text-xs" style={{ color: '#9c9088' }}>
                Pick a folder containing <code className="font-mono">spec.md</code> and <code className="font-mono">events.ndjson</code>
              </p>
            </div>
            <button
              onClick={() => folderRef.current?.click()}
              className="flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90"
              style={{ backgroundColor: '#2563eb' }}>
              <FolderOpen className="h-4 w-4" />
              Choose folder
            </button>
          </div>
        )}

        {/* ANALYTICS IDLE — either pick which fully-executed spec to run
            analytics against (gated the same way run_analytics_for_spec gates
            server-side: only specs whose latest proposal reached 'executed'),
            or ask a free-text question with no single table in mind
            (run_analytics_for_prompt -- the agent decides what's relevant
            itself via list_tables, see ANALYTICS_AGENT's custom_investigation
            branch). */}
        {panelMode === 'analytics' && mode === 'idle' && (
          <div className="p-5">
            <div className="mb-4 flex rounded-xl border p-1" style={{ borderColor: '#e5dfd6', backgroundColor: '#faf8f5' }}>
              {(['spec', 'custom'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setAnalyticsTab(tab)}
                  className="flex-1 rounded-lg py-1.5 text-xs font-semibold transition-colors"
                  style={analyticsTab === tab
                    ? { backgroundColor: '#ffffff', color: '#1c1814', boxShadow: '0 1px 2px rgba(0,0,0,0.06)' }
                    : { color: '#9c9088' }}>
                  {tab === 'spec' ? 'From a spec' : 'Custom question'}
                </button>
              ))}
            </div>

            {analyticsTab === 'spec' ? (
              <>
                <p className="mb-3 text-xs leading-relaxed" style={{ color: '#9c9088' }}>
                  Pick a spec whose schema has been fully executed. The analytics agent explores its
                  table live — via its own queries, not canned ones — and writes a PM-ready insight report.
                </p>
                {eligibleLoading && (
                  <p className="py-8 text-center text-xs" style={{ color: '#c0b8b0' }}>Loading eligible specs…</p>
                )}
                {!eligibleLoading && eligibleSpecs.length === 0 && (
                  <div className="flex flex-col items-center gap-3 py-10 text-center">
                    <LineChart className="h-7 w-7" style={{ color: '#c0b8b0' }} />
                    <p className="max-w-xs text-xs" style={{ color: '#9c9088' }}>
                      No fully-executed specs yet. Run a spec through ingestion until its schema is
                      <span className="font-semibold"> executed</span> before analytics can run on it.
                    </p>
                  </div>
                )}
                {!eligibleLoading && eligibleSpecs.length > 0 && (
                  <div className="rounded-xl border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
                    {eligibleSpecs.map(s => (
                      <button
                        key={s.spec_name}
                        onClick={() => { setSpecName(s.spec_name); setMode('folder-selected'); }}
                        className="w-full flex items-center justify-between gap-3 px-4 py-3 text-left hover:bg-stone-50 border-b last:border-0 transition-colors"
                        style={{ borderColor: '#f0ece6' }}>
                        <div className="min-w-0">
                          <p className="text-[13px] font-semibold font-mono truncate" style={{ color: '#1c1814' }}>{s.spec_name}</p>
                          <p className="text-[11px] font-mono truncate" style={{ color: '#9c9088' }}>{s.table_name || '—'}</p>
                        </div>
                        {s.has_insight > 0 && (
                          <span className="flex-shrink-0 text-[10px] font-semibold px-1.5 py-0.5 rounded"
                            style={{ color: '#16a34a', backgroundColor: '#f0fdf4' }}>
                            has insight
                          </span>
                        )}
                      </button>
                    ))}
                  </div>
                )}
              </>
            ) : (
              <>
                <p className="mb-3 text-xs leading-relaxed" style={{ color: '#9c9088' }}>
                  Ask anything — the agent explores whichever tables (new features, the original
                  funnel, or both) are actually relevant to your question, not just one spec's own
                  PM questions. E.g. "why did checkout conversion drop last week" or "compare Express
                  vs standard checkout across geos".
                </p>
                <textarea
                  value={customPrompt}
                  onChange={e => setCustomPrompt(e.target.value)}
                  placeholder="What do you want to know?"
                  rows={4}
                  className="w-full rounded-xl border p-3 text-sm resize-none focus:outline-none focus:ring-2"
                  style={{ borderColor: '#e5dfd6', color: '#1c1814' }}
                />
                <button
                  onClick={() => { if (customPrompt.trim()) { setSpecName(customPrompt.trim().slice(0, 60)); setMode('folder-selected'); } }}
                  disabled={!customPrompt.trim()}
                  className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl py-2.5 text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
                  style={{ backgroundColor: '#16a34a' }}>
                  Continue
                </button>
              </>
            )}
          </div>
        )}

        {/* FOLDER SELECTED — confirm + run (ingest) / confirm + run (analytics) */}
        {mode === 'folder-selected' && panelMode === 'analytics' && (
          <div className="space-y-4 p-5">
            <div className="rounded-xl border p-4" style={{ borderColor: '#e5dfd6', backgroundColor: '#faf8f5' }}>
              <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#9c9088' }}>
                {analyticsTab === 'custom' ? 'Question' : 'Spec'}
              </p>
              <p className="mt-1 text-sm font-semibold" style={{ color: '#1c1814' }}>
                {analyticsTab === 'custom'
                  ? <span className="font-normal">{customPrompt}</span>
                  : <span className="font-mono">{specName}</span>}
              </p>
            </div>

            <button
              onClick={() => setMode('idle')}
              className="w-full rounded-xl border py-2 text-xs transition-colors hover:bg-stone-50"
              style={{ borderColor: '#e5dfd6', color: '#7a7068' }}>
              {analyticsTab === 'custom' ? 'Edit question' : 'Choose a different spec'}
            </button>

            <button
              onClick={handleRunAnalytics}
              className="flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold text-white transition-opacity hover:opacity-90"
              style={{ backgroundColor: '#16a34a' }}>
              <Play className="h-4 w-4" />
              Run Analytics
            </button>
          </div>
        )}

        {mode === 'folder-selected' && panelMode !== 'analytics' && (
          <div className="space-y-4 p-5">
            <div className="rounded-xl border p-4 space-y-3" style={{ borderColor: '#e5dfd6', backgroundColor: '#faf8f5' }}>
              <div>
                <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#9c9088' }}>Spec name</p>
                <p className="mt-1 text-sm font-semibold font-mono" style={{ color: '#1c1814' }}>{specName}</p>
              </div>
              <div className="flex gap-4">
                <div className="flex-1">
                  <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#9c9088' }}>Spec file</p>
                  <p className="mt-1 text-xs truncate" style={{ color: specFile ? '#16a34a' : '#dc2626' }}>
                    {specFile ? `✓ ${specFile.name}` : '✗ spec.md not found'}
                  </p>
                </div>
                <div className="flex-1">
                  <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#9c9088' }}>Events file</p>
                  <p className="mt-1 text-xs truncate" style={{ color: eventsFile ? '#16a34a' : '#dc2626' }}>
                    {eventsFile ? `✓ ${eventsFile.name}` : '✗ events not found'}
                  </p>
                </div>
              </div>
            </div>

            <button
              onClick={() => folderRef.current?.click()}
              className="w-full rounded-xl border py-2 text-xs transition-colors hover:bg-stone-50"
              style={{ borderColor: '#e5dfd6', color: '#7a7068' }}>
              Change folder
            </button>

            <button
              onClick={handleRun}
              disabled={!specFile || !eventsFile}
              className="flex w-full items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold text-white transition-opacity disabled:opacity-40"
              style={{ backgroundColor: '#2563eb' }}>
              <Play className="h-4 w-4" />
              Run Pipeline
            </button>
          </div>
        )}

        {/* RUNNING — live agent trace: every reasoning step and tool call
            rendered through the same per-tool widgets as the trace viewer,
            as it happens (not a post-hoc replay) — driven directly by
            dashboard/emitter.py's live event stream, no Langfuse fetch. */}
        {mode === 'running' && (
          <div className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />
              <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#9c9088' }}>
                {panelMode === 'analytics' ? 'Analytics agent — live trace' : 'Live trace'}
              </p>
            </div>
            {traceEvents.length === 0 && visibleLogs.length === 0 ? (
              <p className="py-8 text-center text-xs" style={{ color: '#c0b8b0' }}>Initializing…</p>
            ) : (
              <>
                {traceEvents.length > 0 && <TraceViewer events={traceEvents} active />}
                {/* init/complete/error only -- these come from the subprocess
                    wrapper itself, not run.log(), so they're not trace_events. */}
                {visibleLogs.length > 0 && (
                  <div className="mt-3 rounded-xl border p-2.5" style={{ borderColor: '#e5dfd6', backgroundColor: '#faf8f5' }}>
                    {visibleLogs.map(l => <LogRow key={l.id} entry={l} />)}
                  </div>
                )}
                <div ref={traceEndRef} />
                <div ref={logsEndRef} />
              </>
            )}
          </div>
        )}

        {/* DONE */}
        {mode === 'done' && result && (
          <div className="p-5 space-y-4">
            {/* Status banner */}
            <div className="rounded-xl border p-4"
              style={{
                borderColor: success ? '#bbf7d0' : '#fecaca',
                backgroundColor: success ? '#f0fdf4' : '#fef2f2',
              }}>
              <p className="text-sm font-semibold" style={{ color: success ? '#15803d' : '#dc2626' }}>
                {panelMode === 'analytics'
                  ? (success ? '✓ Insight generated' : '✗ Analytics failed')
                  : (success ? '✓ Pipeline executed successfully' : `✗ Pipeline ${result.status}`)}
              </p>
              {panelMode === 'analytics' && success && result.title && (
                <p className="mt-1 text-xs font-medium leading-relaxed" style={{ color: '#1c1814' }}>{result.title}</p>
              )}
              {panelMode !== 'analytics' && result.table_name && (
                <p className="mt-1 text-xs font-mono" style={{ color: '#1c1814' }}>{result.table_name}</p>
              )}
              {(result.error || result.reason) && (
                <p className="mt-1.5 text-xs" style={{ color: '#7f1d1d' }}>{result.error ?? result.reason}</p>
              )}
              {panelMode === 'analytics' && success && result.insight_id && (
                <a href={`/insights/${result.insight_id}`} target="_blank" rel="noopener noreferrer"
                  className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold hover:opacity-70"
                  style={{ color: '#16a34a' }}>
                  View full report <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </div>

            {/* Full trace — every reasoning step and tool call from the run,
                same widgets as while it was live. */}
            {traceEvents.length > 0 && <TraceViewer events={traceEvents} />}

            {/* Plain init/error/complete log lines */}
            {visibleLogs.length > 0 && (
              <details className="rounded-xl border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
                <summary className="px-4 py-2.5 text-xs font-medium cursor-pointer hover:bg-stone-50"
                  style={{ color: '#4a4540' }}>
                  Run log ({visibleLogs.length} entries)
                </summary>
                <div className="px-3 py-2 max-h-60 overflow-y-auto" style={{ backgroundColor: '#faf8f5' }}>
                  {visibleLogs.map(l => <LogRow key={l.id} entry={l} />)}
                </div>
              </details>
            )}

            {success && panelMode === 'new' && (
              <p className="text-center text-xs" style={{ color: '#9c9088' }}>
                Navigating to spec detail…
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
