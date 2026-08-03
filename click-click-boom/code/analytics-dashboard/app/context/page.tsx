'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  Compass, Users, Database, Calculator, GitBranch, BookOpen, AlertTriangle,
  AlertCircle, ExternalLink, ChevronDown, ChevronRight, History, ArrowLeft,
} from 'lucide-react';
import type { ContextSection, ContextVersion } from '@/lib/types';

// ── taxonomy ──────────────────────────────────────────────────────────────────
// Section keys are "prefix:name" (see mcp_servers/context_server.py's docstring
// and atlys-agents/scripts/seed_context.py) -- the prefix IS the taxonomy, not
// something the dashboard invents.

type TaxonomyMeta = { label: string; icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>; accent: string };

const TAXONOMY: Record<string, TaxonomyMeta> = {
  overview:     { label: 'Overview',       icon: Compass,       accent: '#7c3aed' },
  entity:       { label: 'Entities',       icon: Users,         accent: '#2563eb' },
  table:        { label: 'Tables',         icon: Database,      accent: '#d97706' },
  metric:       { label: 'Metrics',        icon: Calculator,    accent: '#16a34a' },
  relationship: { label: 'Relationships',  icon: GitBranch,     accent: '#0d9488' },
  convention:   { label: 'Conventions',    icon: BookOpen,      accent: '#7c3aed' },
  dataquality:  { label: 'Data Quality',   icon: AlertTriangle, accent: '#d97706' },
  issue:        { label: 'Known Issues',   icon: AlertCircle,   accent: '#dc2626' },
};
const GROUP_ORDER = ['overview', 'entity', 'table', 'metric', 'relationship', 'convention', 'dataquality', 'issue'];

function taxonomyOf(section: string): string {
  return section.split(':')[0] ?? 'other';
}

interface SectionContent {
  title?: string;
  summary?: string;
  body?: string;
  fields?: Record<string, unknown>;
  sources?: string[];
}

function parseJSON<T>(raw: string): T | null {
  try { return JSON.parse(raw) as T; } catch { return null; }
}

function ConfidenceBadge({ value }: { value: number }) {
  const pct   = Math.round(value * 100);
  const color = pct >= 80 ? '#16a34a' : pct >= 60 ? '#d97706' : '#dc2626';
  const bg    = pct >= 80 ? '#f0fdf4' : pct >= 60 ? '#fffbeb' : '#fef2f2';
  return (
    <span className="flex-shrink-0 text-[11px] font-bold tabular-nums font-mono rounded-md px-1.5 py-0.5"
      style={{ color, backgroundColor: bg }}>
      {pct}%
    </span>
  );
}

// ── fields renderer ──────────────────────────────────────────────────────────
// `fields` is section-type-specific free-form JSON (see seed_context.py) --
// no fixed shape, so render generically: scalars inline, arrays as chips,
// nested objects as a small indented list.

function FieldValue({ value }: { value: unknown }) {
  if (value == null) return <span style={{ color: '#c0b8b0' }}>—</span>;
  if (Array.isArray(value)) {
    if (value.length === 0) return <span style={{ color: '#c0b8b0' }}>—</span>;
    return (
      <div className="flex flex-wrap gap-1">
        {value.map((v, i) => (
          <span key={i} className="text-[11px] font-mono px-1.5 py-0.5 rounded" style={{ backgroundColor: '#f0ece6', color: '#4a4540' }}>
            {typeof v === 'object' ? JSON.stringify(v) : String(v)}
          </span>
        ))}
      </div>
    );
  }
  if (typeof value === 'object') {
    return (
      <pre className="text-[11px] font-mono whitespace-pre-wrap" style={{ color: '#4a4540' }}>
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  if (typeof value === 'boolean') {
    return <span style={{ color: value ? '#16a34a' : '#dc2626' }}>{String(value)}</span>;
  }
  return <span className="font-mono text-[12.5px]" style={{ color: '#1c1814' }}>{String(value)}</span>;
}

function FieldsTable({ fields }: { fields: Record<string, unknown> }) {
  const entries = Object.entries(fields ?? {});
  if (entries.length === 0) return null;
  return (
    <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
      {entries.map(([k, v], i) => (
        <div key={k} className="grid gap-3 px-3 py-2 border-b last:border-0"
          style={{ gridTemplateColumns: '160px 1fr', borderColor: '#f0ece6', backgroundColor: i % 2 ? '#faf8f5' : '#ffffff' }}>
          <span className="text-[11px] font-semibold font-mono truncate" style={{ color: '#9c9088' }}>{k}</span>
          <FieldValue value={v} />
        </div>
      ))}
    </div>
  );
}

// ── knowledge browser ────────────────────────────────────────────────────────

function SectionRow({ section, active, onClick }: { section: ContextSection; active: boolean; onClick: () => void }) {
  const content = parseJSON<SectionContent>(section.content);
  return (
    <button
      onClick={onClick}
      className="w-full flex items-start gap-2.5 px-3 py-2.5 text-left border-b last:border-0 transition-colors"
      style={{ borderColor: '#f0ece6', backgroundColor: active ? '#eef2ff' : 'transparent' }}>
      <div className="min-w-0 flex-1">
        <p className="text-[12.5px] font-semibold leading-snug truncate" style={{ color: active ? '#3730a3' : '#1c1814' }}>
          {content?.title || section.section}
        </p>
        <p className="text-[11px] font-mono truncate mt-0.5" style={{ color: '#c0b8b0' }}>{section.section}</p>
      </div>
      <ConfidenceBadge value={section.confidence} />
    </button>
  );
}

function TaxonomyGroup({ groupKey, sections, activeSection, onSelect }: {
  groupKey: string; sections: ContextSection[]; activeSection: string | null; onSelect: (s: string) => void;
}) {
  const [open, setOpen] = useState(true);
  const meta = TAXONOMY[groupKey] ?? { label: groupKey, icon: Compass, accent: '#6b7280' };
  const Icon = meta.icon;
  return (
    <div className="border-b last:border-0" style={{ borderColor: '#e5dfd6' }}>
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-stone-50 transition-colors">
        <Icon className="h-3.5 w-3.5 flex-shrink-0" style={{ color: meta.accent }} />
        <span className="text-[11px] font-bold uppercase tracking-wider" style={{ color: meta.accent }}>{meta.label}</span>
        <span className="text-[10px] font-mono" style={{ color: '#c0b8b0' }}>{sections.length}</span>
        <div className="flex-1" />
        {open ? <ChevronDown className="h-3 w-3" style={{ color: '#c0b8b0' }} /> : <ChevronRight className="h-3 w-3" style={{ color: '#c0b8b0' }} />}
      </button>
      {open && sections.map(s => (
        <SectionRow key={s.section} section={s} active={s.section === activeSection} onClick={() => onSelect(s.section)} />
      ))}
    </div>
  );
}

function SectionDetail({ section, onViewHistory }: { section: ContextSection; onViewHistory: () => void }) {
  const content = parseJSON<SectionContent>(section.content);
  return (
    <div className="p-6 space-y-5">
      <div>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-mono" style={{ color: '#9c9088' }}>{section.section}</p>
            <h2 className="text-lg font-semibold mt-0.5" style={{ color: '#1c1814' }}>{content?.title || section.section}</h2>
          </div>
          <ConfidenceBadge value={section.confidence} />
        </div>
        {content?.summary && (
          <p className="mt-2 text-sm leading-relaxed" style={{ color: '#4a4540' }}>{content.summary}</p>
        )}
      </div>

      {content?.body && (
        <p className="text-[13px] leading-relaxed whitespace-pre-wrap" style={{ color: '#4a4540' }}>{content.body}</p>
      )}

      {content?.fields && Object.keys(content.fields).length > 0 && (
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: '#9c9088' }}>Fields</p>
          <FieldsTable fields={content.fields} />
        </div>
      )}

      {content?.sources && content.sources.length > 0 && (
        <div>
          <p className="text-[10px] font-bold uppercase tracking-wider mb-1.5" style={{ color: '#9c9088' }}>Sources</p>
          <div className="flex flex-wrap gap-1.5">
            {content.sources.map((s, i) => (
              <span key={i} className="text-[11px] font-mono px-2 py-0.5 rounded-full" style={{ backgroundColor: '#f0ece6', color: '#4a4540' }}>
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="flex items-center justify-between pt-3 border-t" style={{ borderColor: '#f0ece6' }}>
        <button onClick={onViewHistory}
          className="flex items-center gap-1.5 text-xs font-semibold hover:opacity-70" style={{ color: '#1c1814' }}>
          <History className="h-3.5 w-3.5" /> View change history
        </button>
        <div className="flex items-center gap-3">
          <span className="text-[11px]" style={{ color: '#c0b8b0' }}>updated {section.last_updated}</span>
          {section.trace_url && (
            <a href={section.trace_url} target="_blank" rel="noopener noreferrer"
              className="flex items-center gap-1 text-xs font-medium hover:opacity-70" style={{ color: '#2563eb' }}>
              trace <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

function KnowledgeView({ sections, loading }: { sections: ContextSection[]; loading: boolean }) {
  const [selected, setSelected] = useState<string | null>(null);
  const [historyFor, setHistoryFor] = useState<string | null>(null);

  const groups = useMemo(() => {
    const byGroup = new Map<string, ContextSection[]>();
    for (const s of sections) {
      const key = taxonomyOf(s.section);
      const arr = byGroup.get(key) ?? [];
      arr.push(s);
      byGroup.set(key, arr);
    }
    const orderedKeys = [...GROUP_ORDER, ...[...byGroup.keys()].filter(k => !GROUP_ORDER.includes(k))];
    return orderedKeys.filter(k => byGroup.has(k)).map(k => ({ key: k, sections: byGroup.get(k)! }));
  }, [sections]);

  useEffect(() => {
    if (!selected && sections.length > 0) setSelected(sections[0].section);
  }, [sections, selected]);

  if (loading) {
    return <div className="flex h-40 items-center justify-center"><p className="text-sm" style={{ color: '#9c9088' }}>Loading…</p></div>;
  }

  if (historyFor) {
    return <ChangelogView allVersionsSection={historyFor} onBack={() => setHistoryFor(null)} />;
  }

  const activeSection = sections.find(s => s.section === selected);

  return (
    <div className="flex flex-1 min-h-0">
      <div className="w-72 flex-shrink-0 border-r overflow-y-auto" style={{ borderColor: '#e5dfd6' }}>
        {groups.map(g => (
          <TaxonomyGroup key={g.key} groupKey={g.key} sections={g.sections} activeSection={selected} onSelect={setSelected} />
        ))}
      </div>
      <div className="flex-1 overflow-y-auto">
        {activeSection
          ? <SectionDetail section={activeSection} onViewHistory={() => setHistoryFor(activeSection.section)} />
          : <div className="flex h-40 items-center justify-center"><p className="text-sm" style={{ color: '#9c9088' }}>Select a section</p></div>}
      </div>
    </div>
  );
}

// ── changelog ─────────────────────────────────────────────────────────────────

const TRIGGER_META: Record<string, { label: string; color: string }> = {
  seed:            { label: 'seed',      color: '#9c9088' },
  seed_correction: { label: 'correction', color: '#dc2626' },
  chronicle:       { label: 'chronicle', color: '#7c3aed' },
};

function VersionRow({ v }: { v: ContextVersion }) {
  const [open, setOpen] = useState(false);
  const after  = parseJSON<SectionContent>(v.after);
  const isCorrection = !!v.before;
  const tm = TRIGGER_META[v.trigger] ?? { label: v.trigger, color: '#6b7280' };

  return (
    <div className="border-b last:border-0" style={{ borderColor: '#f0ece6' }}>
      <button onClick={() => setOpen(o => !o)}
        className="w-full flex items-start gap-3 px-4 py-3 text-left hover:bg-stone-50 transition-colors">
        <span className="mt-1 h-1.5 w-1.5 flex-shrink-0 rounded-full" style={{ backgroundColor: isCorrection ? '#dc2626' : '#16a34a' }} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-[12px] font-mono font-semibold" style={{ color: '#1c1814' }}>{v.section}</span>
            <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded" style={{ color: tm.color, backgroundColor: tm.color + '15' }}>
              {tm.label}
            </span>
            {isCorrection && (
              <span className="text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded" style={{ color: '#dc2626', backgroundColor: '#fef2f2' }}>
                corrected prior claim
              </span>
            )}
          </div>
          <p className="text-[12.5px] mt-1" style={{ color: '#4a4540' }}>{v.diff_summary || after?.summary || '—'}</p>
        </div>
        <span className="flex-shrink-0 text-[11px] font-mono tabular-nums" style={{ color: '#c0b8b0' }}>{v.created_at.slice(5, 16).replace('T', ' ')}</span>
        {open ? <ChevronDown className="h-3.5 w-3.5 flex-shrink-0" style={{ color: '#c0b8b0' }} /> : <ChevronRight className="h-3.5 w-3.5 flex-shrink-0" style={{ color: '#c0b8b0' }} />}
      </button>
      {open && (
        <div className="px-4 pb-4 space-y-3" style={{ backgroundColor: '#faf8f5' }}>
          {v.rationale && (
            <div className="rounded-lg px-3 py-2.5 text-[12.5px] leading-relaxed" style={{ backgroundColor: '#eef2ff', color: '#3730a3', border: '1px solid #c7d2fe' }}>
              {v.rationale}
            </div>
          )}
          <div className="grid gap-3" style={{ gridTemplateColumns: isCorrection ? '1fr 1fr' : '1fr' }}>
            {isCorrection && (
              <div>
                <p className="text-[9.5px] font-bold uppercase tracking-widest mb-1" style={{ color: '#dc2626' }}>Before</p>
                <pre className="text-[11px] font-mono whitespace-pre-wrap p-2.5 rounded-lg" style={{ backgroundColor: '#fef2f2', color: '#7f1d1d', border: '1px solid #fecaca' }}>
                  {v.before}
                </pre>
              </div>
            )}
            <div>
              <p className="text-[9.5px] font-bold uppercase tracking-widest mb-1" style={{ color: '#16a34a' }}>After</p>
              <pre className="text-[11px] font-mono whitespace-pre-wrap p-2.5 rounded-lg max-h-64 overflow-y-auto" style={{ backgroundColor: '#f0fdf4', color: '#14532d', border: '1px solid #bbf7d0' }}>
                {after ? JSON.stringify(after, null, 2) : v.after}
              </pre>
            </div>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono" style={{ color: '#9c9088' }}>confidence {Math.round(v.confidence * 100)}%</span>
            {v.trace_url && (
              <a href={v.trace_url} target="_blank" rel="noopener noreferrer"
                className="flex items-center gap-1 text-xs font-medium hover:opacity-70" style={{ color: '#2563eb' }}>
                trace <ExternalLink className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ChangelogView({ allVersionsSection, onBack }: { allVersionsSection?: string | null; onBack?: () => void }) {
  const [versions, setVersions] = useState<ContextVersion[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const url = allVersionsSection ? `/api/context?section=${encodeURIComponent(allVersionsSection)}` : '/api/context';
    fetch(url).then(r => r.json())
      .then(d => setVersions(Array.isArray(d) ? d : []))
      .catch(() => setVersions([]))
      .finally(() => setLoading(false));
  }, [allVersionsSection]);

  return (
    <div className="flex-1 overflow-y-auto">
      {allVersionsSection && (
        <div className="flex items-center gap-2 px-4 py-2.5 border-b" style={{ borderColor: '#e5dfd6', backgroundColor: '#faf8f5' }}>
          <button onClick={onBack} className="flex items-center gap-1.5 text-xs font-medium hover:opacity-70" style={{ color: '#7a7068' }}>
            <ArrowLeft className="h-3.5 w-3.5" /> Back to section
          </button>
          <span style={{ color: '#e5dfd6' }}>/</span>
          <span className="text-xs font-mono font-semibold" style={{ color: '#1c1814' }}>{allVersionsSection}</span>
        </div>
      )}
      {loading && <div className="flex h-40 items-center justify-center"><p className="text-sm" style={{ color: '#9c9088' }}>Loading…</p></div>}
      {!loading && versions.length === 0 && (
        <div className="flex h-40 items-center justify-center"><p className="text-sm" style={{ color: '#9c9088' }}>No changelog entries.</p></div>
      )}
      {!loading && versions.length > 0 && versions.map(v => <VersionRow key={v.version_id} v={v} />)}
    </div>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

type Tab = 'knowledge' | 'changelog';

export default function ContextPage() {
  const [tab, setTab] = useState<Tab>('knowledge');
  const [sections, setSections] = useState<ContextSection[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch('/api/context/sections')
      .then(r => r.json())
      .then(d => setSections(Array.isArray(d) ? d : []))
      .catch(() => setSections([]))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="flex h-full flex-col" style={{ backgroundColor: '#faf8f5' }}>
      {/* Header */}
      <div className="flex items-center justify-between border-b px-8 py-5" style={{ borderColor: '#e5dfd6', backgroundColor: '#ffffff' }}>
        <div>
          <h1 className="text-lg font-semibold" style={{ color: '#1c1814' }}>Context</h1>
          <p className="mt-0.5 text-sm" style={{ color: '#9c9088' }}>
            The business/data knowledge layer every agent reads live — {sections.length} sections, kept current by the Context Chronicler.
          </p>
        </div>
        <div className="flex flex-shrink-0 rounded-lg border p-0.5" style={{ borderColor: '#e5dfd6' }}>
          {(['knowledge', 'changelog'] as Tab[]).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className="rounded-md px-3.5 py-1.5 text-[12.5px] font-semibold capitalize transition-colors"
              style={{ backgroundColor: tab === t ? '#1c1814' : 'transparent', color: tab === t ? '#ffffff' : '#7a7068' }}>
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      {tab === 'knowledge'
        ? <KnowledgeView sections={sections} loading={loading} />
        : <ChangelogView />}
    </div>
  );
}
