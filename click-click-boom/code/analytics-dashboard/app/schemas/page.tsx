'use client';

import { useEffect, useLayoutEffect, useCallback, useRef, useState } from 'react';
import { Database, X, ExternalLink, Copy, Check, ChevronDown, ChevronRight, Loader2 } from 'lucide-react';
import { TraceViewer } from '@/components/trace/TraceViewer';
import type { AgentEvent } from '@/components/trace/types';

// ── types ─────────────────────────────────────────────────────────────────────

interface SchemaItem {
  proposal_id: string;
  spec_name: string;
  table_name: string;
  engine: string;
  status: string;        // empty string if not tracked in schema_proposals
  confidence: number;
  ordering_key: string;
  ddl: string;
  materialized_views: string;
  rationale: string;
  trace_url: string;
  created_at: string;
}

// ── helpers ───────────────────────────────────────────────────────────────────

function tryParseJSON(v: unknown): unknown {
  if (typeof v !== 'string' || v === '') return v;
  try { return JSON.parse(v); } catch { return v; }
}

function normalizeEvent(raw: Record<string, any>): AgentEvent {
  const usage    = tryParseJSON(raw.usage)    as AgentEvent['usage'] | undefined;
  const metadata = tryParseJSON(raw.metadata) as Record<string, any> | undefined;
  return {
    id:             crypto.randomUUID(),
    ts:             raw.ts_ms ?? (raw.ts ?? Date.now() / 1000) * 1000,
    kind:           raw.kind ?? 'log',
    step:           raw.step ?? raw.event ?? '',
    agent:          raw.agent,
    spec:           raw.spec ?? raw.spec_name,
    trace_id:       raw.trace_id,
    trace_url:      raw.trace_url,
    input:          tryParseJSON(raw.input),
    output:         tryParseJSON(raw.output),
    reasoning:      raw.reasoning || undefined,
    model_reasoning: metadata?.model_reasoning ?? undefined,
    usage:          usage && typeof usage === 'object' && Object.keys(usage).length ? usage : undefined,
    n_tool_calls:   metadata?.n_tool_calls,
  };
}

const STATUS_COLOR: Record<string, string> = {
  executed:       '#16a34a',
  approved:       '#2563eb',
  pending_review: '#d97706',
  needs_rework:   '#ea580c',
  rejected:       '#dc2626',
  drafted:        '#9c9088',
  '':             '#16a34a',   // table exists in atlys but not tracked — show as live
};

// ClickHouse system.tables returns create_table_query as a single long line.
// This breaks it into readable multi-line format.
function formatDDL(ddl: string): string {
  if (!ddl) return '';
  // Already formatted (contains real newlines + indentation)
  if ((ddl.match(/\n/g) ?? []).length > 3) return ddl;

  try {
    // Locate the opening paren for the column list (skip nested parens in db/table path)
    let parenDepth = 0;
    let colStart = -1;
    let colEnd   = -1;
    for (let i = 0; i < ddl.length; i++) {
      if (ddl[i] === '(') {
        parenDepth++;
        if (parenDepth === 1) { colStart = i; }
      } else if (ddl[i] === ')') {
        parenDepth--;
        if (parenDepth === 0 && colStart !== -1) { colEnd = i; break; }
      }
    }

    if (colStart === -1 || colEnd === -1) {
      // No column block (e.g. simple MATERIALIZED VIEW … AS SELECT …)
      return ddl
        .replace(/\s+(AS\s+SELECT)\s+/g, '\nAS SELECT\n    ')
        .replace(/\s+FROM\s+/g, '\nFROM ')
        .replace(/\s+WHERE\s+/g, '\nWHERE ')
        .replace(/\s+GROUP BY\s+/g, '\nGROUP BY ');
    }

    const header  = ddl.slice(0, colStart).trim();
    const colBody = ddl.slice(colStart + 1, colEnd);
    const rest    = ddl.slice(colEnd + 1).trim();

    // Split columns respecting nested parens / angle brackets
    const cols: string[] = [];
    let depth = 0;
    let cur   = '';
    for (const ch of colBody) {
      if (ch === '(' || ch === '<') depth++;
      else if (ch === ')' || ch === '>') depth--;
      if (ch === ',' && depth === 0) {
        cols.push(cur.trim());
        cur = '';
      } else {
        cur += ch;
      }
    }
    if (cur.trim()) cols.push(cur.trim());

    // Format trailing clauses onto their own lines
    const formatted = rest
      .replace(/\s+ENGINE\s*=/g,      '\nENGINE =')
      .replace(/\s+PARTITION BY\s+/g, '\nPARTITION BY ')
      .replace(/\s+ORDER BY\s+/g,     '\nORDER BY ')
      .replace(/\s+PRIMARY KEY\s+/g,  '\nPRIMARY KEY ')
      .replace(/\s+SAMPLE BY\s+/g,    '\nSAMPLE BY ')
      .replace(/\s+TTL\s+/g,          '\nTTL ')
      .replace(/\s+SETTINGS\s+/g,     '\nSETTINGS ')
      .trim();

    return `${header}\n(\n    ${cols.join(',\n    ')}\n)\n${formatted}`;
  } catch {
    return ddl;
  }
}

function fmtDate(ts: string): string {
  try {
    const d = new Date(ts.replace(' ', 'T') + 'Z');
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch { return ts.slice(5, 10); }
}

// ── copy button ────────────────────────────────────────────────────────────────

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const copy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };
  return (
    <button
      onClick={copy}
      className="flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium transition-opacity hover:opacity-70"
      style={{ color: copied ? '#16a34a' : '#9c9088', backgroundColor: '#f0ece6' }}
    >
      {copied ? <Check className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
      {copied ? 'Copied' : 'Copy'}
    </button>
  );
}

// ── schema card (middle list) ─────────────────────────────────────────────────

function SchemaCard({ schema, selected, onSelect }: {
  schema: SchemaItem;
  selected: boolean;
  onSelect: () => void;
}) {
  const isMV  = schema.engine === 'MaterializedView';
  const color = isMV ? '#7c3aed' : (STATUS_COLOR[schema.status] ?? '#9c9088');
  const pct     = Math.round(schema.confidence * 100);
  const confClr = pct >= 80 ? '#16a34a' : pct >= 60 ? '#d97706' : '#dc2626';

  return (
    <button
      onClick={onSelect}
      className="w-full text-left rounded-xl border transition-colors hover:bg-stone-50"
      style={{
        borderColor:     selected ? '#2563eb' : '#e5dfd6',
        backgroundColor: selected ? '#eff6ff' : '#ffffff',
        outline:         selected ? '1px solid #2563eb' : 'none',
        outlineOffset:   '-1px',
      }}
    >
      <div className="flex items-center gap-2.5 px-4 py-3.5">
        <span className="h-2 w-2 flex-shrink-0 rounded-full" style={{ backgroundColor: color }} />
        <span className="text-[13px] font-semibold font-mono truncate" style={{ color: '#1c1814' }}>
          {schema.table_name}
        </span>
        <div className="ml-auto flex items-center gap-3 flex-shrink-0">
          {pct > 0 && (
            <span className="text-[10px] font-mono font-semibold" style={{ color: confClr }}>
              {pct}%
            </span>
          )}
          <span className="text-[10px] font-mono" style={{ color: '#9c9088' }}>
            {schema.engine}
          </span>
          <span className="text-[10px] font-mono tabular-nums" style={{ color: '#c0b8b0' }}>
            {fmtDate(schema.created_at)}
          </span>
        </div>
      </div>
    </button>
  );
}

// ── right panel ───────────────────────────────────────────────────────────────

function SchemaPanel({ schema, onClose }: { schema: SchemaItem; onClose: () => void }) {
  const [traceEvents,   setTraceEvents]   = useState<AgentEvent[]>([]);
  const [traceLoading,  setTraceLoading]  = useState(false);
  const [ddlOpen,       setDdlOpen]       = useState(true);
  const [mvsOpen,       setMvsOpen]       = useState(false);

  // Resizable drag
  const [width,     setWidth]     = useState(540);
  const dragging    = useRef(false);
  const dragStartX  = useRef(0);
  const dragStartW  = useRef(0);

  const onDragStart = useCallback((e: React.MouseEvent) => {
    dragging.current = true;
    dragStartX.current = e.clientX;
    dragStartW.current = width;
    document.body.style.cursor    = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [width]);

  useLayoutEffect(() => {
    const onMove = (e: MouseEvent) => {
      if (!dragging.current) return;
      const delta = dragStartX.current - e.clientX;
      setWidth(Math.min(900, Math.max(320, dragStartW.current + delta)));
    };
    const onUp = () => {
      dragging.current = false;
      document.body.style.cursor    = '';
      document.body.style.userSelect = '';
    };
    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup',   onUp);
    return () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup',   onUp);
    };
  }, []);

  // Fetch trace events — only possible if table was tracked through the pipeline
  useEffect(() => {
    setTraceEvents([]);
    if (!schema.spec_name) return;
    setTraceLoading(true);
    fetch(`/api/specs/${encodeURIComponent(schema.spec_name)}/events`)
      .then(r => r.json())
      .then(d => setTraceEvents((d.events ?? []).map(normalizeEvent)))
      .catch(() => setTraceEvents([]))
      .finally(() => setTraceLoading(false));
  }, [schema.spec_name]);

  const color = STATUS_COLOR[schema.status] ?? '#9c9088';
  const pct   = Math.round(schema.confidence * 100);
  const mvs   = schema.materialized_views?.trim().split('\n\n').filter(Boolean) ?? [];

  return (
    <div
      className="relative flex h-full flex-shrink-0 flex-col border-l"
      style={{ width, backgroundColor: '#ffffff', borderColor: '#e5dfd6' }}
    >
      {/* Drag handle */}
      <div
        onMouseDown={onDragStart}
        className="absolute left-0 top-0 z-10 h-full w-1 cursor-col-resize transition-colors hover:bg-blue-400/30"
      />

      {/* Header */}
      <div
        className="flex h-14 flex-shrink-0 items-center justify-between border-b px-4"
        style={{ borderColor: '#e5dfd6' }}
      >
        <div className="flex items-center gap-2 min-w-0">
          <span className="h-2 w-2 flex-shrink-0 rounded-full" style={{ backgroundColor: color }} />
          <span className="text-sm font-semibold font-mono truncate" style={{ color: '#1c1814' }}>
            {schema.table_name || schema.spec_name}
          </span>
          <span
            className="flex-shrink-0 text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded"
            style={{ color, backgroundColor: color + '18' }}
          >
            {schema.status}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {schema.trace_url && (
            <a
              href={schema.trace_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs font-medium hover:opacity-70"
              style={{ color: '#2563eb' }}
            >
              Langfuse <ExternalLink className="h-3 w-3" />
            </a>
          )}
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-lg hover:bg-stone-100 transition-colors"
            style={{ color: '#9c9088' }}
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* ── Final Schema ──────────────────────────────────────── */}
        <div className="rounded-xl border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
          <div className="px-4 py-2.5 border-b" style={{ borderColor: '#f0ece6', backgroundColor: '#faf8f5' }}>
            <p className="text-[9.5px] font-bold uppercase tracking-widest" style={{ color: '#9c9088' }}>
              Final Schema
            </p>
          </div>

          <div className="px-4 py-3 space-y-3">
            {/* Metadata */}
            <div className="grid grid-cols-2 gap-x-4 gap-y-2.5">
              <div>
                <p className="text-[9px] font-bold uppercase tracking-widest mb-0.5" style={{ color: '#c0b8b0' }}>Engine</p>
                <p className="text-xs font-mono font-medium" style={{ color: '#1c1814' }}>
                  {schema.engine || '—'}
                </p>
              </div>
              {pct > 0 && (
                <div>
                  <p className="text-[9px] font-bold uppercase tracking-widest mb-0.5" style={{ color: '#c0b8b0' }}>Confidence</p>
                  <p
                    className="text-xs font-mono font-semibold"
                    style={{ color: pct >= 80 ? '#16a34a' : pct >= 60 ? '#d97706' : '#dc2626' }}
                  >
                    {pct}%
                  </p>
                </div>
              )}
              {schema.ordering_key && (
                <div className="col-span-2">
                  <p className="text-[9px] font-bold uppercase tracking-widest mb-0.5" style={{ color: '#c0b8b0' }}>Ordering key</p>
                  <p className="text-xs font-mono" style={{ color: '#4a4540' }}>{schema.ordering_key}</p>
                </div>
              )}
              {schema.spec_name && (
                <div className="col-span-2">
                  <p className="text-[9px] font-bold uppercase tracking-widest mb-0.5" style={{ color: '#c0b8b0' }}>Spec</p>
                  <p className="text-xs font-mono" style={{ color: '#4a4540' }}>{schema.spec_name}</p>
                </div>
              )}
              {schema.rationale && (
                <div className="col-span-2">
                  <p className="text-[9px] font-bold uppercase tracking-widest mb-0.5" style={{ color: '#c0b8b0' }}>Rationale</p>
                  <p className="text-xs leading-relaxed" style={{ color: '#4a4540' }}>{schema.rationale}</p>
                </div>
              )}
            </div>

            {/* DDL */}
            {schema.ddl && (
              <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
                <button
                  onClick={() => setDdlOpen(v => !v)}
                  className="flex w-full items-center justify-between px-3 py-2 hover:bg-white transition-colors"
                  style={{ backgroundColor: '#faf8f5' }}
                >
                  <span className="text-xs font-semibold" style={{ color: '#4a4540' }}>DDL</span>
                  <div className="flex items-center gap-2">
                    {ddlOpen && <CopyButton text={schema.ddl} />}
                    {ddlOpen
                      ? <ChevronDown  className="h-3.5 w-3.5" style={{ color: '#9c9088' }} />
                      : <ChevronRight className="h-3.5 w-3.5" style={{ color: '#9c9088' }} />}
                  </div>
                </button>
                {ddlOpen && (
                  <pre
                    className="p-3.5 text-[11.5px] font-mono leading-relaxed border-t"
                    style={{
                      borderColor:     '#e5dfd6',
                      backgroundColor: '#0f0e0c',
                      color:           '#e8e4df',
                      maxHeight:       '360px',
                      overflowY:       'auto',
                      overflowX:       'auto',
                      whiteSpace:      'pre',
                    }}
                  >
                    {formatDDL(schema.ddl)}
                  </pre>
                )}
              </div>
            )}

            {/* Materialized views */}
            {mvs.length > 0 && (
              <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
                <button
                  onClick={() => setMvsOpen(v => !v)}
                  className="flex w-full items-center justify-between px-3 py-2 hover:bg-white transition-colors"
                  style={{ backgroundColor: '#faf8f5' }}
                >
                  <span className="text-xs font-semibold" style={{ color: '#4a4540' }}>
                    Materialized views ({mvs.length})
                  </span>
                  {mvsOpen
                    ? <ChevronDown  className="h-3.5 w-3.5" style={{ color: '#9c9088' }} />
                    : <ChevronRight className="h-3.5 w-3.5" style={{ color: '#9c9088' }} />}
                </button>
                {mvsOpen && (
                  <div className="border-t" style={{ borderColor: '#e5dfd6' }}>
                    {mvs.map((mv, i) => (
                      <div key={i} className={i > 0 ? 'border-t' : ''} style={{ borderColor: '#1f1d1a' }}>
                        <pre
                          className="p-3.5 text-[11px] font-mono leading-relaxed overflow-x-auto"
                          style={{ backgroundColor: '#0f0e0c', color: '#e8e4df', maxHeight: '200px', overflowY: 'auto' }}
                        >
                          {mv}
                        </pre>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* ── Agent Trace ───────────────────────────────────────── */}
        <div className="rounded-xl border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
          <div className="px-4 py-2.5 border-b" style={{ borderColor: '#f0ece6', backgroundColor: '#faf8f5' }}>
            <p className="text-[9.5px] font-bold uppercase tracking-widest" style={{ color: '#9c9088' }}>
              Agent Trace
            </p>
          </div>
          <div className="p-4">
            {traceLoading && (
              <div className="flex items-center gap-2 py-6 text-xs justify-center" style={{ color: '#9c9088' }}>
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                Loading trace…
              </div>
            )}
            {!traceLoading && traceEvents.length === 0 && (
              <p className="py-6 text-xs text-center" style={{ color: '#c0b8b0' }}>
                {schema.spec_name
                  ? 'No trace events found — re-run the spec to capture trace history.'
                  : 'This table was not created through the instrumentation pipeline.'}
              </p>
            )}
            {!traceLoading && traceEvents.length > 0 && (
              <TraceViewer events={traceEvents} active={false} />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── empty state ───────────────────────────────────────────────────────────────

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center text-center px-8">
      <div
        className="flex h-16 w-16 items-center justify-center rounded-2xl mb-5"
        style={{ backgroundColor: '#f0ece6' }}
      >
        <Database className="h-7 w-7" style={{ color: '#9c9088' }} />
      </div>
      <h2 className="text-base font-semibold" style={{ color: '#1c1814' }}>No schemas yet</h2>
      <p className="mt-1.5 max-w-xs text-sm" style={{ color: '#9c9088' }}>
        Approved schemas from the instrumentation pipeline will appear here.
      </p>
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

export default function SchemasPage() {
  const [schemas,  setSchemas]  = useState<SchemaItem[]>([]);
  const [loading,  setLoading]  = useState(true);
  const [selected, setSelected] = useState<SchemaItem | null>(null);

  useEffect(() => {
    fetch('/api/schemas')
      .then(r => r.json())
      .then(d => {
        const list = Array.isArray(d) ? d : [];
        setSchemas(list);
        if (list.length > 0) setSelected(list[0]); // open first card by default
      })
      .catch(() => setSchemas([]))
      .finally(() => setLoading(false));
  }, []);

  const handleSelect = (schema: SchemaItem) => setSelected(schema);
  const isSelected  = (schema: SchemaItem) => selected?.table_name === schema.table_name;

  return (
    <div className="flex h-full overflow-hidden" style={{ backgroundColor: '#faf8f5' }}>

      {/* ── Middle: list ─────────────────────────────────────────── */}
      <div className="flex flex-1 flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <div
          className="flex items-center justify-between border-b px-8 py-5 flex-shrink-0"
          style={{ borderColor: '#e5dfd6', backgroundColor: '#ffffff' }}
        >
          <div>
            <h1 className="text-lg font-semibold" style={{ color: '#1c1814' }}>Schemas</h1>
            <p className="mt-0.5 text-sm" style={{ color: '#9c9088' }}>
              Approved ClickHouse tables created by the instrumentation agent.
            </p>
          </div>
          {!loading && schemas.length > 0 && (
            <span className="text-sm font-mono" style={{ color: '#9c9088' }}>
              {schemas.length} table{schemas.length !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        {/* Schema list */}
        <div className="flex-1 overflow-y-auto px-8 py-6">
          {loading && (
            <div className="flex h-40 items-center justify-center">
              <p className="text-sm" style={{ color: '#9c9088' }}>Loading schemas…</p>
            </div>
          )}

          {!loading && schemas.length === 0 && <EmptyState />}

          {!loading && schemas.length > 0 && (() => {
            const tables = schemas.filter(s => s.engine !== 'MaterializedView');
            const mvs    = schemas.filter(s => s.engine === 'MaterializedView');
            return (
              <div className="space-y-6">
                {tables.length > 0 && (
                  <section>
                    <p className="text-[9.5px] font-bold uppercase tracking-widest mb-3"
                      style={{ color: '#9c9088' }}>
                      Tables ({tables.length})
                    </p>
                    <div className="space-y-2">
                      {tables.map(s => (
                        <SchemaCard
                          key={s.table_name}
                          schema={s}
                          selected={isSelected(s)}
                          onSelect={() => handleSelect(s)}
                        />
                      ))}
                    </div>
                  </section>
                )}

                {mvs.length > 0 && (
                  <section>
                    <p className="text-[9.5px] font-bold uppercase tracking-widest mb-3"
                      style={{ color: '#9c9088' }}>
                      Materialized Views ({mvs.length})
                    </p>
                    <div className="space-y-2">
                      {mvs.map(s => (
                        <SchemaCard
                          key={s.table_name}
                          schema={s}
                          selected={isSelected(s)}
                          onSelect={() => handleSelect(s)}
                        />
                      ))}
                    </div>
                  </section>
                )}
              </div>
            );
          })()}
        </div>
      </div>

      {/* ── Right panel ──────────────────────────────────────────── */}
      {selected && (
        <SchemaPanel
          schema={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </div>
  );
}
