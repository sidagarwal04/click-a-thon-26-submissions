'use client';
import { BaseWidget } from '../BaseWidget';
import type { ContextSection } from '../types';

// ── Lookup Context ────────────────────────────────────────────────────────────

interface LookupProps { step: string; input?: unknown; output?: unknown; defaultOpen?: boolean }

function ConfidenceDot({ score }: { score?: number }) {
  if (score == null) return null;
  const color = score >= 0.8 ? '#16a34a' : score >= 0.6 ? '#d97706' : '#dc2626';
  return (
    <span className="flex items-center gap-1 text-[10px]" style={{ color }}>
      <span className="h-1.5 w-1.5 rounded-full inline-block" style={{ backgroundColor: color }} />
      {Math.round(score * 100)}%
    </span>
  );
}

function SectionCard({ section }: { section: ContextSection }) {
  const prefix = section.section.split(':')[0];
  const badgeColor: Record<string, string> = {
    issue:        '#dc2626', metric: '#2563eb', convention: '#7c3aed',
    table:        '#16a34a', relationship: '#0891b2', dataquality: '#d97706',
    overview:     '#6b7280', entity: '#6b7280',
  };
  const bc = badgeColor[prefix] ?? '#9c9088';

  return (
    <div className="rounded-xl border p-3 space-y-1.5" style={{ borderColor: '#e5dfd6', backgroundColor: '#ffffff' }}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase px-1.5 py-0.5 rounded"
            style={{ color: bc, backgroundColor: bc + '15' }}>
            {section.section}
          </span>
          {section.title && <span className="text-xs font-medium" style={{ color: '#1c1814' }}>{section.title}</span>}
        </div>
        <ConfidenceDot score={section.confidence} />
      </div>
      {section.summary && (
        <p className="text-xs leading-relaxed" style={{ color: '#4a4540' }}>{section.summary}</p>
      )}
      {section.body && (
        <details className="group">
          <summary className="text-[11px] cursor-pointer hover:opacity-70" style={{ color: '#14b8a6' }}>
            full body ▼
          </summary>
          <pre className="mt-2 text-[11px] leading-relaxed whitespace-pre-wrap font-sans overflow-x-auto max-h-40"
            style={{ color: '#4a4540' }}>
            {section.body}
          </pre>
        </details>
      )}
    </div>
  );
}

export function ContextLookupWidget({ step, input, output, defaultOpen }: LookupProps) {
  const sections = Array.isArray(output) ? output as ContextSection[] : [];
  const keys = sections.map(s => s.section);

  return (
    <BaseWidget
      family="context_lookup"
      title={keys.slice(0, 3).join(', ') + (keys.length > 3 ? ` +${keys.length - 3}` : '')}
      meta={`${sections.length} section${sections.length !== 1 ? 's' : ''}`}
      defaultOpen={defaultOpen}
      collapsedPreview={<>{keys.slice(0, 4).join(' · ')}</>}
    >
      <div className="p-3.5 space-y-2">
        {sections.map((s, i) => <SectionCard key={i} section={s} />)}
      </div>
    </BaseWidget>
  );
}

// ── List Context Sections ─────────────────────────────────────────────────────

interface IndexProps { step: string; output?: unknown; defaultOpen?: boolean }

export function ContextIndexWidget({ step, output, defaultOpen }: IndexProps) {
  const sections = Array.isArray(output) ? output as ContextSection[] : [];

  return (
    <BaseWidget
      family="context_index"
      title="all context sections"
      meta={`${sections.length} sections`}
      defaultOpen={defaultOpen}
    >
      <div className="p-3.5">
        <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#e5dfd6' }}>
          <div className="overflow-y-auto max-h-72">
            <table className="text-xs w-full">
              <thead>
                <tr style={{ backgroundColor: '#f0fdfa' }}>
                  {['section', 'summary', 'confidence'].map(h => (
                    <th key={h} className="text-left px-3 py-2 font-semibold border-b capitalize"
                      style={{ color: '#0f766e', borderColor: '#ccfbf1' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sections.map((s, i) => (
                  <tr key={i} className="border-b last:border-0" style={{ borderColor: '#f0ece6' }}>
                    <td className="px-3 py-1.5 font-mono text-[11px] whitespace-nowrap" style={{ color: '#0f766e' }}>{s.section}</td>
                    <td className="px-3 py-1.5 max-w-xs truncate" style={{ color: '#4a4540' }}>{s.summary}</td>
                    <td className="px-3 py-1.5"><ConfidenceDot score={s.confidence} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </BaseWidget>
  );
}
