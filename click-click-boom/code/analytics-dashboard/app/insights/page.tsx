'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { GitBranch, Sparkles, TrendingUp, AlertCircle } from 'lucide-react';
import { openAnalyticsPanel, openInsightTrace } from '@/lib/panel-context';

// ── types ─────────────────────────────────────────────────────────────────────

interface Insight {
  insight_id: string;
  spec_name: string; // '' for a custom/broad-prompt investigation — see `prompt`
  title: string;
  summary: string;
  confidence: number;
  evidence: string;
  related_known_issues: string[];
  segment_cuts: string[];
  has_report: boolean;
  created_at: string;
  trace_url: string | null;
  prompt: string;
}

// ── confidence badge ─────────────────────────────────────────────────────────
// Same three-tier color convention as everywhere else confidence shows up
// (specs list's ConfidenceCell, agent-panel's insight/proposal widgets).

function ConfidenceBadge({ score }: { score: number }) {
  const pct   = Math.round(score * 100);
  const color = pct >= 80 ? '#16a34a' : pct >= 60 ? '#d97706' : '#dc2626';
  const bg    = pct >= 80 ? '#f0fdf4' : pct >= 60 ? '#fffbeb' : '#fef2f2';
  return (
    <span className="flex-shrink-0 text-[12px] font-bold tabular-nums font-mono rounded-lg px-2 py-1"
      style={{ color, backgroundColor: bg }}>
      {pct}%
    </span>
  );
}

// ── row ───────────────────────────────────────────────────────────────────────
// One row = one insight. The full row opens the standalone report (the real
// content — see analytics/analytics_agent.py's Stage 5); the trace icon is a
// separate, smaller action that opens the SAME right panel used for live
// runs, showing this insight's own persisted tool-call trace
// (/api/insights/[id]/events) — a spec can have several insights now that
// analytics is an explicit, re-runnable step, so this is scoped to exactly
// the one the user clicked, not "this spec's latest trace."

function InsightRow({ ins }: { ins: Insight }) {
  const body = (
    <>
      <ConfidenceBadge score={ins.confidence} />

      <div className="min-w-0">
        <p className="text-[13.5px] font-semibold leading-snug truncate" style={{ color: '#1c1814' }}>
          {ins.title}
        </p>
        <p className="mt-0.5 text-[12px] leading-snug line-clamp-1" style={{ color: '#9c9088' }}>
          {ins.summary}
        </p>
      </div>

      {ins.spec_name ? (
        <span className="hidden sm:block flex-shrink-0 text-[11px] font-mono truncate max-w-[140px]" style={{ color: '#9c9088' }}>
          {ins.spec_name}
        </span>
      ) : (
        <span className="hidden sm:flex flex-shrink-0 items-center gap-1 text-[11px] truncate max-w-[160px]"
          title={ins.prompt} style={{ color: '#9c9088' }}>
          <span className="flex-shrink-0 text-[9.5px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded"
            style={{ color: '#7c3aed', backgroundColor: '#7c3aed15' }}>
            custom
          </span>
          <span className="truncate">{ins.prompt}</span>
        </span>
      )}

      <span className="hidden md:block flex-shrink-0 text-[11px] font-mono tabular-nums" style={{ color: '#c0b8b0' }}>
        {ins.created_at.slice(5, 16).replace('T', ' ')}
      </span>
    </>
  );

  return (
    <div className="flex items-center gap-4 px-4 py-3 border-b last:border-0 transition-colors hover:bg-stone-50"
      style={{ borderColor: '#f0ece6' }}>
      {ins.has_report ? (
        <Link href={`/insights/${ins.insight_id}`} className="flex-1 min-w-0 flex items-center gap-4">
          {body}
        </Link>
      ) : (
        <div className="flex-1 min-w-0 flex items-center gap-4">{body}</div>
      )}

      <button
        onClick={() => openInsightTrace({ insightId: ins.insight_id, title: ins.title, specName: ins.spec_name })}
        title="View the tool-call trace behind this insight"
        className="flex-shrink-0 flex h-7 w-7 items-center justify-center rounded-lg hover:bg-stone-200 transition-colors"
        style={{ color: '#9c9088' }}>
        <GitBranch className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function InsightsPage() {
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const refetch = () => {
    fetch('/api/insights')
      .then(r => r.json())
      .then(d => setInsights(Array.isArray(d) ? d : []))
      .catch(() => setError(true))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    refetch();
    // agent-panel.tsx fires this after a successful analytics run
    window.addEventListener('insights-updated', refetch);
    return () => window.removeEventListener('insights-updated', refetch);
  }, []);

  return (
    <div className="flex h-full flex-col" style={{ backgroundColor: '#faf8f5' }}>
      {/* Header */}
      <div className="flex items-center justify-between border-b px-8 py-5"
        style={{ borderColor: '#e5dfd6', backgroundColor: '#ffffff' }}>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: '#1c1814' }}>Insights</h1>
          <p className="mt-0.5 text-sm" style={{ color: '#9c9088' }}>
            PM-ready findings generated by the analytics agent for fully-executed specs.
          </p>
        </div>
        <button
          onClick={() => openAnalyticsPanel()}
          className="flex flex-shrink-0 items-center gap-2 rounded-lg px-3.5 py-2 text-[13px] font-semibold text-white transition-opacity hover:opacity-90"
          style={{ backgroundColor: '#16a34a' }}>
          <Sparkles className="h-4 w-4" />
          Create Insight
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {loading && (
          <div className="flex h-40 items-center justify-center">
            <p className="text-sm" style={{ color: '#9c9088' }}>Loading…</p>
          </div>
        )}

        {error && (
          <div className="flex items-center gap-2 rounded-xl p-4" style={{ backgroundColor: '#fef2f2' }}>
            <AlertCircle className="h-4 w-4 text-red-500 flex-shrink-0" />
            <p className="text-sm" style={{ color: '#dc2626' }}>Failed to load insights — check ClickHouse connection.</p>
          </div>
        )}

        {!loading && !error && insights.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center text-center">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl mb-5"
              style={{ backgroundColor: '#f0ece6' }}>
              <TrendingUp className="h-7 w-7" style={{ color: '#9c9088' }} />
            </div>
            <h2 className="text-base font-semibold" style={{ color: '#1c1814' }}>No insights yet</h2>
            <p className="mt-1.5 max-w-xs text-sm" style={{ color: '#9c9088' }}>
              Click <strong>Create Insight</strong> and pick a spec whose schema has been
              fully executed — the analytics agent explores it live and writes the report.
            </p>
            <button
              onClick={() => openAnalyticsPanel()}
              className="mt-6 flex items-center gap-2 rounded-xl px-5 py-2.5 text-sm font-semibold text-white hover:opacity-90"
              style={{ backgroundColor: '#16a34a' }}>
              <Sparkles className="h-4 w-4" /> Create Insight
            </button>
          </div>
        )}

        {!loading && !error && insights.length > 0 && (
          <div className="rounded-xl border overflow-hidden" style={{ borderColor: '#e5dfd6', backgroundColor: '#ffffff' }}>
            {insights.map(ins => <InsightRow key={ins.insight_id} ins={ins} />)}
          </div>
        )}
      </div>
    </div>
  );
}
