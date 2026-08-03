'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, ExternalLink, ChevronDown, ChevronRight, Plus, CheckCircle, XCircle, AlertCircle, Clock } from 'lucide-react';
import { openAgentPanel } from '@/lib/panel-context';

// ── types ─────────────────────────────────────────────────────────────────────

interface Proposal {
  proposal_id: string;
  revision: number;
  status: string;
  confidence: number;
  table_name: string;
  ordering_key: string;
  rationale: string;
  perf_report: string;
  ddl: string;
  trace_url: string;
  last_updated: string;
}

interface Review {
  review_id: string;
  proposal_id: string;
  verdict: string;
  findings: string;
  reviewer_confidence: number;
  trace_url: string;
  ts: string;
}

interface Insight {
  insight_id: string;
  title: string;
  summary: string;
  confidence: number;
  has_report: number;
  trace_url: string;
  ts: string;
}

// ── helpers ───────────────────────────────────────────────────────────────────

const STATUS_COLOR: Record<string, string> = {
  executed:       '#16a34a',
  approved:       '#2563eb',
  pending_review: '#d97706',
  needs_rework:   '#ea580c',
  rejected:       '#dc2626',
  drafted:        '#9c9088',
};

const VERDICT_COLOR: Record<string, string> = {
  approve:          '#16a34a',
  request_changes:  '#d97706',
  block:            '#dc2626',
};

function Badge({ label, color }: { label: string; color: string }) {
  return (
    <span className="rounded-full px-2.5 py-0.5 text-[11px] font-semibold"
      style={{ color, backgroundColor: color + '18' }}>
      {label}
    </span>
  );
}

// ── proposal card ─────────────────────────────────────────────────────────────

function ProposalCard({ proposal, reviews }: { proposal: Proposal; reviews: Review[] }) {
  const [open, setOpen] = useState(proposal.status === 'executed');
  const [ddlOpen, setDdlOpen] = useState(false);
  const myReviews = reviews.filter(r => r.proposal_id === proposal.proposal_id);
  const color = STATUS_COLOR[proposal.status] ?? '#9c9088';

  return (
    <div className="rounded-2xl border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
      {/* Card header */}
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-3 px-5 py-3.5 text-left hover:bg-stone-50 transition-colors"
        style={{ backgroundColor: open ? '#faf8f5' : '#ffffff' }}>
        <span className="h-2 w-2 rounded-full flex-shrink-0" style={{ backgroundColor: color }} />
        <span className="text-sm font-semibold font-mono" style={{ color: '#1c1814' }}>
          revision {proposal.revision}
        </span>
        <Badge label={proposal.status} color={color} />
        {proposal.confidence > 0 && (
          <span className="text-xs font-mono" style={{ color: '#9c9088' }}>
            {Math.round(proposal.confidence * 100)}% confidence
          </span>
        )}
        <span className="ml-auto flex-shrink-0 flex items-center gap-1 text-[11px]" style={{ color: '#c0b8b0' }}>
          <Clock className="h-3 w-3" />
          {proposal.last_updated}
        </span>
        {open ? <ChevronDown className="h-4 w-4 flex-shrink-0" style={{ color: '#c0b8b0' }} />
               : <ChevronRight className="h-4 w-4 flex-shrink-0" style={{ color: '#c0b8b0' }} />}
      </button>

      {/* Expanded body */}
      {open && (
        <div className="border-t px-5 py-4 space-y-4" style={{ borderColor: '#f0ece6', backgroundColor: '#faf8f5' }}>
          {/* Table + ordering key */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: '#9c9088' }}>Table</p>
              <p className="text-xs font-mono font-medium" style={{ color: '#1c1814' }}>{proposal.table_name || '—'}</p>
            </div>
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: '#9c9088' }}>Ordering key</p>
              <p className="text-xs font-mono" style={{ color: '#4a4540' }}>{proposal.ordering_key || '—'}</p>
            </div>
          </div>

          {/* Rationale */}
          {proposal.rationale && (
            <div>
              <p className="text-[10px] font-bold uppercase tracking-wider mb-1" style={{ color: '#9c9088' }}>Rationale</p>
              <p className="text-xs leading-relaxed" style={{ color: '#4a4540' }}>{proposal.rationale}</p>
            </div>
          )}

          {/* DDL collapsible */}
          {proposal.ddl && (
            <div className="rounded-xl border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
              <button
                onClick={() => setDdlOpen(v => !v)}
                className="flex w-full items-center justify-between px-3.5 py-2.5 text-left hover:bg-white transition-colors"
                style={{ backgroundColor: '#faf8f5' }}>
                <span className="text-xs font-semibold" style={{ color: '#4a4540' }}>Generated DDL</span>
                {ddlOpen ? <ChevronDown className="h-3.5 w-3.5" style={{ color: '#9c9088' }} />
                          : <ChevronRight className="h-3.5 w-3.5" style={{ color: '#9c9088' }} />}
              </button>
              {ddlOpen && (
                <pre className="overflow-x-auto p-3.5 text-xs font-mono leading-relaxed border-t"
                  style={{ borderColor: '#e5dfd6', backgroundColor: '#0f0e0c', color: '#e8e4df', maxHeight: '280px', overflowY: 'auto' }}>
                  {proposal.ddl}
                </pre>
              )}
            </div>
          )}

          {/* Reviews */}
          {myReviews.length > 0 && (
            <div className="space-y-2">
              <p className="text-[10px] font-bold uppercase tracking-wider" style={{ color: '#9c9088' }}>
                Reviews ({myReviews.length})
              </p>
              {myReviews.map(rev => {
                const vc = VERDICT_COLOR[rev.verdict] ?? '#9c9088';
                let findings: Array<{ severity: string; category: string; description: string }> = [];
                try { findings = JSON.parse(rev.findings); } catch {}
                return (
                  <div key={rev.review_id} className="rounded-xl border p-3 space-y-2"
                    style={{ borderColor: vc + '40', backgroundColor: vc + '08' }}>
                    <div className="flex items-center gap-2">
                      <Badge label={rev.verdict} color={vc} />
                      <span className="text-[10px]" style={{ color: '#9c9088' }}>{rev.ts}</span>
                      {rev.trace_url && (
                        <a href={rev.trace_url} target="_blank" rel="noopener noreferrer"
                          className="ml-auto flex items-center gap-1 text-[10px] hover:opacity-70"
                          style={{ color: '#2563eb' }}>
                          trace <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      )}
                    </div>
                    {findings.map((f, i) => (
                      <div key={i} className="text-xs" style={{ color: '#4a4540' }}>
                        <span className="font-semibold"
                          style={{ color: f.severity === 'block' ? '#dc2626' : f.severity === 'warn' ? '#d97706' : '#9c9088' }}>
                          [{f.severity}] {f.category}
                        </span>
                        {' — '}{f.description}
                      </div>
                    ))}
                  </div>
                );
              })}
            </div>
          )}

          {/* Trace link */}
          {proposal.trace_url && (
            <a href={proposal.trace_url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1.5 text-xs font-medium hover:opacity-70"
              style={{ color: '#2563eb' }}>
              <ExternalLink className="h-3.5 w-3.5" />
              View Langfuse trace
            </a>
          )}
        </div>
      )}
    </div>
  );
}

// ── insight card ──────────────────────────────────────────────────────────────

function InsightCard({ insight, specName }: { insight: Insight; specName: string }) {
  const pct   = Math.round(insight.confidence * 100);
  const color = pct >= 80 ? '#16a34a' : pct >= 60 ? '#d97706' : '#dc2626';
  return (
    <div className="rounded-2xl border p-5 space-y-3"
      style={{ borderColor: '#bbf7d0', backgroundColor: '#f0fdf4' }}>
      <div className="flex items-start justify-between gap-3">
        <h3 className="text-sm font-semibold leading-snug flex-1" style={{ color: '#15803d' }}>
          {insight.title}
        </h3>
        <span className="flex-shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold"
          style={{ color, backgroundColor: color + '18' }}>
          {pct}%
        </span>
      </div>
      <p className="text-xs leading-relaxed" style={{ color: '#166534' }}>{insight.summary}</p>
      <div className="flex items-center justify-between">
        <span className="text-[10px]" style={{ color: '#86efac' }}>{insight.ts}</span>
        <div className="flex items-center gap-3">
          {insight.has_report > 0 && (
            <a href={`/insights/${insight.insight_id}`} target="_blank" rel="noopener noreferrer"
              className="text-xs font-medium hover:opacity-70" style={{ color: '#16a34a' }}>
              View full report →
            </a>
          )}
          {insight.trace_url && (
            <a href={insight.trace_url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 text-[11px] hover:opacity-70" style={{ color: '#2563eb' }}>
              <ExternalLink className="h-3 w-3" /> Trace
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function SpecDetailPage() {
  const params = useParams();
  const router = useRouter();
  const specName = params.name as string;

  const [data, setData]     = useState<{ proposals: Proposal[]; reviews: Review[]; insight: Insight | null } | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`/api/specs/${specName}/runs`)
      .then(r => r.json())
      .then(d => setData(d))
      .catch(() => setData({ proposals: [], reviews: [], insight: null }))
      .finally(() => setLoading(false));
  }, [specName]);

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center gap-3 border-b px-8 py-5"
        style={{ borderColor: '#e5dfd6' }}>
        <button onClick={() => router.push('/specs')}
          className="flex items-center gap-1.5 text-sm hover:opacity-70 transition-opacity"
          style={{ color: '#9c9088' }}>
          <ArrowLeft className="h-4 w-4" /> Specs
        </button>
        <span style={{ color: '#e5dfd6' }}>/</span>
        <h1 className="text-lg font-semibold font-mono" style={{ color: '#1c1814' }}>{specName}</h1>
        <button
          onClick={openAgentPanel}
          className="ml-auto flex items-center gap-1.5 rounded-xl border px-3.5 py-2 text-xs font-semibold hover:bg-stone-50 transition-colors"
          style={{ borderColor: '#e5dfd6', color: '#4a4540' }}>
          <Plus className="h-3.5 w-3.5" /> Run again
        </button>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-8 py-8">
        {loading && (
          <p className="text-sm" style={{ color: '#9c9088' }}>Loading…</p>
        )}

        {!loading && data && (
          <div className="max-w-2xl space-y-6">
            {/* Insight */}
            {data.insight && <InsightCard insight={data.insight} specName={specName} />}

            {/* Run history */}
            <div>
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-semibold" style={{ color: '#1c1814' }}>
                  Run history
                  <span className="ml-2 text-xs font-normal" style={{ color: '#9c9088' }}>
                    {data.proposals.length} proposal{data.proposals.length !== 1 ? 's' : ''}
                  </span>
                </h2>
              </div>

              {data.proposals.length === 0 ? (
                <p className="text-sm" style={{ color: '#9c9088' }}>No proposals yet.</p>
              ) : (
                <div className="space-y-3">
                  {data.proposals.map(p => (
                    <ProposalCard key={p.proposal_id} proposal={p} reviews={data.reviews} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
