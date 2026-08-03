'use client';
import { useState } from 'react';
import { BaseWidget } from '../BaseWidget';
import { highlightSQL, truncate } from '../utils';
import type { AgentEvent } from '../types';

// The proposer's and reviewer's full structured output is exactly what a
// reader needs to see clearly between these two agents -- generic JSON-dump
// treatment (GenerationWidget) buries it behind a collapsed toggle. These
// parse agent_runner/schemas.py's real shapes (INSTRUMENTATION_PROPOSER_SCHEMA
// / CONTEXT_REVIEWER_SCHEMA) into real structure: DDL as a code block,
// candidates/findings as their own cards, not a wall of raw text.

function parseOutput(output: unknown): Record<string, any> | null {
  if (output && typeof output === 'object') return output as Record<string, any>;
  if (typeof output === 'string') {
    try { return JSON.parse(output); } catch { return null; }
  }
  return null;
}

function ConfidenceBadge({ value }: { value?: number }) {
  if (value == null) return null;
  const pct = Math.round(value * 100);
  const color = pct >= 80 ? '#16a34a' : pct >= 60 ? '#d97706' : '#dc2626';
  return (
    <span className="text-[11px] font-mono font-semibold tabular-nums px-1.5 py-0.5 rounded"
      style={{ color, backgroundColor: color + '15' }}>
      {pct}% confidence
    </span>
  );
}

function Prose({ label, text, accent }: { label: string; text: string; accent: string }) {
  if (!text) return null;
  return (
    <div className="rounded-lg px-3 py-2.5 text-sm leading-relaxed"
      style={{ backgroundColor: accent + '10', color: accent, border: `1px solid ${accent}30` }}>
      <span className="text-[9px] font-bold uppercase tracking-widest block mb-1" style={{ opacity: 0.85 }}>
        {label}
      </span>
      <span style={{ opacity: 0.9 }}>{text}</span>
    </div>
  );
}

function CodeBlock({ code, lang }: { code: string; lang?: 'sql' }) {
  const [open, setOpen] = useState(true);
  const lines = code.split('\n');
  const long = lines.length > 6;
  const shown = open ? code : lines.slice(0, 6).join('\n') + (long ? '\n…' : '');
  return (
    <div>
      <pre className="text-[11px] p-3 rounded-lg overflow-x-auto font-mono leading-relaxed"
        style={{ backgroundColor: '#0f0e0c', color: '#e8e4df', border: '1px solid #2d2a20' }}
        dangerouslySetInnerHTML={lang === 'sql' ? { __html: highlightSQL(shown) } : undefined}>
        {lang === 'sql' ? undefined : shown}
      </pre>
      {long && (
        <button onClick={() => setOpen(v => !v)}
          className="text-[10px] mt-1 hover:opacity-70" style={{ color: '#9c9088' }}>
          {open ? 'collapse ▲' : `show all ${lines.length} lines ▼`}
        </button>
      )}
    </div>
  );
}

// ── Proposal ──────────────────────────────────────────────────────────────────

export function ProposalWidget({ event }: { event: AgentEvent }) {
  const parsed = parseOutput(event.output);
  if (!parsed) return <FallbackRaw event={event} family="proposal" title="proposal" />;

  const {
    table_name, columns_ddl, ordering_key_candidates = [], column_mapping = [],
    materialized_views = [], confidence, rationale,
  } = parsed;

  return (
    <BaseWidget
      family="proposal"
      title={table_name || 'proposal'}
      meta={undefined}
      defaultOpen
      collapsedPreview={<span className="italic">{truncate(rationale ?? '', 60)}</span>}
    >
      <div className="p-3.5 space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          {table_name && (
            <span className="text-[12px] font-mono font-semibold px-2 py-0.5 rounded" style={{ color: '#1c1814', backgroundColor: '#f0ece6' }}>
              {table_name}
            </span>
          )}
          <ConfidenceBadge value={confidence} />
        </div>

        {rationale && <Prose label="proposer's rationale" text={rationale} accent="#d97706" />}

        {columns_ddl && (
          <div>
            <span className="text-[9.5px] font-bold uppercase tracking-widest block mb-1" style={{ color: '#9c9088' }}>
              columns DDL
            </span>
            <CodeBlock code={columns_ddl} lang="sql" />
          </div>
        )}

        {ordering_key_candidates.length > 0 && (
          <div>
            <span className="text-[9.5px] font-bold uppercase tracking-widest block mb-1" style={{ color: '#9c9088' }}>
              ordering key candidates ({ordering_key_candidates.length})
            </span>
            <div className="space-y-1.5">
              {ordering_key_candidates.map((c: any, i: number) => (
                <div key={i} className="rounded-lg border p-2.5 text-[11.5px]" style={{ borderColor: '#e5dfd6', backgroundColor: '#faf8f5' }}>
                  <div className="font-semibold" style={{ color: '#1c1814' }}>{c.label}</div>
                  <div className="font-mono mt-0.5" style={{ color: '#7a7068' }}>
                    ORDER BY {c.ordering_key} {c.partition_key && <>· PARTITION BY {c.partition_key}</>}
                  </div>
                  {c.rationale && <div className="mt-1" style={{ color: '#9c9088' }}>{c.rationale}</div>}
                </div>
              ))}
            </div>
          </div>
        )}

        {materialized_views.length > 0 && (
          <div>
            <span className="text-[9.5px] font-bold uppercase tracking-widest block mb-1" style={{ color: '#9c9088' }}>
              materialized views ({materialized_views.length})
            </span>
            <div className="space-y-2">
              {materialized_views.map((mv: any, i: number) => (
                <div key={i} className="rounded-lg border p-2.5" style={{ borderColor: '#e5dfd6', backgroundColor: '#faf8f5' }}>
                  <div className="text-[11.5px] font-mono font-semibold mb-1" style={{ color: '#1c1814' }}>{mv.name}</div>
                  {mv.ddl && <CodeBlock code={mv.ddl} lang="sql" />}
                </div>
              ))}
            </div>
          </div>
        )}

        {column_mapping.length > 0 && (
          <div>
            <span className="text-[9.5px] font-bold uppercase tracking-widest block mb-1" style={{ color: '#9c9088' }}>
              column mapping ({column_mapping.length})
            </span>
            <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
              <table className="text-[11px] w-full">
                <tbody>
                  {column_mapping.map((m: any, i: number) => (
                    <tr key={i} className="border-b last:border-0" style={{ borderColor: '#f0ece6' }}>
                      <td className="px-2.5 py-1 font-mono" style={{ color: '#9c9088' }}>{m.raw_field}</td>
                      <td className="px-2.5 py-1 font-mono" style={{ color: '#1c1814' }}>→ {m.column_name}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </BaseWidget>
  );
}

// ── Review ────────────────────────────────────────────────────────────────────

const VERDICT_META: Record<string, { label: string; color: string }> = {
  approve:         { label: 'Approved',        color: '#16a34a' },
  request_changes: { label: 'Changes Requested', color: '#d97706' },
  block:           { label: 'Blocked',         color: '#dc2626' },
};

const SEVERITY_META: Record<string, { color: string }> = {
  block: { color: '#dc2626' }, warn: { color: '#d97706' }, info: { color: '#2563eb' },
};

export function ReviewWidget({ event }: { event: AgentEvent }) {
  const parsed = parseOutput(event.output);
  if (!parsed) return <FallbackRaw event={event} family="review" title="review" />;

  const { verdict, findings = [], reviewer_confidence } = parsed;
  const vm = VERDICT_META[verdict] ?? { label: verdict ?? 'unknown', color: '#6b7280' };

  return (
    <BaseWidget
      family="review"
      title={vm.label}
      meta={undefined}
      defaultOpen
      collapsedPreview={<span className="italic">{findings.length} finding{findings.length !== 1 ? 's' : ''}</span>}
    >
      <div className="p-3.5 space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[11.5px] font-bold px-2 py-0.5 rounded" style={{ color: vm.color, backgroundColor: vm.color + '15' }}>
            {vm.label}
          </span>
          <ConfidenceBadge value={reviewer_confidence} />
        </div>

        {findings.length === 0 ? (
          <p className="text-[11.5px]" style={{ color: '#9c9088' }}>No findings.</p>
        ) : (
          <div className="space-y-1.5">
            {findings.map((f: any, i: number) => {
              const sm = SEVERITY_META[f.severity] ?? { color: '#6b7280' };
              return (
                <div key={i} className="rounded-lg border p-2.5" style={{ borderColor: sm.color + '35', backgroundColor: sm.color + '08' }}>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[9.5px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded"
                      style={{ color: sm.color, backgroundColor: sm.color + '18' }}>
                      {f.severity}
                    </span>
                    {f.category && <span className="text-[10.5px] font-mono" style={{ color: '#9c9088' }}>{f.category}</span>}
                  </div>
                  {f.description && <p className="text-[11.5px] leading-relaxed" style={{ color: '#1c1814' }}>{f.description}</p>}
                  {f.suggested_fix && (
                    <p className="text-[11px] leading-relaxed mt-1" style={{ color: '#7a7068' }}>
                      <span className="font-semibold">fix: </span>{f.suggested_fix}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </BaseWidget>
  );
}

// ── Insight (analytics agent's final output) ─────────────────────────────────
// Same "real structure, not a JSON dump" treatment as Proposal/Review, for
// analytics_agent's output (title/summary/confidence/segment_cuts/
// related_known_issues/report_html — see analytics/analytics_agent.py).
// report_html itself is the self-contained report already viewable on the
// Insights page once persisted — shown here as a length/availability note,
// not inlined (it can be tens of KB of markup, wrong fit for a trace widget).

export function InsightWidget({ event }: { event: AgentEvent }) {
  const parsed = parseOutput(event.output);
  if (!parsed) return <FallbackRaw event={event} family="insight" title="insight" />;

  const {
    title, summary, confidence, segment_cuts = [], related_known_issues = [], report_html,
  } = parsed;

  return (
    <BaseWidget
      family="insight"
      title={title || 'insight'}
      meta={undefined}
      defaultOpen
      collapsedPreview={<span className="italic">{truncate(summary ?? '', 60)}</span>}
    >
      <div className="p-3.5 space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          <ConfidenceBadge value={confidence} />
        </div>

        {summary && <Prose label="summary" text={summary} accent="#16a34a" />}

        {segment_cuts.length > 0 && (
          <div>
            <span className="text-[9.5px] font-bold uppercase tracking-widest block mb-1" style={{ color: '#9c9088' }}>
              segment cuts explored
            </span>
            <div className="flex flex-wrap gap-1.5">
              {segment_cuts.map((s: string, i: number) => (
                <span key={i} className="text-[11px] font-mono px-2 py-0.5 rounded-full"
                  style={{ color: '#1c1814', backgroundColor: '#f0ece6' }}>
                  {s}
                </span>
              ))}
            </div>
          </div>
        )}

        {related_known_issues.length > 0 && (
          <div>
            <span className="text-[9.5px] font-bold uppercase tracking-widest block mb-1" style={{ color: '#9c9088' }}>
              related known issues ({related_known_issues.length})
            </span>
            <div className="space-y-1.5">
              {related_known_issues.map((ki: any, i: number) => {
                const parsedKi = typeof ki === 'string' ? (() => { try { return JSON.parse(ki); } catch { return { issue: ki }; } })() : ki;
                return (
                  <div key={i} className="rounded-lg border p-2.5 text-[11.5px]" style={{ borderColor: '#e5dfd6', backgroundColor: '#faf8f5' }}>
                    <span className="font-semibold" style={{ color: '#1c1814' }}>{parsedKi.issue}</span>
                    {parsedKi.status && (
                      <span className="ml-2 text-[10px] font-semibold uppercase" style={{ color: '#9c9088' }}>{parsedKi.status}</span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {report_html && (
          <p className="text-[11px]" style={{ color: '#9c9088' }}>
            Full HTML report written ({Math.round(String(report_html).length / 1024)} KB) — view it from the Insights list once this run finishes.
          </p>
        )}
      </div>
    </BaseWidget>
  );
}

// ── Approved (the gate passing, distinct from the reviewer's own verdict) ─────
// orchestrator/pipeline.py's "approved" step -- logged right where the
// pipeline actually transitions the proposal to status="approved", between
// the reviewer's own turn and the real execution that follows. A revision
// that only proceeded because MAX_REVISIONS was hit (not a genuine approve)
// is flagged distinctly rather than looking identical to a clean pass.

export function ApprovedWidget({ event }: { event: AgentEvent }) {
  const parsed = parseOutput(event.output);
  if (!parsed) return <FallbackRaw event={event} family="approved" title="approved" />;

  const { table_name, verdict, revision, proceeded_at_revision_cap, confidence } = parsed;

  return (
    <BaseWidget
      family="approved"
      title={table_name || 'approved'}
      meta={undefined}
      defaultOpen
      collapsedPreview={proceeded_at_revision_cap ? <span className="italic">forced at revision cap</span> : undefined}
    >
      <div className="p-3.5 space-y-2.5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-[11.5px] font-bold px-2 py-0.5 rounded"
            style={{
              color: proceeded_at_revision_cap ? '#d97706' : '#16a34a',
              backgroundColor: proceeded_at_revision_cap ? '#d9770615' : '#16a34a15',
            }}>
            {proceeded_at_revision_cap ? 'Proceeding at revision cap' : 'Approved'}
          </span>
          <ConfidenceBadge value={confidence} />
          {revision != null && (
            <span className="text-[10.5px] font-mono" style={{ color: '#9c9088' }}>revision {revision}</span>
          )}
        </div>
        {proceeded_at_revision_cap && (
          <p className="text-[11.5px] leading-relaxed" style={{ color: '#7a7068' }}>
            The reviewer's verdict was <span className="font-mono">{verdict}</span>, but the revision budget was
            exhausted -- proceeding to execution anyway rather than looping forever, with confidence clamped down.
          </p>
        )}
      </div>
    </BaseWidget>
  );
}

// ── Execution (what actually landed in ClickHouse) ────────────────────────────
// orchestrator/pipeline.py's "executed" step -- deterministic Python output,
// not an LLM turn, but the single most concrete "what happened" moment in
// the whole run: the real DDL that ran and the real row count that landed.

export function ExecutionWidget({ event }: { event: AgentEvent }) {
  const parsed = parseOutput(event.output);
  if (!parsed) return <FallbackRaw event={event} family="execution" title="execution" />;

  const { base_table, base_table_ddl, rows_inserted, materialized_views = [] } = parsed;

  return (
    <BaseWidget
      family="execution"
      title={base_table || 'execution'}
      meta={rows_inserted != null ? `${rows_inserted.toLocaleString()} rows` : undefined}
      defaultOpen
      collapsedPreview={materialized_views.length ? <span className="italic">+{materialized_views.length} MV{materialized_views.length !== 1 ? 's' : ''}</span> : undefined}
    >
      <div className="p-3.5 space-y-3">
        <div className="flex items-center gap-2 flex-wrap">
          {base_table && (
            <span className="text-[12px] font-mono font-semibold px-2 py-0.5 rounded" style={{ color: '#1c1814', backgroundColor: '#f0ece6' }}>
              {base_table}
            </span>
          )}
          {rows_inserted != null && (
            <span className="text-[11px] font-mono tabular-nums px-1.5 py-0.5 rounded" style={{ color: '#16a34a', backgroundColor: '#16a34a15' }}>
              {rows_inserted.toLocaleString()} rows inserted
            </span>
          )}
        </div>

        {base_table_ddl && (
          <div>
            <span className="text-[9.5px] font-bold uppercase tracking-widest block mb-1" style={{ color: '#9c9088' }}>
              base table DDL (as executed)
            </span>
            <CodeBlock code={base_table_ddl} lang="sql" />
          </div>
        )}

        {materialized_views.length > 0 && (
          <div>
            <span className="text-[9.5px] font-bold uppercase tracking-widest block mb-1" style={{ color: '#9c9088' }}>
              materialized views created ({materialized_views.length})
            </span>
            <div className="space-y-2">
              {materialized_views.map((mv: any, i: number) => (
                <div key={i} className="rounded-lg border p-2.5" style={{ borderColor: '#e5dfd6', backgroundColor: '#faf8f5' }}>
                  <div className="text-[11.5px] font-mono font-semibold mb-1" style={{ color: '#1c1814' }}>{mv.name}</div>
                  {mv.ddl && <CodeBlock code={mv.ddl} lang="sql" />}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </BaseWidget>
  );
}

// ── Context Update (chronicler's committed sections) ──────────────────────────
// orchestrator/pipeline.py's "context_updated" step -- one row per
// context_versions section actually written this run. Separate from the
// chronicle_generation event (the chronicler's own reasoning turn) --
// this is the settled OUTCOME: what the context layer looks like now.

export function ContextUpdateWidget({ event }: { event: AgentEvent }) {
  const parsed = parseOutput(event.output);
  if (!parsed) return <FallbackRaw event={event} family="context_update" title="context update" />;

  const { sections = [] } = parsed;
  const newCount = sections.filter((s: any) => s.is_new).length;

  return (
    <BaseWidget
      family="context_update"
      title={`${sections.length} section${sections.length !== 1 ? 's' : ''} updated`}
      meta={newCount > 0 ? `${newCount} new` : undefined}
      defaultOpen
      collapsedPreview={<span className="italic">{sections.slice(0, 3).map((s: any) => s.section).join(', ')}</span>}
    >
      <div className="p-3.5 space-y-1.5">
        {sections.length === 0 ? (
          <p className="text-[11.5px]" style={{ color: '#9c9088' }}>No sections updated.</p>
        ) : sections.map((s: any, i: number) => (
          <div key={i} className="rounded-lg border p-2.5" style={{ borderColor: '#e5dfd6', backgroundColor: '#faf8f5' }}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-[11px] font-mono font-semibold" style={{ color: '#1c1814' }}>{s.section}</span>
              <span className="text-[9.5px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded"
                style={{
                  color: s.is_new ? '#7c3aed' : '#9c9088',
                  backgroundColor: s.is_new ? '#7c3aed18' : '#f0ece6',
                }}>
                {s.is_new ? 'new' : 'updated'}
              </span>
            </div>
            {s.title && <p className="text-[11.5px]" style={{ color: '#4a4540' }}>{s.title}</p>}
            {s.diff_summary && (
              <p className="text-[11px] mt-1" style={{ color: '#7a7068' }}>{s.diff_summary}</p>
            )}
          </div>
        ))}
      </div>
    </BaseWidget>
  );
}

// Fallback if output somehow doesn't parse as JSON (shouldn't happen — the
// proposer/reviewer are both strict-json_schema constrained — but never
// silently show nothing).
function FallbackRaw({ event, family, title }: { event: AgentEvent; family: string; title: string }) {
  const text = typeof event.output === 'string' ? event.output : JSON.stringify(event.output, null, 2);
  return (
    <BaseWidget family={family} title={title} defaultOpen>
      <pre className="p-3.5 text-[11px] font-mono whitespace-pre-wrap overflow-x-auto" style={{ color: '#4a4540' }}>
        {text}
      </pre>
    </BaseWidget>
  );
}
