'use client';

import { useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { openAgentPanel, openSpecHistory } from '@/lib/panel-context';
import type { SpecSummary } from '../api/specs/route';

// "Running" is real-time truth, not a status enum -- exactly one thing: this
// spec is the one live-run-store currently has active (see
// lib/live-run-store.ts). Once NOT live, though, schema_proposals'
// latest_status still tells a real, settled story worth surfacing:
// 'executed' actually landed a table; anything else (needs_rework/rejected/
// stuck mid-approval) means the run finished without ever landing one --
// whether because it hit MAX_REVISIONS and gave up (see
// orchestrator/pipeline.py's at_cap + test_harness_failed path) or was
// rejected outright. Collapsing that into a generic "Completed" reads as
// success when it wasn't one.
function StatusDot({ isLive, latestStatus }: { isLive: boolean; latestStatus: string }) {
  if (isLive) {
    return (
      <span className="flex items-center gap-1.5 min-w-0">
        <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ backgroundColor: '#2563eb' }} />
        <span className="text-[11px] font-medium truncate" style={{ color: '#4a4540' }}>Running</span>
      </span>
    );
  }
  const executed = latestStatus === 'executed';
  return (
    <span className="flex items-center gap-1.5 min-w-0">
      <span className="h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ backgroundColor: executed ? '#16a34a' : '#dc2626' }} />
      <span className="text-[11px] font-medium truncate" style={{ color: '#4a4540' }}>
        {executed ? 'Completed' : 'Failed'}
      </span>
    </span>
  );
}

// A proposal's confidence is self-reported by the proposer on its most
// recent revision -- while the run is genuinely still going, that number can
// still change, so hide it. But a FINISHED run (whether it reached executed
// or gave up after MAX_REVISIONS) has a real, settled last-known confidence
// worth showing either way -- gating this on the status enum instead of
// actual liveness hid it forever for any run that ended in needs_rework.
function ConfidenceCell({ isLive, value }: { isLive: boolean; value: number }) {
  if (isLive) return <span className="text-[11px] italic" style={{ color: '#c0b8b0' }}>in progress</span>;
  if (!value) return <span style={{ color: '#c0b8b0' }}>—</span>;
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? '#16a34a' : pct >= 60 ? '#d97706' : '#dc2626';
  return (
    <div className="flex items-center gap-2">
      <div className="h-1 w-10 flex-shrink-0 rounded-full overflow-hidden" style={{ backgroundColor: '#f0ece6' }}>
        <div className="h-full rounded-full" style={{ width: `${pct}%`, backgroundColor: color }} />
      </div>
      <span className="text-[11px] font-mono tabular-nums" style={{ color: '#7a7068' }}>{pct}%</span>
    </div>
  );
}

// Column layout shared between header and body rows so everything lines up —
// status is a fixed-width dot+label, name/table share the flexible middle,
// confidence/time are fixed-width and right-leaning (scannable, like a file
// manager or job queue, not a card grid).
const GRID_COLS = '96px minmax(0,1.3fr) minmax(0,1fr) 84px 92px';

function SpecRow({ spec, isLive }: { spec: SpecSummary; isLive: boolean }) {
  return (
    <button
      onClick={() => openSpecHistory(spec.spec_name)}
      className="w-full grid items-center gap-4 px-4 py-2.5 text-left transition-colors hover:bg-stone-50 border-b last:border-0"
      style={{ gridTemplateColumns: GRID_COLS, borderColor: '#f0ece6' }}
    >
      <StatusDot isLive={isLive} latestStatus={spec.latest_status} />

      <span className="text-[13px] font-semibold font-mono truncate" style={{ color: '#1c1814' }}>
        {spec.spec_name}
      </span>

      <span className="text-[12px] font-mono truncate" style={{ color: '#9c9088' }}>
        {spec.table_name || '—'}
      </span>

      <ConfidenceCell isLive={isLive} value={spec.latest_confidence} />

      <span className="text-[11px] font-mono tabular-nums text-right" style={{ color: '#c0b8b0' }}>
        {spec.last_run.slice(5, 16).replace('T', ' ')}
      </span>
    </button>
  );
}

export default function SpecsPage() {
  const [specs,   setSpecs]   = useState<SpecSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [liveSpecNames, setLiveSpecNames] = useState<Set<string>>(new Set());

  const refetch = () => {
    fetch('/api/specs')
      .then(r => r.json())
      .then(d => setSpecs(Array.isArray(d) ? d : []))
      .catch(() => setSpecs([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refetch();
    // agent-panel.tsx fires this after a successful new-spec run
    window.addEventListener('specs-updated', refetch);
    return () => window.removeEventListener('specs-updated', refetch);
  }, []);

  // If any INGESTION is still running (e.g. this tab got reloaded mid-run),
  // reopen the panel automatically -- it reattaches to the live trace itself
  // via lib/live-run-store.ts on mount. Also poll for which specs (plural --
  // several ingestions can be genuinely active at once now, each tracked by
  // its own runId, see lib/live-run-store.ts) are ACTUALLY live right now, so
  // each row's status reflects real-time truth instead of a frozen status
  // enum (see StatusDot's comment) -- stops polling once nothing is active.
  //
  // Scoped to kind='ingest' specifically -- an active analytics run
  // (/api/analytics) is a different kind of run entirely and must never mark
  // a spec's row "Running" here (that page auto-opening the ingest panel for
  // a pipeline that was never running was a real bug this scoping fixed).
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    const poll = () => {
      fetch('/api/live-run?kind=ingest').then(r => r.json()).then((d: { runs: { label: string }[] }) => {
        setLiveSpecNames(new Set(d.runs.map(r => r.label)));
        if (d.runs.length === 0 && timer) { clearInterval(timer); timer = null; }
      }).catch(() => {});
    };
    fetch('/api/live-run?kind=ingest').then(r => r.json()).then((d: { runs: { label: string }[] }) => {
      if (d.runs.length > 0) {
        openAgentPanel();
        setLiveSpecNames(new Set(d.runs.map(r => r.label)));
        timer = setInterval(poll, 3000);
      }
    }).catch(() => {});
    return () => { if (timer) clearInterval(timer); };
  }, []);

  return (
    <div className="flex h-full flex-col" style={{ backgroundColor: '#faf8f5' }}>
      {/* Header */}
      <div className="flex items-center justify-between border-b px-8 py-5"
        style={{ borderColor: '#e5dfd6', backgroundColor: '#ffffff' }}>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: '#1c1814' }}>Specs</h1>
          <p className="mt-0.5 text-sm" style={{ color: '#9c9088' }}>
            Feature specs that have been instrumented through the pipeline.
          </p>
        </div>
        <button
          onClick={openAgentPanel}
          className="flex items-center gap-2 rounded-lg px-3.5 py-2 text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
          style={{ backgroundColor: '#2563eb' }}>
          <Plus className="h-4 w-4" />
          New Spec
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {loading && (
          <div className="flex h-40 items-center justify-center">
            <p className="text-sm" style={{ color: '#9c9088' }}>Loading specs…</p>
          </div>
        )}

        {!loading && specs.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl mb-5"
              style={{ backgroundColor: '#f0ece6' }}>
              <Plus className="h-7 w-7" style={{ color: '#9c9088' }} />
            </div>
            <h2 className="text-base font-semibold" style={{ color: '#1c1814' }}>No specs yet</h2>
            <p className="mt-1.5 max-w-xs text-sm" style={{ color: '#9c9088' }}>
              Click <strong>New Spec</strong> and select a folder containing <code className="font-mono">spec.md</code> and <code className="font-mono">events.ndjson</code>.
            </p>
            <button
              onClick={openAgentPanel}
              className="mt-6 flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white hover:opacity-90"
              style={{ backgroundColor: '#2563eb' }}>
              <Plus className="h-4 w-4" /> New Spec
            </button>
          </div>
        )}

        {!loading && specs.length > 0 && (
          <div className="rounded-xl border overflow-hidden" style={{ borderColor: '#e5dfd6', backgroundColor: '#ffffff' }}>
            {/* Column headers */}
            <div className="grid items-center gap-4 px-4 py-2 border-b"
              style={{ gridTemplateColumns: GRID_COLS, borderColor: '#e5dfd6', backgroundColor: '#faf8f5' }}>
              {['Status', 'Spec', 'Table', 'Conf.', 'Last run'].map((h, i) => (
                <span key={h}
                  className={`text-[9.5px] font-bold uppercase tracking-widest ${i === 4 ? 'text-right' : ''}`}
                  style={{ color: '#9c9088' }}>
                  {h}
                </span>
              ))}
            </div>
            {specs.map(s => <SpecRow key={s.spec_name} spec={s} isLive={liveSpecNames.has(s.spec_name)} />)}
          </div>
        )}
      </div>
    </div>
  );
}
